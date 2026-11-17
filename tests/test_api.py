from datetime import datetime, timedelta, timezone

import pytest

from hub.db.archive import append_event, create_run, finish_run
from hub.db.write import insert_agent_row

from .conftest import ORIGIN, start_hub


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    hub, server, client = start_hub(tmp_path_factory.mktemp("api"))
    yield hub, client
    server.shutdown()


def lead(hub, name, url, agent="saudade-of-sunday"):
    return insert_agent_row(hub.db, agent, "seed", "program_leads", {"name": name, "url": url, "found_via": "security.txt", "scope_summary": "unverified"})


def tracked_program(hub, client, name, url):
    lead(hub, name, url)
    status, body = client.post("/api/leads/track", {"normalizedUrl": url.replace("https://", "")})
    assert status == 200
    return body["programId"]


def propose(hub, program_id, asset="app.example.com"):
    return insert_agent_row(hub.db, "sen-of-saturday", "seed", "scope_proposals", {
        "program_id": program_id, "in_scope": [{"asset": asset, "type": "domain"}], "out_of_scope": [], "exclusions": ["no DoS"]})["id"]


# ---- cross-site guard ----


def test_rejects_non_json_posts(api):
    _, client = api
    status, _, _ = client.request("POST", "/api/runs", b"{}", {"Content-Type": "text/plain", "Origin": ORIGIN})
    assert status == 415


def test_rejects_posts_from_another_origin(api):
    _, client = api
    status, _ = client.post("/api/proposals/1/confirm", {}, {"Origin": "https://evil.example"})
    assert status == 403


def test_rejects_a_non_object_body(api):
    _, client = api
    status, _ = client.post("/api/programs", ["not", "an", "object"])
    assert status == 400


# ---- bounty pipeline ----


def test_moves_a_lead_to_tracked(api):
    hub, client = api
    lead(hub, "Alpha", "https://hackerone.com/alpha")
    lead(hub, "Alpha", "https://www.hackerone.com/alpha/", "dahlia-of-wednesday")
    b = client.get("/api/bounties")[1]
    entry = next(x for x in b["leads"] if x["normalizedUrl"] == "hackerone.com/alpha")
    assert entry["sightings"] == 2
    assert sorted(entry["agents"]) == ["dahlia-of-wednesday", "saudade-of-sunday"]
    assert client.post("/api/leads/track", {"normalizedUrl": "hackerone.com/alpha"})[0] == 200
    b = client.get("/api/bounties")[1]
    assert not any(x["normalizedUrl"] == "hackerone.com/alpha" for x in b["leads"])
    assert any(p["name"] == "Alpha" for p in b["tracked"])


def test_hides_a_dismissed_lead(api):
    hub, client = api
    lead(hub, "Beta", "https://bugcrowd.com/beta")
    assert client.post("/api/leads/dismiss", {"normalizedUrl": "bugcrowd.com/beta"}) == (200, {"ok": True})
    b = client.get("/api/bounties")[1]
    assert not any(x["normalizedUrl"] == "bugcrowd.com/beta" for x in b["leads"])
    assert not any(p["name"] == "Beta" for p in b["tracked"])


def test_adds_a_program_manually(api):
    _, client = api
    assert client.post("/api/programs", {"name": "Gamma", "url": "https://intigriti.com/gamma", "policyText": "Scope: *.gamma.io"})[0] == 200
    assert client.post("/api/programs", {"name": "Gamma again", "url": "https://www.intigriti.com/gamma/"})[0] == 409


def test_confirms_a_proposal_into_a_snapshot_exactly_once(api):
    hub, client = api
    pid = tracked_program(hub, client, "Delta", "https://hackerone.com/delta")
    prop = propose(hub, pid)
    b = client.get("/api/bounties")[1]
    assert [p["id"] for p in next(p for p in b["tracked"] if p["id"] == pid)["proposals"]] == [prop]
    assert client.post(f"/api/proposals/{prop}/confirm")[0] == 200
    assert client.post(f"/api/proposals/{prop}/confirm")[0] == 409
    c = next(p for p in client.get("/api/bounties")[1]["confirmed"] if p["id"] == pid)
    assert c["snapshot"]["inScope"][0]["asset"] == "app.example.com"
    assert c["snapshot"]["stale"] is False


def test_creates_no_snapshot_for_a_rejected_proposal(api):
    hub, client = api
    pid = tracked_program(hub, client, "Epsilon", "https://hackerone.com/epsilon")
    prop = propose(hub, pid)
    assert client.post(f"/api/proposals/{prop}/reject")[0] == 200
    assert hub.db.get("SELECT count(*) n FROM scope_snapshots WHERE program_id = ?", pid)["n"] == 0


def test_rejects_a_bad_proposal_id(api):
    _, client = api
    assert client.post("/api/proposals/abc/confirm")[0] == 400


def test_flags_scope_confirmed_more_than_30_days_ago_as_stale(api):
    hub, client = api
    pid = tracked_program(hub, client, "Zeta", "https://hackerone.com/zeta")
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    hub.db.run("INSERT INTO scope_snapshots(program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?, '[]', '[]', '[]', ?)", pid, old)
    c = next(p for p in client.get("/api/bounties")[1]["confirmed"] if p["id"] == pid)
    assert c["snapshot"]["stale"] is True


# ---- runs linked to programs ----


def test_refuses_a_program_without_confirmed_scope(api):
    hub, client = api
    pid = tracked_program(hub, client, "Eta", "https://hackerone.com/eta")
    assert client.post("/api/runs", {"agent": "sin-of-friday", "task": "x", "programId": pid})[0] == 400


def test_records_the_snapshot_a_run_was_authorized_under(api):
    hub, client = api
    pid = tracked_program(hub, client, "Theta", "https://hackerone.com/theta")
    snap = client.post(f"/api/proposals/{propose(hub, pid)}/confirm")[1]["snapshotId"]
    status, body = client.post("/api/runs", {"agent": "sin-of-friday", "task": "x", "programId": pid})
    assert status == 200
    assert hub.db.get("SELECT program_id, snapshot_id FROM runs WHERE id = ?", body["id"]) == {"program_id": pid, "snapshot_id": snap}


def test_ignores_a_snapshot_id_supplied_by_the_client(api):
    hub, client = api
    pid = tracked_program(hub, client, "Kappa", "https://hackerone.com/kappa")
    real = client.post(f"/api/proposals/{propose(hub, pid)}/confirm")[1]["snapshotId"]
    body = client.post("/api/runs", {"agent": "sin-of-friday", "task": "x", "programId": pid, "snapshotId": 9999})[1]
    assert hub.db.get("SELECT snapshot_id FROM runs WHERE id = ?", body["id"])["snapshot_id"] == real


def test_requires_agent_and_task(api):
    _, client = api
    assert client.post("/api/runs", {"agent": "sin-of-friday", "task": "  "})[0] == 400
    assert client.post("/api/runs", {"agent": "nobody", "task": "x"})[0] == 400


# ---- archive endpoints ----


def test_replays_a_stored_run_that_is_no_longer_live(api):
    hub, client = api
    create_run(hub.db, {"id": "old-run", "agent": "sin-of-friday", "task": "old task", "tools": ["Read"]})
    append_event(hub.db, "old-run", 0, {"kind": "meta", "agent": "sin-of-friday", "ts": 1})
    append_event(hub.db, "old-run", 1, {"kind": "closed", "code": 0, "status": "done", "ts": 2})
    finish_run(hub.db, "old-run", "done")
    _, _, text = client.request("GET", "/api/runs/old-run/events")
    assert '"kind":"meta"' in text
    assert "event: done" in text
    assert any(x["id"] == "old-run" for x in client.get("/api/runs?agent=sin-of-friday")[1])
    assert client.get("/api/runs/old-run")[1]["task"] == "old task"
    assert client.get("/api/runs/no-such-run")[0] == 404


def test_lists_findings_by_severity(api):
    hub, client = api

    def f(title, severity):
        return {"target": "app.example.com", "title": title, "status": "suspected", "severity": severity, "description": "d"}

    insert_agent_row(hub.db, "diablo-of-monday", "seed", "web_findings", f("Low one", "low"))
    insert_agent_row(hub.db, "metsa-of-tuesday", "seed", "api_findings", f("Critical one", "critical"))
    rows = client.get("/api/findings")[1]
    assert [x["title"] for x in rows][:2] == ["Critical one", "Low one"]
    assert rows[0]["kind"] == "api"


def test_exports_a_submission_as_markdown(api):
    hub, client = api
    pid = tracked_program(hub, client, "Iota", "https://hackerone.com/iota")
    sub = insert_agent_row(hub.db, "sen-of-saturday", "seed", "submissions", {
        "program_id": pid, "title": "IDOR in invoices", "severity": "high", "body_markdown": "## Steps\n1. ..."})["id"]
    status, body = client.get(f"/api/submissions/{sub}/export")
    assert status == 200
    assert "IDOR in invoices" in body
    assert "Iota" in body


def test_lists_agents_orchestrator_first(api):
    _, client = api
    agents = client.get("/api/agents")[1]
    assert agents[0]["agent"] == "dann-of-thursday"
    assert len(agents) == 7


def test_serves_the_built_client_with_spa_fallback(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><head></head><body>app</body></html>", encoding="utf8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf8")
    hub, server, client = start_hub(tmp_path, static_dir=dist, index_bootstrap=lambda: {"prefs": {"scale": 1.25}})
    try:
        status, headers, text = client.request("GET", "/assets/app.js")
        assert status == 200 and "javascript" in headers["Content-Type"]
        status, _, text = client.request("GET", "/bounties/anything")
        assert status == 200 and "window.__EI_DESKTOP__" in text and '"scale":1.25' in text
        status, _, text = client.request("GET", "/../../secret.txt")
        assert "app" in text
    finally:
        server.shutdown()
