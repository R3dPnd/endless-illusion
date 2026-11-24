"""Stage runs (runs belonging to an engagement stage) go through the ei-gate; plain runs don't."""

import json
import os
import stat
import time
from pathlib import Path

import pytest

from hub import HUB_DIR
from hub.db import now_iso, open_db
from hub.db.archive import get_run
from hub.db.pipeline import add_stage, create_engagement
from hub.gate import hook_settings
from hub.session import build_session_args, python_for_children
from hub.tool_names import DECLARE_TOOL, PERMISSION_TOOL, SHARED_READ_TOOLS, qualified_tools_for

from .conftest import start_hub

GATED = {"Bash", "WebFetch", "Write", "Edit", "MultiEdit", "NotebookEdit"}
STAGE_TOOLS = ["Read", "Grep", "Bash", "WebFetch", "Write", "Edit"]


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    hub, server, client = start_hub(tmp_path_factory.mktemp("stage"))
    yield hub, client
    hub.runner.stop_all()
    server.shutdown()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    files = {k: tmp_path / f"{k}.json" for k in ("argv", "env")}
    monkeypatch.setenv("FAKE_ARGV_FILE", str(files["argv"]))
    monkeypatch.setenv("FAKE_ENV_FILE", str(files["env"]))
    monkeypatch.delenv("EI_RUN_ID", raising=False)
    return files


def wait(hub, run_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_run(hub.db, run_id)["status"] != "running" and hub.runner.get(run_id).finished:
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def new_stage(hub, stage="web"):
    eng = create_engagement(hub.db, f"Lab {time.time_ns()}", "lab", ["10.0.0.5"], "", "owner's written permission")
    return eng["id"], add_stage(hub.db, eng["id"], stage, None, True)


def start_stage(hub, tools=STAGE_TOOLS, agents=("diablo-of-monday",), stage="web"):
    eid, sid = new_stage(hub, stage)
    run = hub.runner.start(
        {"agent": "diablo-of-monday", "task": "test the app", "scope": "10.0.0.5", "authorization": "lab"},
        stage={"engagementId": eid, "stageId": sid, "stage": stage, "armed": True, "tools": list(tools), "mcpAgents": list(agents)},
    )
    return run, sid


def argv_of(fake):
    return json.loads(fake["argv"].read_text(encoding="utf8"))


def at(argv, flag):
    return argv[argv.index(flag) + 1]


def stage_row(hub, sid):
    return hub.db.get("SELECT * FROM ops_stages WHERE id = ?", sid)


# ---- argv ----


def test_stage_run_args_include_gate(api, fake):
    hub, _ = api
    run, _ = start_stage(hub)
    wait(hub, run.id)
    argv = argv_of(fake)
    assert at(argv, "--permission-prompt-tool") == PERMISSION_TOOL
    allowed = at(argv, "--allowedTools").split(",")
    assert not GATED & set(allowed)
    assert DECLARE_TOOL in allowed
    assert at(argv, "--tools").split(",") == STAGE_TOOLS  # gated tools still available, just not pre-approved
    servers = json.loads(Path(at(argv, "--mcp-config")).read_text(encoding="utf8"))["mcpServers"]
    gate = servers["ei-gate"]
    assert gate["command"] == python_for_children()
    assert gate["args"] == [str(HUB_DIR / "gate.py"), "--db", str(hub.db_file), "--repo-root", str(hub.repo_root)]
    assert gate["env"] == {"EI_RUN_ID": run.id}


def test_stage_run_has_no_foreign_mcp_tools(api, fake):
    hub, _ = api
    run, _ = start_stage(hub, tools=["Read", "WebFetch"], agents=["diablo-of-monday", "sen-of-saturday"])
    wait(hub, run.id)
    argv = argv_of(fake)
    assert "--strict-mcp-config" in argv
    assert at(argv, "--tools") == "Read,WebFetch"
    servers = json.loads(Path(at(argv, "--mcp-config")).read_text(encoding="utf8"))["mcpServers"]
    expected = {"ei-diablo", "ei-sen", "ei-gate"} | ({"pnd-notes"} if "pnd-notes" in servers else set())
    assert set(servers) == expected
    allowed = at(argv, "--allowedTools").split(",")
    assert not any("*" in t for t in allowed)
    assert set(allowed) == {"Read", DECLARE_TOOL, *qualified_tools_for("diablo-of-monday"), *qualified_tools_for("sen-of-saturday"),
                            *(SHARED_READ_TOOLS if "pnd-notes" in servers else [])}


def test_stage_run_settings_file_has_hook(api, fake):
    hub, _ = api
    run, _ = start_stage(hub)
    wait(hub, run.id)
    argv = argv_of(fake)
    settings = Path(at(argv, "--settings"))
    assert settings.parent == Path(at(argv, "--mcp-config")).parent
    assert json.loads(settings.read_text(encoding="utf8")) == hook_settings(
        python_for_children(), str(HUB_DIR / "gate.py"), str(hub.db_file), str(hub.repo_root))
    if os.name != "nt":
        assert stat.S_IMODE(settings.stat().st_mode) == 0o600


def test_stage_run_env_has_run_id(api, fake):
    hub, _ = api
    run, _ = start_stage(hub)
    wait(hub, run.id)
    assert json.loads(fake["env"].read_text(encoding="utf8"))["EI_RUN_ID"] == run.id


def test_stage_run_pins_permission_mode(api, fake):
    hub, _ = api
    run, _ = start_stage(hub)
    wait(hub, run.id)
    argv = argv_of(fake)
    assert at(argv, "--permission-mode") == "default"
    assert at(argv, "--setting-sources") == ""  # no project/local settings can override the gate hook
    assert "--fork-session" not in argv


def test_plain_console_run_unchanged(api, fake):
    """Byte-for-byte the argv a plain direct run produced before stage runs existed."""
    hub, client = api
    status, body = client.post("/api/runs", {"agent": "sin-of-friday", "task": "x"})
    assert status == 200
    wait(hub, body["id"])
    argv = argv_of(fake)
    shared = "pnd-notes" in json.loads(Path(at(argv, "--mcp-config")).read_text(encoding="utf8"))["mcpServers"]
    allowed = ["Read", "Grep", "Glob", "WebSearch", "WebFetch", *qualified_tools_for("sin-of-friday"), *(SHARED_READ_TOOLS if shared else [])]
    assert argv == [
        "-p", "--output-format", "stream-json", "--verbose", "--tools", "Read,Grep,Glob,WebSearch,WebFetch", "--strict-mcp-config",
        "--mcp-config", str(hub.data_dir / "run-configs" / f"{body['id']}.json"),
        "--allowedTools", ",".join(allowed),
        "--append-system-prompt", at(argv, "--append-system-prompt"),
    ]
    assert "ei-gate" not in json.loads(Path(at(argv, "--mcp-config")).read_text(encoding="utf8"))["mcpServers"]
    assert json.loads(fake["env"].read_text(encoding="utf8"))["EI_RUN_ID"] is None
    assert not (hub.data_dir / "run-configs" / f"{body['id']}.settings.json").exists()


def test_build_session_args_defaults_and_fork():
    base = build_session_args(["Read"], mcp_tools=["x"], resume="s1")
    assert base == ["-p", "--output-format", "stream-json", "--verbose", "--tools", "Read", "--strict-mcp-config",
                    "--allowedTools", "Read,x", "--resume", "s1"]
    forked = build_session_args(["Read"], resume="s1", fork=True)
    assert forked[-3:] == ["--resume", "s1", "--fork-session"]
    with pytest.raises(ValueError):
        build_session_args(["Read"], fork=True)


# ---- lifecycle ----


def test_stage_status_mirrors_run(api, fake, monkeypatch):
    hub, _ = api
    run, sid = start_stage(hub)
    assert stage_row(hub, sid)["run_id"] == run.id
    wait(hub, run.id)
    assert stage_row(hub, sid)["status"] == "done"
    assert stage_row(hub, sid)["finished_at"]

    monkeypatch.setenv("FAKE_EXIT", "3")
    run, sid = start_stage(hub)
    wait(hub, run.id)
    assert run.status == "error"
    assert stage_row(hub, sid)["status"] == "failed"


def test_stop_cancels_pending_action(api, fake, tmp_path, monkeypatch):
    hub, _ = api
    hold = tmp_path / "hold"
    hold.write_text("", encoding="utf8")
    monkeypatch.setenv("FAKE_HOLD_FILE", str(hold))
    run, sid = start_stage(hub)
    assert stage_row(hub, sid)["status"] == "running"
    aid, _ = hub.db.run(
        "INSERT INTO gate_actions (run_id, tool_name, verdict, status, created_at) VALUES (?, 'Bash', 'in', 'pending', ?)", run.id, now_iso())
    hub.runner.stop(run.id)
    wait(hub, run.id)
    assert hub.db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "cancelled"
    assert stage_row(hub, sid)["status"] == "stopped"


def test_startup_expires_orphaned_pending(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = open_db(data / "endless-illusion.db")
    aid, _ = db.run("INSERT INTO gate_actions (run_id, tool_name, verdict, status, created_at) VALUES ('gone', 'Bash', 'in', 'pending', ?)", now_iso())
    db.close()
    hub, server, _ = start_hub(tmp_path)
    try:
        assert hub.db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "expired"
    finally:
        server.shutdown()
