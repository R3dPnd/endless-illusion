import json

import pytest

from hub.db.write import insert_agent_row

from .conftest import start_hub
from .test_api import propose, tracked_program

PLAN = {"stages": {"web": {"include": True, "targets": ["localhost:3000"], "focus": "login"}}, "research": []}


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    hub, server, client = start_hub(tmp_path_factory.mktemp("eng-api"))
    yield hub, client
    hub.runner.stop_all()
    server.shutdown()


def lab(client, name="Juice Lab", hosts=("localhost:3000",)):
    status, body = client.post("/api/engagements", {"name": name, "kind": "lab", "scopeHosts": list(hosts), "scopeNotes": "n", "authorization": "my lab"})
    assert status == 200, body
    return body


def stage_status(client, eid, stage):
    return next(s for s in client.get(f"/api/engagements/{eid}")[1]["stages"] if s["stage"] == stage)["status"]


def action(hub, eid, verdict, status="pending"):
    aid, _ = hub.db.run(
        "INSERT INTO gate_actions (run_id, engagement_id, stage, tool_name, input, target, why, technique, risk, hosts, verdict, status, created_at)"
        " VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)",
        eid, "web", "Bash", "{}", "http://x/", "why", "tech", "low", json.dumps(["x"]), verdict, status, "2026-01-01T00:00:00Z",
    )
    return aid


def test_create_engagement_and_view(api):
    hub, client = api
    eng = lab(client)
    assert client.get("/api/engagements")[1][0]["id"] == eng["id"]
    status, view = client.get(f"/api/engagements/{eng['id']}")
    assert status == 200
    assert view["engagement"]["scope_hosts"] == ["localhost:3000"]
    assert [s["stage"] for s in view["stages"]][0] == "discovery"
    assert view["plan"] == {"draft": None, "approved": None}
    assert view["pending"] == [] and view["questions"] == []


def test_create_validation(api):
    _, client = api
    assert client.post("/api/engagements", {"name": "x", "kind": "lab", "scopeHosts": "localhost"})[0] == 400
    assert client.post("/api/engagements", {"name": "x", "kind": "lab", "scopeHosts": [1]})[0] == 400
    assert client.post("/api/engagements", {"name": "", "kind": "lab", "scopeHosts": ["a"]})[0] == 400


def test_start_locked_stage_400(api):
    _, client = api
    eng = lab(client)
    status, body = client.post(f"/api/engagements/{eng['id']}/stages/web/start", {})
    assert status == 400 and "locked" in body["error"]
    assert client.post(f"/api/engagements/{eng['id']}/stages/nope/start", {})[0] == 400


def test_decide_out_of_scope_409(api):
    hub, client = api
    eng = lab(client)
    aid = action(hub, eng["id"], "out")
    status, body = client.post(f"/api/gate/actions/{aid}/decide", {"approve": True, "scopeAck": True})
    assert status == 409 and "out-of-scope" in body["error"]
    assert client.post(f"/api/gate/actions/{aid}/decide", {"approve": False})[0] == 200
    assert client.post(f"/api/gate/actions/{aid}/decide", {"approve": False})[0] == 400  # no longer pending


def test_decide_unknown_needs_scope_ack_409(api):
    # Scope refusals are 409 (GateRefused), same as out-of-scope.
    hub, client = api
    eng = lab(client)
    aid = action(hub, eng["id"], "unknown")
    assert client.post(f"/api/gate/actions/{aid}/decide", {"approve": True})[0] == 409
    status, body = client.post(f"/api/gate/actions/{aid}/decide", {"approve": True, "scopeAck": True})
    assert status == 200 and body["status"] == "approved"


def test_decide_cross_origin_403(api):
    hub, client = api
    aid = action(hub, lab(client)["id"], "in")
    assert client.post(f"/api/gate/actions/{aid}/decide", {"approve": True}, {"Origin": "http://evil.example"})[0] == 403
    assert hub.db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "pending"


def test_bounty_snapshot_not_taken_from_body(api):
    hub, client = api
    pid = tracked_program(hub, client, "Engbounty", "https://hackerone.com/engbounty")
    body = {"name": "B", "kind": "bounty", "programId": pid, "scopeHosts": [], "authorization": "bounty", "snapshotId": 9999}
    assert client.post("/api/engagements", body)[0] == 400  # no confirmed scope yet
    real = client.post(f"/api/proposals/{propose(hub, pid)}/confirm")[1]["snapshotId"]
    status, eng = client.post("/api/engagements", body)
    assert status == 200 and eng["snapshot_id"] == real


def test_skip_and_start_routes(api):
    _, client = api
    eng = lab(client)
    eid = eng["id"]
    status, run = client.post(f"/api/engagements/{eid}/stages/discovery/start", {})
    assert status == 200 and run["stage"] == "discovery"
    assert client.post(f"/api/engagements/{eid}/stages/discovery/start", {})[0] == 400  # already running
    assert client.post(f"/api/engagements/{eid}/stages/discovery/skip")[0] == 400  # running: stop first
    status, body = client.post(f"/api/engagements/{eid}/stages/discovery/stop")
    assert status == 200 and body["stopped"] == [run["runId"]]
    assert client.post(f"/api/engagements/{eid}/stages/discovery/stop")[0] == 400
    assert client.post(f"/api/engagements/{eid}/stages/discovery/skip")[0] == 200
    assert stage_status(client, eid, "discovery") == "skipped"
    assert client.post(f"/api/engagements/{eid}/stages/research/skip")[0] == 400


def test_plan_approve_validates(api):
    hub, client = api
    eid = lab(client)["id"]
    assert client.post(f"/api/engagements/{eid}/plan/approve")[0] == 400  # no draft
    insert_agent_row(hub.db, "dann-of-thursday", "r", "plan_drafts", {"engagement_id": eid, "summary": "s", "plan": {"stages": {"web": {"include": "yes"}}}})
    status, body = client.post(f"/api/engagements/{eid}/plan/approve")
    assert status == 400 and body["error"]
    insert_agent_row(hub.db, "dann-of-thursday", "r", "plan_drafts", {"engagement_id": eid, "summary": "s", "plan": PLAN})
    assert client.post(f"/api/engagements/{eid}/plan/approve")[0] == 200
    plan = client.get(f"/api/engagements/{eid}")[1]["plan"]
    assert plan["approved"]["plan"] == PLAN and plan["draft"]["plan"] == PLAN


def test_unknown_engagement_404(api):
    _, client = api
    assert client.get("/api/engagements/9999")[0] == 404
    for path in ("stages/web/start", "stages/web/skip", "stages/web/stop", "plan/approve", "plan/revise", "ask"):
        assert client.post(f"/api/engagements/9999/{path}", {"stage": "web", "question": "q", "comment": "c"})[0] == 404, path


def test_ask_validates(api):
    _, client = api
    eid = lab(client)["id"]
    assert client.post(f"/api/engagements/{eid}/ask", {"stage": "bogus", "question": "q"})[0] == 400
    assert client.post(f"/api/engagements/{eid}/ask", {"stage": "web", "question": "q"})[0] == 400  # no run to ask


def test_gate_pending_count(api):
    hub, client = api
    a, b = lab(client)["id"], lab(client)["id"]
    before = client.get("/api/gate/pending")[1]["count"]
    ids = [action(hub, a, "in"), action(hub, b, "unknown"), action(hub, b, "in", status="approved")]
    status, body = client.get("/api/gate/pending")
    assert status == 200 and body["count"] == before + 2
    assert {i["id"] for i in body["items"]} >= set(ids[:2]) and ids[2] not in {i["id"] for i in body["items"]}
    view = client.get(f"/api/engagements/{b}")[1]
    assert [p["id"] for p in view["pending"]] == [ids[1]]
    assert view["pending"][0]["hosts"] == ["x"] and view["pending"][0]["technique"] == "tech"


BAD = ["false", "no", 1, 0.5]


def test_gate_booleans_must_be_real_booleans(api):
    hub, client = api
    eid = lab(client)["id"]
    aid = action(hub, eid, "unknown")
    for bad in BAD:
        for body in ({"approve": bad}, {"approve": True, "scopeAck": bad}):
            status, err = client.post(f"/api/gate/actions/{aid}/decide", body)
            assert status == 400 and "must be true or false" in err["error"], body
        status, err = client.post(f"/api/engagements/{eid}/stages/discovery/start", {"armed": bad})
        assert status == 400 and "armed must be true or false" in err["error"]
    assert client.post(f"/api/gate/actions/{aid}/decide", {})[0] == 400  # approve is required
    assert hub.db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "pending"
    assert hub.db.get("SELECT COUNT(*) AS n FROM ops_stages WHERE engagement_id = ?", eid)["n"] == 0


def test_create_engagement_types(api):
    _, client = api
    base = {"name": "x", "kind": "lab", "scopeHosts": ["a"]}
    for field in ("name", "scopeNotes", "authorization"):
        assert client.post("/api/engagements", {**base, field: 5})[0] == 400, field
