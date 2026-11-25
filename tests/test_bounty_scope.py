"""I1: a bounty engagement's scope comes from its confirmed snapshot, never from free text."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from hub.db import now_iso
from hub.db.bounties import list_bounties
from hub.db.pipeline import add_stage, create_engagement
from hub.db.scope import asset_hosts, snapshot_scope
from hub.gate_service import DECLARE_FIRST, check_permission, context_for_run, record_declaration

IN_SCOPE = [
    {"asset": "*.example.com", "type": "wildcard"},
    {"asset": "https://app.example.org/login", "type": "url"},
    {"asset": "api.example.net:8443"},
    {"asset": "com.example.android", "type": "Android app"},
    {"asset": "Any other asset the program owns"},
]
OUT_OF_SCOPE = [{"asset": "legacy.example.com"}]
EXCLUSIONS = {"conduct": ["no DoS"], "assets": ["Do not test *.corp.example.com or status.example.com."]}


_N = iter(range(10**6))


def program(db, in_scope=IN_SCOPE, out=OUT_OF_SCOPE, exclusions=EXCLUSIONS, age_days=0):
    n = next(_N)
    pid, _ = db.run(
        "INSERT INTO programs (name, url, normalized_url, source, created_at) VALUES (?, ?, ?, 'manual', ?)",
        f"P{n}", f"https://h1.example/p{n}", f"h1.example/p{n}", now_iso(),
    )
    confirmed = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat().replace("+00:00", "Z")
    db.run(
        "INSERT INTO scope_snapshots (program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?,?,?,?,?)",
        pid, json.dumps(in_scope), json.dumps(out), json.dumps(exclusions), confirmed,
    )
    return pid


def test_asset_hosts():
    assert asset_hosts("*.example.com") == ["*.example.com"]
    assert asset_hosts("https://user@App.Example.org:8443/x?y") == ["app.example.org:8443"]
    assert asset_hosts("a.example.com, b.example.com (API)") == ["a.example.com", "b.example.com"]
    assert asset_hosts("10.0.0.5") == ["10.0.0.5"]
    for junk in ("*", "*.com", "Any other asset", "e.g. things", "no DoS", ""):
        assert asset_hosts(junk) == [], junk


def test_snapshot_scope_derives_in_and_out(db):
    s = snapshot_scope(db, None)
    assert s == {"in": [], "out": [], "stale": False, "snapshot_id": None}
    pid = program(db)
    snap = db.get("SELECT id FROM scope_snapshots WHERE program_id = ?", pid)["id"]
    s = snapshot_scope(db, snap)
    assert s["in"] == ["*.example.com", "app.example.org", "api.example.net:8443"]  # the Android app id is skipped
    assert set(s["out"]) == {"legacy.example.com", "*.corp.example.com", "status.example.com"}
    assert s["stale"] is False


def test_bounty_engagement_scope_comes_from_the_snapshot(db):
    pid = program(db)
    e = create_engagement(db, "B", "bounty", [], "", "program policy", program_id=pid)
    assert e["scope_hosts"] == ["*.example.com", "app.example.org", "api.example.net:8443"]
    # The operator may narrow to hosts inside the snapshot, never widen it.
    e2 = create_engagement(db, "B2", "bounty", ["shop.example.com", "app.example.org"], "", "program policy", program_id=pid)
    assert e2["scope_hosts"] == ["shop.example.com", "app.example.org"]
    for outside in (["evil.com"], ["example.com"], ["api.example.net:9999", "shop.example.com"], ["*.example.com.evil.io"]):
        with pytest.raises(ValueError, match="outside"):
            create_engagement(db, "B3", "bounty", outside, "", "program policy", program_id=pid)
    # Excluded hosts can't be chosen even if they match in_scope.
    with pytest.raises(ValueError, match="outside|excluded"):
        create_engagement(db, "B4", "bounty", ["legacy.example.com"], "", "program policy", program_id=pid)


def test_bounty_without_host_assets_refused(db):
    pid = program(db, in_scope=[{"asset": "The iOS app", "type": "ios"}])
    with pytest.raises(ValueError, match="host"):
        create_engagement(db, "B", "bounty", [], "", "program policy", program_id=pid)


def _ctx(db, tmp_path, run_id):
    e = create_engagement(db, f"B {run_id}", "bounty", [], "", "program policy", program_id=program(db))
    add_stage(db, e["id"], "web", run_id, True)
    return context_for_run(db, run_id, tmp_path)


def test_gate_treats_out_of_scope_and_exclusions_as_out(db, tmp_path):
    ctx = _ctx(db, tmp_path, "run-b")
    assert set(ctx.out_hosts) == {"legacy.example.com", "*.corp.example.com", "status.example.com"}
    for cmd in ("curl -s https://legacy.example.com/", "curl -s https://vpn.corp.example.com/", "curl -s https://status.example.com/",
                "curl -sL https://legacy.example.com/"):  # even an indirect command naming an excluded host
        record_declaration(db, ctx.run_id, cmd, "why", "tech", "risk")
        t = check_permission(db, ctx, "Bash", {"command": cmd}, lambda aid: {"behavior": "deny", "message": "x"})
        assert t["behavior"] == "deny"
        a = db.get("SELECT verdict, status FROM gate_actions ORDER BY id DESC LIMIT 1")
        assert a["verdict"] == "out", cmd
    # An in-scope host stays "in".
    record_declaration(db, ctx.run_id, "curl -s https://shop.example.com/", "why", "tech", "risk")
    check_permission(db, ctx, "Bash", {"command": "curl -s https://shop.example.com/"}, lambda aid: {"behavior": "deny", "message": "x"})
    assert db.get("SELECT verdict FROM gate_actions ORDER BY id DESC LIMIT 1")["verdict"] == "in"


def test_webfetch_to_an_excluded_host_is_denied_not_auto_allowed(db, tmp_path):
    ctx = _ctx(db, tmp_path, "run-bf")
    reply = check_permission(db, ctx, "WebFetch", {"url": "https://status.example.com/", "prompt": "x"}, lambda aid: 1 / 0)
    assert reply["behavior"] == "deny" and reply["message"] != DECLARE_FIRST
    a = db.get("SELECT verdict, status FROM gate_actions ORDER BY id DESC LIMIT 1")
    assert (a["verdict"], a["status"]) == ("out", "auto_denied")


def test_list_bounties_exposes_derived_scope_hosts(db):
    program(db)
    (p,) = list_bounties(db)["confirmed"]
    assert p["snapshot"]["scopeHosts"] == ["*.example.com", "app.example.org", "api.example.net:8443"]


def test_arming_a_bounty_stage_refused_on_a_stale_snapshot(tmp_path):
    from types import SimpleNamespace

    from hub import pipeline
    from hub.db import open_db

    db = open_db(":memory:")
    hub = SimpleNamespace(db=db, repo_root=tmp_path, runner=SimpleNamespace(get=lambda run_id: None))
    stale = create_engagement(db, "Old", "bounty", [], "", "program policy", program_id=program(db, age_days=31))
    with pytest.raises(ValueError, match="stale"):
        pipeline.start_stage(hub, stale["id"], "discovery", armed=True)
