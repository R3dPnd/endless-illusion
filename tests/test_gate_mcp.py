"""The ei-gate server (MCP stdio mode) and its PreToolUse hook mode, driven as Claude Code drives them."""

import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time

import pytest

from hub import HUB_DIR
from hub.db import open_db
from hub.db.pipeline import add_stage, create_engagement
from hub.gate_service import DECLARE_FIRST, decide, pending_actions
from hub.tool_names import DECLARE_TOOL, GATE_SERVER, PERMISSION_TOOL

GATE = HUB_DIR / "gate.py"
SCOPE = ["localhost:3000", "127.0.0.1:3000"]
IN_CMD = "curl -s http://localhost:3000/a"
RUN = "run-gate"


@pytest.fixture
def env(tmp_path):
    """A file DB with one lab engagement whose web stage is run RUN."""
    db_file = tmp_path / "ei.db"
    db = open_db(db_file)
    e = create_engagement(db, "Juice Lab", "lab", SCOPE, "", "my own lab")
    add_stage(db, e["id"], "web", RUN, True)
    yield db, db_file, tmp_path
    db.close()


class GateClient:
    def __init__(self, db_file, repo_root, run_id=RUN):
        environ = {k: v for k, v in os.environ.items() if k != "EI_RUN_ID"}
        if run_id is not None:
            environ["EI_RUN_ID"] = run_id
        self.proc = subprocess.Popen(
            [sys.executable, str(GATE), "--db", str(db_file), "--repo-root", str(repo_root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environ,
        )
        self.next_id = 0
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
        assert init["result"]["serverInfo"]["name"] == GATE_SERVER
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, message):
        self.proc.stdin.write(json.dumps(message).encode() + b"\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        response = json.loads(self.proc.stdout.readline())
        assert response["id"] == self.next_id
        return response

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


@pytest.fixture
def client(env):
    _, db_file, root = env
    c = GateClient(db_file, root)
    yield c
    c.close()


def text(response):
    return "\n".join(c["text"] for c in response["result"]["content"])


def permission(client, command, tool="Bash"):
    res = client.call("permission", {"tool_name": tool, "input": {"command": command}, "tool_use_id": "toolu_1"})
    assert not res["result"].get("isError")
    return json.loads(text(res))


def approve_when_pending(db, run_id=RUN, **kw):
    errors = []

    def go():
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            mine = [a for a in pending_actions(db) if a["run_id"] == run_id]
            if mine:
                try:
                    decide(db, mine[0]["id"], True, **kw)
                except Exception as err:
                    errors.append(err)
                return
            time.sleep(0.02)
        errors.append(TimeoutError("no pending action"))

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, errors


def test_constants():
    assert GATE_SERVER == "ei-gate"
    assert PERMISSION_TOOL == "mcp__ei-gate__permission"
    assert DECLARE_TOOL == "mcp__ei-gate__declare_action"
    from hub.gate import SERVER_NAME
    assert SERVER_NAME == GATE_SERVER


def test_lists_two_tools(client):
    tools = client.request("tools/list")["result"]["tools"]
    assert sorted(t["name"] for t in tools) == ["declare_action", "permission"]
    declare = next(t for t in tools if t["name"] == "declare_action")
    assert sorted(declare["inputSchema"]["required"]) == ["risk", "target", "technique", "why"]


def test_declare_then_permission_pending_then_approve(env, client):
    db, _, _ = env
    res = client.call("declare_action", {"target": IN_CMD, "why": "check login", "technique": "GET", "risk": "read-only"})
    assert text(res).startswith("declared #")
    t, errors = approve_when_pending(db)
    reply = permission(client, IN_CMD)
    t.join(5)
    assert not errors
    assert reply == {"behavior": "allow"}
    assert db.get("SELECT status FROM gate_actions ORDER BY id DESC LIMIT 1")["status"] == "approved"


def test_permission_without_declaration_denies(client):
    reply = permission(client, IN_CMD)
    assert reply == {"behavior": "deny", "message": DECLARE_FIRST}


def test_permission_malformed_args_deny(client):
    malformed = [
        {},
        {"input": {"command": "echo hi > x"}},
        {"tool_name": 5, "input": {}},
        {"tool_name": None, "input": {}},
        {"tool_name": "Bash"},
        {"tool_name": "Bash", "input": "echo hi > x"},
        {"tool_name": "Bash", "input": ["echo"]},
        {"tool_name": "Bash", "input": None, "tool_use_id": "t"},
    ]
    for args in malformed:
        res = client.call("permission", args)
        assert not res["result"].get("isError"), args
        assert json.loads(text(res)) == {"behavior": "deny", "message": "malformed permission request"}, args
    # extra fields from a newer Claude Code are tolerated, not refused
    res = client.call("permission", {"tool_name": "Bash", "input": {"command": "echo hi > x"}, "tool_use_id": "t", "new": 1})
    assert json.loads(text(res))["behavior"] == "deny" and not res["result"].get("isError")


def test_permission_without_context_denies(env):
    _, db_file, root = env
    for run_id in ("no-such-run", None):
        c = GateClient(db_file, root, run_id=run_id)
        try:
            reply = permission(c, "echo hi > hi.txt")
            assert reply["behavior"] == "deny"
            assert reply["message"]
        finally:
            c.close()


def test_declare_action_rejects_empty_fields(client):
    good = {"target": IN_CMD, "why": "w", "technique": "t", "risk": "r"}
    for key in good:
        for bad in ("", "   "):
            res = client.call("declare_action", {**good, key: bad})
            assert res["result"].get("isError") is True, (key, bad)
        missing = {k: v for k, v in good.items() if k != key}
        assert client.call("declare_action", missing)["result"].get("isError") is True


def test_memory_server_unchanged():
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", str(HUB_DIR.parent / "tests" / "test_mcp.py")], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-2000:]


# ---- hook mode ---------------------------------------------------------------------------------

def hook_input(command, tool="Bash"):
    return json.dumps({
        "session_id": "s", "transcript_path": "/x", "cwd": "/", "permission_mode": "default",
        "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}, "tool_use_id": "toolu_1",
    })


def run_hook(db_file, root, stdin, run_id=RUN, cmd=None, timeout=30):
    environ = {k: v for k, v in os.environ.items() if k != "EI_RUN_ID"}
    if run_id is not None:
        environ["EI_RUN_ID"] = run_id
    if cmd is None:
        args = [sys.executable, str(GATE), "--hook", "--db", str(db_file), "--repo-root", str(root)]
        return subprocess.run(args, input=stdin, capture_output=True, text=True, env=environ, timeout=timeout)
    return subprocess.run(cmd, shell=True, input=stdin, capture_output=True, text=True, env=environ, timeout=timeout)


def decision(res):
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert isinstance(spec["permissionDecisionReason"], str)
    return spec["permissionDecision"], spec["permissionDecisionReason"]


def declare_in_db(db, target=IN_CMD):
    from hub.gate_service import record_declaration
    return record_declaration(db, RUN, target, "check login", "GET", "read-only")


def test_hook_allows_after_approval(env):
    db, db_file, root = env
    declare_in_db(db)
    t, errors = approve_when_pending(db, message="go ahead")
    res = run_hook(db_file, root, hook_input(IN_CMD))
    t.join(5)
    assert not errors
    assert decision(res) == ("allow", "go ahead")


def test_hook_denies_without_declaration(env):
    _, db_file, root = env
    assert decision(run_hook(db_file, root, hook_input(IN_CMD))) == ("deny", DECLARE_FIRST)


def test_hook_denies_garbage_stdin(env):
    _, db_file, root = env
    for garbage in ("not json", "", "[1,2]", '{"tool_name": 5}'):
        verdict, reason = decision(run_hook(db_file, root, garbage))
        assert verdict == "deny" and reason, garbage


def test_hook_denies_unknown_run(env):
    _, db_file, root = env
    for run_id in ("no-such-run", None):
        verdict, reason = decision(run_hook(db_file, root, hook_input("echo hi"), run_id=run_id))
        assert verdict == "deny" and reason


def test_hook_denies_unreachable_db(tmp_path):
    bad = tmp_path / "a-directory"  # sqlite cannot open a directory
    bad.mkdir()
    verdict, reason = decision(run_hook(bad, tmp_path, hook_input("echo hi")))
    assert verdict == "deny" and reason


NASTY = ["/py thon", "/a $HOME/gate.py", '/d "b"/`id`.db', "/r'oot; rm -rf x"]


def test_hook_settings_shape():
    from hub.gate import hook_settings

    s = hook_settings(*NASTY)
    assert list(s) == ["hooks"]
    (entry,) = s["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash|WebFetch|Write|Edit|MultiEdit|NotebookEdit"
    (hook,) = entry["hooks"]
    assert hook["type"] == "command" and hook["timeout"] == 86400
    json.dumps(s)
    outer = shlex.split(hook["command"])
    assert outer[:2] == ["/bin/sh", "-c"] and len(outer) == 3
    inner = shlex.split(outer[2])
    py, gate, db_file, root = NASTY
    assert inner[:7] == [py, gate, "--hook", "--db", db_file, "--repo-root", root]
    assert inner[7] == "||"


def test_hook_wrapper_allows_after_approval(env):
    from hub.gate import hook_settings

    db, db_file, root = env
    cmd = hook_settings(sys.executable, str(GATE), str(db_file), str(root))["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    declare_in_db(db)
    t, errors = approve_when_pending(db)
    res = run_hook(db_file, root, hook_input(IN_CMD), cmd=cmd)
    t.join(5)
    assert not errors
    assert decision(res)[0] == "allow"


def test_hook_wrapper_blocks_on_bad_interpreter(env):
    from hub.gate import hook_settings

    _, db_file, root = env
    cmd = hook_settings("/no/such/python", str(GATE), str(db_file), str(root))["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    res = run_hook(db_file, root, hook_input("echo hi"), cmd=cmd)
    assert res.returncode == 2
    assert "(exit 127)" in res.stderr


def test_hook_wrapper_denies_garbage_stdin(env):
    from hub.gate import hook_settings

    _, db_file, root = env
    cmd = hook_settings(sys.executable, str(GATE), str(db_file), str(root))["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert decision(run_hook(db_file, root, "garbage{", cmd=cmd))[0] == "deny"


def test_hook_sigterm_during_wait_expires_pending(env):
    db, db_file, root = env
    declare_in_db(db)
    environ = {**os.environ, "EI_RUN_ID": RUN}
    proc = subprocess.Popen(
        [sys.executable, str(GATE), "--hook", "--db", str(db_file), "--repo-root", str(root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environ,
    )
    proc.stdin.write(hook_input(IN_CMD))
    proc.stdin.close()
    deadline = time.monotonic() + 15
    while not [a for a in pending_actions(db) if a["run_id"] == RUN]:
        assert time.monotonic() < deadline, "no pending action"
        time.sleep(0.02)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)
    out, err = proc.stdout.read(), proc.stderr.read()
    assert proc.returncode == 0, err
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["permissionDecision"] == "deny"
    assert "GateSignal" in spec["permissionDecisionReason"]
    statuses = [r["status"] for r in db.all("SELECT status FROM gate_actions WHERE run_id = ? ORDER BY id", RUN)]
    assert "pending" not in statuses and "expired" in statuses
