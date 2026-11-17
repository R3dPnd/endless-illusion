import json
import os
import time

import pytest

from hub.db.archive import add_report, append_event, create_run, finish_run, get_run, get_run_events, list_runs, mark_interrupted
from hub.db.ownership import AGENTS
from hub.report import clean_report

from .conftest import FIXTURES, start_hub

FIXTURE_LINES = len((FIXTURES / "run-events.jsonl").read_text(encoding="utf8").strip().splitlines())


def base_run(**over):
    return {"id": "r1", "agent": "dahlia-of-wednesday", "task": "t", "scope": "", "authorization": "",
            "activeEngaged": False, "tools": ["Read"], **over}


def test_records_a_run_with_events_and_reports(db):
    create_run(db, base_run())
    append_event(db, "r1", 0, {"kind": "meta", "ts": 1})
    append_event(db, "r1", 1, {"kind": "closed", "ts": 2})
    add_report(db, "r1", "dahlia-of-wednesday", "final", "done", {"cost": 1})
    finish_run(db, "r1", "done", 0.5, 1000)
    run = get_run(db, "r1")
    assert (run["status"], run["cost_usd"], run["tools"]) == ("done", 0.5, ["Read"])
    assert [e["kind"] for e in get_run_events(db, "r1")] == ["meta", "closed"]
    assert [r["id"] for r in list_runs(db)] == ["r1"]


def test_redacts_secrets_in_events_without_corrupting_them(db):
    create_run(db, base_run(id="r3"))
    cmd = 'curl -d "password=hunter2" -H "Authorization: Bearer abc.def"'
    append_event(db, "r3", 0, {"kind": "claude", "ts": 1, "data": {"type": "assistant", "message": {
        "content": [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}})
    (evt,) = get_run_events(db, "r3")
    stored = evt["data"]["message"]["content"][0]["input"]["command"]
    assert "hunter2" not in stored
    assert "abc.def" not in stored
    assert '-H "Authorization: Bearer [REDACTED]"' in stored


def test_marks_runs_left_running_as_interrupted_and_keeps_their_events(db):
    create_run(db, base_run(id="r2"))
    append_event(db, "r2", 0, {"kind": "meta", "ts": 1})
    assert mark_interrupted(db) == 1
    assert get_run(db, "r2")["status"] == "interrupted"
    assert len(get_run_events(db, "r2")) == 1


def test_filters_runs_by_agent_and_text(db):
    create_run(db, base_run(id="a", task="nginx review"))
    create_run(db, base_run(id="b", agent="sin-of-friday", task="log4j analysis"))
    assert [r["id"] for r in list_runs(db, agent="sin-of-friday")] == ["b"]
    assert [r["id"] for r in list_runs(db, q="nginx")] == ["a"]


def test_clean_report_strips_the_handback_frame_and_keeps_stats():
    raw = ("[Subagent hand-back] preamble. The report follows:\n  Line one\n  Line two\n"
           "agentId: x1 (use SendMessage with to: 'x1' to continue)\n<usage>tool_uses: 4\nduration_ms: 65000</usage>")
    assert clean_report(raw) == ("Line one\nLine two", "4 tool uses · 1m 5s")


# ---- end to end: a fake claude replays a recorded stream ----


@pytest.fixture(scope="module")
def hub(tmp_path_factory):
    work = tmp_path_factory.mktemp("hub")
    os.environ["FAKE_ARGV_FILE"] = str(work / "argv.json")
    hub, server, client = start_hub(work)
    yield hub, client, work / "argv.json"
    server.shutdown()
    os.environ.pop("FAKE_ARGV_FILE", None)


def run_to_completion(hub, client, body):
    status, res = client.post("/api/runs", body)
    assert status == 200, res
    for _ in range(200):
        if get_run(hub.db, res["id"])["status"] != "running":
            break
        time.sleep(0.05)
    return res["id"]


def test_stores_the_run_its_events_and_its_reports(hub):
    h, client, _ = hub
    run_id = run_to_completion(h, client, {"agent": "dann-of-thursday", "task": "Summarize Log4Shell"})
    run = get_run(h.db, run_id)
    assert run["status"] == "done"
    assert run["cost_usd"] == pytest.approx(0.0123)
    assert len(get_run_events(h.db, run_id)) == FIXTURE_LINES + 2  # + meta + closed
    reports = h.db.all("SELECT agent, kind, text, meta FROM reports WHERE run_id = ? ORDER BY id", run_id)
    assert [(r["agent"], r["kind"]) for r in reports] == [("dahlia-of-wednesday", "subagent_report"), ("dann-of-thursday", "final")]
    assert reports[0]["text"] == "CVE-2021-44228 is a JNDI lookup RCE in Log4j 2.0-beta9 to 2.14.1.\nFixed in 2.17.1."
    assert json.loads(reports[0]["meta"])["stats"] == "4 tool uses · 1m 5s"


def test_stores_the_subagent_handback_message_as_the_report(hub):
    h, client, _ = hub
    os.environ["FAKE_FIXTURE"] = "run-events-handback.jsonl"
    try:
        run_id = run_to_completion(h, client, {"agent": "dann-of-thursday", "task": "Check prior work"})
    finally:
        os.environ.pop("FAKE_FIXTURE", None)
    sub = h.db.all("SELECT agent, text, meta FROM reports WHERE run_id = ? AND kind = 'subagent_report'", run_id)
    assert len(sub) == 1
    assert sub[0]["agent"] == "dahlia-of-wednesday"
    assert sub[0]["text"] == "One stored note: CVE-2021-44228, CVSS 10.0, KEV since 2021-12-10."
    assert json.loads(sub[0]["meta"])["stats"] == "4 tool uses · 21s"


def test_launches_orchestrated_runs_restricted_as_dann_with_every_memory_server(hub):
    h, client, argv_file = hub
    run_id = run_to_completion(h, client, {"agent": "dann-of-thursday", "task": "x"})
    argv = json.loads(argv_file.read_text(encoding="utf8"))

    def at(flag):
        return argv[argv.index(flag) + 1]

    assert at("--agent") == "dann-of-thursday"
    assert "--strict-mcp-config" in argv
    assert "Bash" not in at("--tools")
    assert "mcp__pnd-notes__search_notes" in at("--allowedTools")
    assert "Rules of Engagement" in at("--append-system-prompt")
    config = json.loads(open(at("--mcp-config"), encoding="utf8").read())
    assert sorted(config["mcpServers"]) == sorted([f"ei-{a.split('-')[0]}" for a in AGENTS] + ["pnd-notes"])
    assert config["mcpServers"]["ei-dahlia"]["env"]["EI_RUN_ID"] == run_id
    assert "dahlia-of-wednesday" in config["mcpServers"]["ei-dahlia"]["args"]


def test_gives_a_direct_run_only_its_own_memory_server(hub):
    h, client, argv_file = hub
    run_to_completion(h, client, {"agent": "sin-of-friday", "task": "x"})
    argv = json.loads(argv_file.read_text(encoding="utf8"))
    assert "--agent" not in argv
    config = json.loads(open(argv[argv.index("--mcp-config") + 1], encoding="utf8").read())
    assert sorted(config["mcpServers"]) == ["ei-sin", "pnd-notes"]
    assert "mcp__ei-sin__save_exploit_analysis" in argv[argv.index("--allowedTools") + 1]


def test_streams_a_live_run_over_server_sent_events(hub):
    h, client, _ = hub
    status, res = client.post("/api/runs", {"agent": "sin-of-friday", "task": "stream me"})
    assert status == 200
    status, headers, text = client.request("GET", f"/api/runs/{res['id']}/events")
    assert status == 200
    assert '"kind":"meta"' in text
    assert '"kind":"closed"' in text
    assert text.rstrip().endswith("event: done\ndata: {}")
