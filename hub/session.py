import json
import os
import sys
from pathlib import Path

from . import HUB_DIR
from .db.ownership import server_name
from .gate import hook_settings
from .tool_names import GATE_SERVER, SHARED_SERVER

MEMORY_SERVER = HUB_DIR / "memory.py"
GATE_SERVER_PY = HUB_DIR / "gate.py"


def build_session_args(
    tools,
    mcp_config_path=None,
    mcp_tools=(),
    agent_def=None,
    system_prompt=None,
    resume=None,
    unapproved=(),
    permission_tool=None,
    fork=False,
    settings_path=None,
    permission_mode=None,
    setting_sources=None,
):
    """
    argv for `claude -p`. `--tools` withholds tools from the session;
    `--allowedTools` only pre-approves them, so it is never the restriction.

    Stage runs also pass: `unapproved` (tools kept in `--tools` but left out of
    `--allowedTools`, so every call reaches the gate), `settings_path` (the gate
    hook), `setting_sources` ("" = no user/project/local settings), a pinned
    `permission_mode`, and `permission_tool` as a backstop. `fork` forks the
    resumed session. With every one left at its default, the argv is exactly a
    plain run's.

    Note: `--setting-sources ""` also drops user-level settings (`env`,
    `apiKeyHelper`, `model`, ...) for stage runs; keychain/OAuth login is
    unaffected (verified on Claude Code 2.1.331). Only the `--settings` file applies.
    """
    if fork and not resume:
        raise ValueError("fork needs a session to resume")
    args = ["-p", "--output-format", "stream-json", "--verbose", "--tools", ",".join(tools), "--strict-mcp-config"]
    if mcp_config_path:
        args += ["--mcp-config", str(mcp_config_path)]
    args += ["--allowedTools", ",".join([t for t in tools if t not in set(unapproved)] + list(mcp_tools))]
    if agent_def:
        args += ["--agent", agent_def]
    if system_prompt:
        args += ["--append-system-prompt", system_prompt]
    if resume:
        args += ["--resume", resume]
    if settings_path:
        args += ["--settings", str(settings_path)]
    if setting_sources is not None:
        args += ["--setting-sources", setting_sources]
    if permission_mode:
        args += ["--permission-mode", permission_mode]
    if permission_tool:
        args += ["--permission-prompt-tool", permission_tool]
    if fork:
        args += ["--fork-session"]
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


def _private_dir(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(directory, 0o700)  # mkdir's mode is ignored when it already exists
    except OSError:
        pass
    return directory


def _write_private(file, data):
    """Create (or truncate) `file` as 0600 from the start: never readable by others, even briefly."""
    fd = os.open(file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf8") as out:
        out.write(json.dumps(data, indent=2))
    try:
        os.chmod(file, 0o600)  # a pre-existing file keeps its old mode through O_CREAT
    except OSError:
        pass
    return file


def write_mcp_config(directory, run_id, agents, db_file, shared=None, gate=False, repo_root=None, read_only=False, write_tools=None):
    """
    Write the per-run MCP config: one ei-memory instance per participating
    agent, each pinned to that agent's identity and this run's id, plus the
    shared knowledge base when given, plus the ei-gate server (pinned to this
    run's id) when `gate` is set. `read_only` starts each memory server without
    its write tools; `write_tools` (bare names) keeps only those write tools.
    """
    directory = _private_dir(directory)
    servers = {}
    if shared:
        servers[SHARED_SERVER] = shared
    if read_only or write_tools is not None and not list(write_tools):
        limit = ["--read-only"]
    elif write_tools is not None:
        limit = ["--write-tools", ",".join(write_tools)]
    else:
        limit = []
    for agent in agents:
        servers[server_name(agent)] = {
            "command": python_for_children(),
            "args": [str(MEMORY_SERVER), "--agent", agent, "--db", str(db_file), *limit],
            "env": {"EI_RUN_ID": run_id},
        }
    if gate:
        if repo_root is None:
            raise ValueError("the gate server needs the repo root")
        servers[GATE_SERVER] = {
            "command": python_for_children(),
            "args": [str(GATE_SERVER_PY), "--db", str(db_file), "--repo-root", str(repo_root)],
            "env": {"EI_RUN_ID": run_id},
        }
    return _write_private(directory / f"{run_id}.json", {"mcpServers": servers})


def write_gate_settings(directory, run_id, db_file, repo_root):
    """Write the per-run `--settings` file that installs the gate's PreToolUse hook (0600)."""
    directory = _private_dir(directory)
    settings = hook_settings(python_for_children(), str(GATE_SERVER_PY), str(db_file), str(repo_root))
    return _write_private(directory / f"{run_id}.settings.json", settings)
