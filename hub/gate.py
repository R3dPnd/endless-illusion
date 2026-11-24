#!/usr/bin/env python3
"""
Endless Illusion approval gate (`ei-gate`) — one instance per engagement stage run.

Two modes, both deciding through hub/gate_service.py (the hub decides, not a prompt):

    python hub/gate.py --db <file> --repo-root <dir>          (env EI_RUN_ID)
        MCP stdio server `ei-gate` with two tools:
          declare_action{target, why, technique, risk} -> "declared #<id>"
          permission{tool_name, input, tool_use_id}     -> Claude Code's permission-prompt tool;
              replies {"behavior":"allow"} or {"behavior":"deny","message":...} as a JSON text
              (no updatedInput, so the original input runs).

    python hub/gate.py --hook --db <file> --repo-root <dir>   (env EI_RUN_ID)
        Claude Code PreToolUse hook: reads the hook JSON on stdin, prints one
        hookSpecificOutput decision on stdout, exits 0. This is the primary gate:
        it also sees calls Claude Code would auto-allow.

Claude Code treats a hook that crashes, exits 1, times out or prints anything but a
decision as "allow" (spec §4). So the hook mode FAILS CLOSED: every error, including
bad stdin, a missing EI_RUN_ID and an unreachable DB, prints a deny decision; if even
that fails it exits 2 (a block). Its own wait ends before Claude Code's hook timeout.
Use `hook_settings` to build the `--settings` JSON; its shell wrapper turns any
non-zero exit (a missing interpreter, an import error) into exit 2.

With no engagement stage for the run (no RunContext), every gated call is denied.
"""

import argparse
import json
import os
import shlex
import sys

if __package__ in (None, ""):
    # Run as a script by claude: make the `hub` package importable.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVER_NAME = "ei-gate"  # == hub.tool_names.GATE_SERVER (not imported: the hook imports as little as possible up front)
HOOK_MATCHER = "Bash|WebFetch|Write|Edit|MultiEdit|NotebookEdit"
HOOK_TIMEOUT = 86400  # seconds, Claude Code's hook timeout
HOOK_WAIT = 86000  # our own deadline, strictly below HOOK_TIMEOUT: Claude Code's timeout fails open

STRING = {"type": "string", "minLength": 1}

TOOLS = {
    "declare_action": {
        "description": (
            "Declare a target-touching action BEFORE making it. `target` must equal the exact Bash command or "
            "WebFetch URL you will run next (byte for byte). Then make the call: the operator approves or denies it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"target": STRING, "why": STRING, "technique": STRING, "risk": STRING},
            "required": ["target", "why", "technique", "risk"],
            "additionalProperties": False,
        },
    },
    "permission": {
        "description": "Claude Code permission-prompt tool: decides one tool call through the engagement gate.",
        "inputSchema": {
            "type": "object",
            "properties": {"tool_name": STRING, "input": {"type": "object"}, "tool_use_id": {"type": "string"}},
            "required": ["tool_name", "input"],
        },
    },
}


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="gate.py")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--db", required=True)
    parser.add_argument("--repo-root", required=True)
    return parser.parse_args(argv)


def _normalize(reply) -> dict:
    """Only an explicit allow allows; anything else is a deny with a non-empty message."""
    if isinstance(reply, dict) and reply.get("behavior") == "allow":
        message = reply.get("message")
        return {"behavior": "allow", "message": message if isinstance(message, str) else ""}
    message = reply.get("message") if isinstance(reply, dict) else None
    return {"behavior": "deny", "message": message if isinstance(message, str) and message else "denied by the gate"}


# ---- MCP server mode ---------------------------------------------------------------------------

def _text(value):
    return {"content": [{"type": "text", "text": value}]}


def serve_main(args):
    from hub.db import open_db
    from hub.gate_service import check_permission, context_for_run, record_declaration, wait_for_decision
    from hub.mcp_stdio import serve

    db = open_db(args.db)
    run_id = os.environ.get("EI_RUN_ID") or None

    def permission(a):
        try:
            ctx = context_for_run(db, run_id, args.repo_root)
            reply = check_permission(
                db, ctx, a["tool_name"], a["input"], lambda aid: wait_for_decision(db, aid, run_id=ctx.run_id)
            )
        except Exception as err:  # check_permission already fails closed; this covers context lookup
            reply = {"behavior": "deny", "message": f"gate error: {type(err).__name__}"}
        reply = _normalize(reply)
        if reply["behavior"] == "allow":
            return _text(json.dumps({"behavior": "allow"}))
        return _text(json.dumps({"behavior": "deny", "message": reply["message"]}))

    def call(name, a):
        if name == "declare_action":
            did = record_declaration(db, run_id, a["target"], a["why"], a["technique"], a["risk"])
            return _text(f"declared #{did}")
        return permission(a)

    serve(TOOLS, call, SERVER_NAME)


# ---- PreToolUse hook mode ----------------------------------------------------------------------

def _hook_decide(argv) -> dict:
    args = _parse_args(argv)
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("hook input must be a JSON object")
    tool_name, tool_input = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(tool_name, str) or not tool_name or not isinstance(tool_input, dict):
        raise ValueError("hook input needs tool_name and tool_input")

    from hub.db import open_db
    from hub.gate_service import check_permission, context_for_run, wait_for_decision

    db = open_db(args.db)
    try:
        ctx = context_for_run(db, os.environ.get("EI_RUN_ID") or None, args.repo_root)
        return check_permission(
            db, ctx, tool_name, tool_input,
            lambda aid: wait_for_decision(db, aid, timeout=HOOK_WAIT, run_id=ctx.run_id),
        )
    finally:
        db.close()


def hook_main(argv) -> int:
    real_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr  # nothing but our json.dumps decision may reach Claude Code's stdout
        reply = _normalize(_hook_decide(argv))
    except BaseException as err:  # noqa: B036 - fail closed on everything, SystemExit/KeyboardInterrupt included
        reply = {"behavior": "deny", "message": f"gate hook error: {type(err).__name__}"}
    finally:
        sys.stdout = real_stdout
    try:
        out = json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": reply["behavior"],
                "permissionDecisionReason": reply["message"],
            }
        })
        real_stdout.write(out + "\n")
        real_stdout.flush()
    except BaseException:  # noqa: B036 - exit 2 is Claude Code's other "block"
        try:
            sys.stderr.write("ei-gate: could not write the hook decision; blocking\n")
        except BaseException:  # noqa: B036
            pass
        return 2
    return 0


def hook_settings(python: str, gate_py: str, db_file: str, repo_root: str) -> dict:
    """The `--settings` JSON that installs the gate as the PreToolUse hook.

    The command is a `/bin/sh -c` wrapper: any non-zero exit of the hook (missing
    interpreter, import error, crash) becomes exit 2, which blocks the call."""
    q = shlex.quote
    inner = (
        f"{q(python)} {q(gate_py)} --hook --db {q(db_file)} --repo-root {q(repo_root)}"
        " || { echo 'ei-gate: the gate hook failed; blocking the call' >&2; exit 2; }"
    )
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": HOOK_MATCHER,
                    "hooks": [{"type": "command", "command": f"/bin/sh -c {q(inner)}", "timeout": HOOK_TIMEOUT}],
                }
            ]
        }
    }


def main():
    argv = sys.argv[1:]
    if "--hook" in argv:
        code = hook_main(argv)
        os._exit(code)  # no interpreter teardown that could print or change the exit code
    serve_main(_parse_args(argv))


if __name__ == "__main__":
    main()
