"""A small, dependency-free MCP server loop over stdio (newline-delimited JSON-RPC 2.0).

It implements the tools subset Claude Code needs: initialize, ping, tools/list and
tools/call. That is enough, and it starts fast, which matters because one
orchestrated run launches several of these servers.

    serve(tools, call, name)

- `tools`: name -> {"description": str, "inputSchema": flat object schema}.
- `call(name, args) -> result`: runs a tool after its arguments pass `check_args`.
  An exception becomes an `isError` tool result, which the agent sees; it is not a
  protocol error.
"""

from __future__ import annotations

import json
import sys
from typing import Callable

PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def check_args(schema, args):
    """Validate arguments against the (flat) input schema we publish.
    Unknown fields are refused unless the schema sets `additionalProperties` to something other than False."""
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    props = schema["properties"]
    if schema.get("additionalProperties", True) is False:
        for key in args:
            if key not in props:
                raise ValueError(f'unknown field "{key}"')
    for key in schema["required"]:
        if args.get(key) is None:
            raise ValueError(f"{key}: required")
    for key, value in args.items():
        if value is None or key not in props:
            continue
        spec = props[key]
        options = spec.get("anyOf", [spec])
        if not any(TYPE_CHECKS[o["type"]](value) for o in options):
            wanted = " or ".join(o["type"] for o in options)
            raise ValueError(f"{key}: must be {wanted}")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"{key}: must be one of {', '.join(spec['enum'])}")
        if spec.get("minLength") and len(value) < spec["minLength"]:
            raise ValueError(f"{key}: must not be empty")


def handle(message, tools, call, name):
    """One JSON-RPC message in, one response (or None for notifications) out."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    is_request = "id" in message and method is not None

    def reply(result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def error(code, text):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": text}}

    if not is_request:
        return None  # notifications (initialized, cancelled) and stray responses
    if method == "initialize":
        requested = params.get("protocolVersion")
        return reply(
            {
                "protocolVersion": requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": name, "version": "1.0.0"},
            }
        )
    if method == "ping":
        return reply({})
    if method == "tools/list":
        return reply({"tools": [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]} for n, t in tools.items()]})
    if method == "tools/call":
        tool = params.get("name")
        if tool not in tools:
            return error(-32602, f"Unknown tool: {tool} (not found)")
        args = params.get("arguments") or {}
        try:
            check_args(tools[tool]["inputSchema"], args)
            return reply(call(tool, args))
        except Exception as err:  # reported to the agent as a tool error, not a protocol error
            return reply({"isError": True, "content": [{"type": "text", "text": f"Error: {err}"}]})
    return error(-32601, f"Method not found: {method}")


def serve(tools: dict[str, dict], call: Callable[[str, dict], dict], name: str) -> None:
    """Answer MCP requests from stdin on stdout until stdin closes."""
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            batch = message if isinstance(message, list) else [message]
            responses = [r for r in (handle(m, tools, call, name) for m in batch if isinstance(m, dict)) if r]
            if not responses:
                continue
            response = responses if isinstance(message, list) else responses[0]
        out.write(json.dumps(response, ensure_ascii=False).encode("utf8") + b"\n")
        out.flush()
