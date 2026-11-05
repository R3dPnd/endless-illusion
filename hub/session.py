import json
import os
import sys
from pathlib import Path

from . import HUB_DIR
from .db.ownership import server_name
from .tool_names import SHARED_SERVER

MEMORY_SERVER = HUB_DIR / "memory.py"


def build_session_args(tools, mcp_config_path=None, mcp_tools=(), agent_def=None, system_prompt=None):
    """
    argv for `claude -p`. `--tools` withholds tools from the session;
    `--allowedTools` only pre-approves them, so it is never the restriction.
    """
    args = ["-p", "--output-format", "stream-json", "--verbose", "--tools", ",".join(tools), "--strict-mcp-config"]
    if mcp_config_path:
        args += ["--mcp-config", str(mcp_config_path)]
    args += ["--allowedTools", ",".join([*tools, *mcp_tools])]
    if agent_def:
        args += ["--agent", agent_def]
    if system_prompt:
        args += ["--append-system-prompt", system_prompt]
    return args


def load_shared_server(repo_root):
    """
    The shared knowledge-base server entry from the repo's .mcp.json, or None
    when it is not registered. Runs use --strict-mcp-config, so it must be
    copied into each run's config to be reachable.
    """
    try:
        config = json.loads((Path(repo_root) / ".mcp.json").read_text(encoding="utf8"))
        return (config.get("mcpServers") or {}).get(SHARED_SERVER)
    except (OSError, ValueError):
        return None


def python_for_children():
    """The interpreter for MCP servers: never pythonw.exe (it has no usable stdio)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)


def write_mcp_config(directory, run_id, agents, db_file, shared=None):
    """
    Write the per-run MCP config: one ei-memory instance per participating
    agent, each pinned to that agent's identity and this run's id, plus the
    shared knowledge base when given.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    servers = {}
    if shared:
        servers[SHARED_SERVER] = shared
    for agent in agents:
        servers[server_name(agent)] = {
            "command": python_for_children(),
            "args": [str(MEMORY_SERVER), "--agent", agent, "--db", str(db_file)],
            "env": {"EI_RUN_ID": run_id},
        }
    file = directory / f"{run_id}.json"
    file.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf8")
    try:
        os.chmod(file, 0o600)
    except OSError:
        pass
    return file
