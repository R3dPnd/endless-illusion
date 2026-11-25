"""R1: the engagement gate end to end, through the real seams.

HTTP (create a lab engagement, start stages, approve the plan, decide actions) -> the hub's Runner
spawning (fake) claude with the real `--settings` file -> that file's exact hook command run through
/bin/sh with PreToolUse stdin -> the hub's database -> the operator's decision -> the hook's answer.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from hub.db.pipeline import add_stage, set_stage_status
from hub.db.write import insert_agent_row
from hub.gate_service import record_declaration

from .conftest import start_hub

SCOPE = "127.0.0.1:3000"
PLAN = {"stages": {"web": {"include": True, "targets": [SCOPE], "focus": "product search"}}, "research": []}


@pytest.fixture
def e2e(tmp_path, monkeypatch):
    hold = tmp_path / "hold"
    hold.write_text("", encoding="utf8")
    monkeypatch.setenv("FAKE_HOLD_FILE", str(hold))  # fake claude keeps every run alive until the test ends
    monkeypatch.delenv("EI_RUN_ID", raising=False)
    hub, server, client = start_hub(tmp_path)
    yield hub, client, tmp_path, monkeypatch
    hold.unlink(missing_ok=True)
    hub.runner.stop_all()
    server.shutdown()


def wait_for(fn, timeout=15, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def start(client, monkeypatch, tmp_path, eid, stage, armed):
    """Start a stage over HTTP; returns (response, argv fake claude was spawned with)."""
    argv_file = tmp_path / f"argv-{stage}.json"
    monkeypatch.setenv("FAKE_ARGV_FILE", str(argv_file))
    status, body = client.post(f"/api/engagements/{eid}/stages/{stage}/start", {"armed": armed})
    assert status == 200, body
    assert body["armed"] is armed
    argv = wait_for(lambda: argv_file.exists() and argv_file.read_text(encoding="utf8") and json.loads(argv_file.read_text(encoding="utf8")),
                    what=f"{stage} spawn")
    return body, argv


def hook_command(argv):
    settings = json.loads(Path(argv[argv.index("--settings") + 1]).read_text(encoding="utf8"))
    (entry,) = settings["hooks"]["PreToolUse"]
    (hook,) = entry["hooks"]
    return hook["command"]


def run_hook_async(command, run_id, payload):
    """Run the exact hook command through /bin/sh, as Claude Code does; returns (thread, result holder)."""
    result = {}
    env = {**{k: v for k, v in os.environ.items() if k != "EI_RUN_ID"}, "EI_RUN_ID": run_id}

    def go():
        result["proc"] = subprocess.run(["/bin/sh", "-c", command], input=json.dumps(payload), capture_output=True, text=True,
                                        env=env, timeout=60)

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, result


def decision(result):
    proc = result["proc"]
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def pending_for(client, run_id):
    status, body = client.get("/api/gate/pending")
    assert status == 200
    return [a for a in body["items"] if a["run_id"] == run_id]


def test_gate_end_to_end(e2e):
    hub, client, tmp_path, monkeypatch = e2e

    # 1. A lab engagement scoped to 127.0.0.1:3000 only (R12).
    status, eng = client.post("/api/engagements", {"name": "E2E Juice", "kind": "lab", "scopeHosts": [SCOPE], "scopeNotes": "",
                                                   "authorization": "operator-owned local lab"})
    assert status == 200, eng
    eid = eng["id"]

    # Discovery, UNARMED: passive tools only, still behind the gate hook.
    disco, disco_argv = start(client, monkeypatch, tmp_path, eid, "discovery", False)
    assert "Bash" not in disco_argv[disco_argv.index("--tools") + 1].split(",")
    assert "--settings" in disco_argv

    # A plan: Dann's memory row (from a planning stage run of this engagement), approved over HTTP.
    set_stage_status(hub.db, add_stage(hub.db, eid, "planning", "e2e-planning-run", False), "done")
    draft = insert_agent_row(hub.db, "dann-of-thursday", "e2e-planning-run", "plan_drafts", {"engagement_id": eid, "plan": PLAN})
    status, body = client.post(f"/api/engagements/{eid}/plan/approve", {"draftId": draft["id"]})
    assert status == 200, body

    # Web, ARMED: Bash is in the toolset but never pre-approved.
    web, web_argv = start(client, monkeypatch, tmp_path, eid, "web", True)
    run_id = web["runId"]
    assert "Bash" in web_argv[web_argv.index("--tools") + 1].split(",")
    assert "Bash" not in web_argv[web_argv.index("--allowedTools") + 1].split(",")

    # 2. The exact hook command from the run's --settings file.
    command = hook_command(web_argv)

    # 3./4. An in-scope curl: declared, pending for the operator, approved over HTTP -> the hook allows.
    curl = "curl -s http://127.0.0.1:3000/rest/products"
    record_declaration(hub.db, run_id, curl, "list products", "WSTG-INFO-06 endpoint enumeration", "read-only GET")
    t, result = run_hook_async(command, run_id, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": curl}})
    (action,) = wait_for(lambda: pending_for(client, run_id), what="pending curl")
    assert action["verdict"] == "in" and action["target"] == curl
    status, body = client.post(f"/api/gate/actions/{action['id']}/decide", {"approve": True})
    assert status == 200, body
    t.join(30)
    assert decision(result) == "allow"

    # 5. WebFetch to localhost:3000, an alias of the scope (R14): pending as unknown; approving without scopeAck is a 409.
    url = "http://localhost:3000/"
    record_declaration(hub.db, run_id, url, "check the landing page", "WSTG-INFO-02 fingerprinting", "read-only GET")
    t, result = run_hook_async(command, run_id, {"hook_event_name": "PreToolUse", "tool_name": "WebFetch",
                                                 "tool_input": {"url": url, "prompt": "what is this"}})
    (action,) = wait_for(lambda: pending_for(client, run_id), what="pending WebFetch")
    assert action["verdict"] == "unknown" and action["tool_name"] == "WebFetch"
    status, body = client.post(f"/api/gate/actions/{action['id']}/decide", {"approve": True})
    assert status == 409, body
    assert pending_for(client, run_id)  # still waiting on the operator
    status, body = client.post(f"/api/gate/actions/{action['id']}/decide", {"approve": False, "message": "use 127.0.0.1"})
    assert status == 200, body
    t.join(30)
    assert decision(result) == "deny"

    # Discovery's run was never involved.
    assert pending_for(client, disco["runId"]) == []
