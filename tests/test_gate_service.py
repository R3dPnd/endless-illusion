import json
import threading
import time

import pytest

from hub.db.pipeline import add_stage, create_engagement
from hub.gate_service import (
    DECLARE_FIRST,
    GateRefused,
    RunContext,
    cancel_for_run,
    check_permission,
    context_for_run,
    decide,
    expire_orphaned,
    pending_actions,
    record_declaration,
    wait_for_decision,
)

SCOPE = ["localhost:3000", "127.0.0.1:3000"]
IN_CMD = "curl -s http://localhost:3000/a"
OUT_CMD = "curl -s http://example.com/"
UNKNOWN_CMD = "curl http://$H/"


def make_ctx(db, tmp_path, run_id="run-a", name="Juice Lab"):
    e = create_engagement(db, name, "lab", SCOPE, "", "my own lab")
    add_stage(db, e["id"], "web", run_id, True)
    ctx = context_for_run(db, run_id, tmp_path)
    assert ctx is not None
    return ctx


def declare(db, ctx, target, why="check login", technique="GET request", risk="none, read-only"):
    return record_declaration(db, ctx.run_id, target, why, technique, risk)


def no_wait(action_id):
    raise AssertionError(f"should not wait (action {action_id})")


def waiter(db):
    return lambda action_id: wait_for_decision(db, action_id, poll=0.01, timeout=10)


def decide_when_pending(db, run_id, **kw):
    """Background operator: once `run_id` has a pending action, decide it."""
    errors = []

    def go():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            mine = [a for a in pending_actions(db) if a["run_id"] == run_id]
            if mine:
                try:
                    decide(db, mine[0]["id"], **kw)
                except Exception as err:  # surfaced by the test
                    errors.append(err)
                return
            time.sleep(0.01)
        errors.append(TimeoutError("no pending action"))

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, errors


def last_action(db):
    return db.get("SELECT * FROM gate_actions ORDER BY id DESC LIMIT 1")


def test_context_for_run(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    assert isinstance(ctx, RunContext)
    assert ctx.slug == "juice-lab"
    assert ctx.stage == "web"
    assert ctx.scope_hosts == SCOPE
    assert ctx.workdir == (tmp_path / "research" / "juice-lab").resolve()
    assert ctx.workdir.is_absolute()


def test_context_for_run_unknown_run_is_none(db, tmp_path):
    make_ctx(db, tmp_path)
    assert context_for_run(db, "no-such-run", tmp_path) is None
    assert context_for_run(db, "", tmp_path) is None


@pytest.mark.parametrize("status", ["done", "failed", "stopped", "skipped", "ready"])
def test_context_for_run_needs_a_running_stage(db, tmp_path, status):
    """I5: a run whose stage row is no longer running has no context, so every gated call is denied."""
    ctx = make_ctx(db, tmp_path)
    row = db.get("SELECT id FROM ops_stages WHERE run_id = ?", ctx.run_id)
    db.run("UPDATE ops_stages SET status = ? WHERE id = ?", status, row["id"])
    assert context_for_run(db, ctx.run_id, tmp_path) is None
    reply = check_permission(db, None, "Bash", {"command": IN_CMD}, no_wait)
    assert reply["behavior"] == "deny"


def test_record_declaration_rejects_empty_fields(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    for field in ("target", "why", "technique", "risk"):
        args = {"target": IN_CMD, "why": "w", "technique": "t", "risk": "r", field: "  "}
        with pytest.raises(ValueError):
            record_declaration(db, ctx.run_id, **args)
    with pytest.raises(ValueError):
        record_declaration(db, "", IN_CMD, "w", "t", "r")


def test_local_bash_auto_allowed(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "Bash", {"command": "ls"}, no_wait)
    assert reply["behavior"] == "allow"
    a = last_action(db)
    assert a["status"] == "auto_allowed"
    assert json.loads(a["input"]) == {"command": "ls"}
    assert a["run_id"] == ctx.run_id and a["engagement_id"] == ctx.engagement_id and a["stage"] == "web"


def test_gated_without_declaration_auto_denied(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, no_wait)
    assert reply == {"behavior": "deny", "message": DECLARE_FIRST}
    assert DECLARE_FIRST == "call declare_action with why, technique and risk first"
    a = last_action(db)
    assert a["status"] == "auto_denied"
    assert a["verdict"] == "in"
    assert json.loads(a["hosts"]) == ["localhost:3000"]


def test_declaration_must_match_exactly(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, "curl -s http://localhost:3000/a")
    reply = check_permission(db, ctx, "Bash", {"command": "curl -s  http://localhost:3000/a"}, no_wait)
    assert reply["behavior"] == "deny"
    assert reply["message"] == DECLARE_FIRST
    assert last_action(db)["status"] == "auto_denied"


def test_declaration_from_other_run_does_not_count(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    record_declaration(db, "other-run", IN_CMD, "w", "t", "r")
    assert check_permission(db, ctx, "Bash", {"command": IN_CMD}, no_wait)["message"] == DECLARE_FIRST


def test_missing_technique_auto_denied(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    # record_declaration refuses empty fields, so plant a bad row directly.
    db.run(
        "INSERT INTO gate_declarations (run_id, target, why, technique, risk, created_at) VALUES (?,?,?,?,?,?)",
        ctx.run_id, IN_CMD, "why", "", "risk", "2026-11-24T00:00:00.000Z",
    )
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, no_wait)
    assert reply == {"behavior": "deny", "message": DECLARE_FIRST}
    assert last_action(db)["status"] == "auto_denied"


def test_approve_returns_allow_with_input(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)
    t, errors = decide_when_pending(db, ctx.run_id, approve=True)
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD, "description": "probe"}, waiter(db))
    t.join(5)
    assert not errors
    assert reply["behavior"] == "allow"
    a = last_action(db)
    assert a["status"] == "approved"
    assert a["decided_at"]
    assert json.loads(a["input"]) == {"command": IN_CMD, "description": "probe"}
    assert (a["target"], a["why"], a["technique"], a["risk"]) == (IN_CMD, "check login", "GET request", "none, read-only")
    assert a["verdict"] == "in"


def test_deny_message_reaches_agent(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)
    t, errors = decide_when_pending(db, ctx.run_id, approve=False, message="too noisy, use -I")
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, waiter(db))
    t.join(5)
    assert not errors
    assert reply == {"behavior": "deny", "message": "too noisy, use -I"}
    assert last_action(db)["status"] == "denied"


def test_deny_without_message_says_operator_denied(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)
    t, _ = decide_when_pending(db, ctx.run_id, approve=False)
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, waiter(db))
    t.join(5)
    assert reply == {"behavior": "deny", "message": "operator denied"}


def pending_one(db, ctx, command):
    """Put one action into `pending` (wait returns immediately) and return its id."""
    declare(db, ctx, command)
    ids = []
    check_permission(db, ctx, "Bash", {"command": command}, lambda aid: ids.append(aid) or {"behavior": "deny", "message": ""})
    assert len(ids) == 1
    return ids[0]


def test_out_of_scope_cannot_be_approved(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, OUT_CMD)
    assert db.get("SELECT verdict, status FROM gate_actions WHERE id = ?", aid) == {"verdict": "out", "status": "pending"}
    with pytest.raises(GateRefused) as exc:
        decide(db, aid, approve=True, scope_ack=True)
    assert exc.value.status == 409
    assert isinstance(exc.value, PermissionError)
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "pending"
    decide(db, aid, approve=False)
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "denied"


def test_unknown_needs_scope_ack(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, UNKNOWN_CMD)
    assert db.get("SELECT verdict FROM gate_actions WHERE id = ?", aid)["verdict"] == "unknown"
    with pytest.raises(GateRefused):
        decide(db, aid, approve=True)
    row = decide(db, aid, approve=True, scope_ack=True)
    assert row["status"] == "approved"
    assert row["scope_ack"] == 1
    assert wait_for_decision(db, aid, poll=0.01, timeout=1)["behavior"] == "allow"


def test_none_verdict_bash_shown_as_unknown(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, "ls &")  # gated, but no host and nothing indirect
    a = db.get("SELECT verdict, hosts FROM gate_actions WHERE id = ?", aid)
    assert a == {"verdict": "unknown", "hosts": "[]"}
    with pytest.raises(GateRefused):
        decide(db, aid, approve=True)


def test_double_decide_rejected(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, IN_CMD)
    decide(db, aid, approve=True)
    with pytest.raises(ValueError):
        decide(db, aid, approve=False)
    with pytest.raises(ValueError):
        decide(db, aid, approve=True)
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "approved"
    with pytest.raises(ValueError):
        decide(db, 9999, approve=True)


def test_parallel_pending_are_independent(db, tmp_path):
    a = make_ctx(db, tmp_path, "run-a", "Lab A")
    b = make_ctx(db, tmp_path, "run-b", "Lab B")
    declare(db, a, IN_CMD)
    declare(db, b, IN_CMD)
    replies = {}

    def agent(ctx):
        replies[ctx.run_id] = check_permission(
            db, ctx, "Bash", {"command": IN_CMD},
            lambda aid: wait_for_decision(db, aid, poll=0.01, timeout=3),
        )

    threads = [threading.Thread(target=agent, args=(c,), daemon=True) for c in (a, b)]
    for t in threads:
        t.start()
    deadline = time.monotonic() + 5
    while len(pending_actions(db)) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    by_run = {p["run_id"]: p for p in pending_actions(db)}
    assert set(by_run) == {"run-a", "run-b"}
    assert [p["run_id"] for p in pending_actions(db, a.engagement_id)] == ["run-a"]
    decide(db, by_run["run-a"]["id"], approve=True)
    threads[0].join(5)
    assert replies["run-a"]["behavior"] == "allow"
    assert "run-b" not in replies
    assert [p["run_id"] for p in pending_actions(db)] == ["run-b"]
    decide(db, by_run["run-b"]["id"], approve=False, message="no")
    threads[1].join(5)
    assert replies["run-b"] == {"behavior": "deny", "message": "no"}


def test_expire_orphaned_pending(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    live = make_ctx(db, tmp_path, "run-live", "Live Lab")
    aid = pending_one(db, ctx, IN_CMD)
    keep = pending_one(db, live, IN_CMD)
    assert expire_orphaned(db, {"run-live"}) == 1
    assert db.get("SELECT status, decided_at FROM gate_actions WHERE id = ?", aid)["status"] == "expired"
    assert wait_for_decision(db, aid, poll=0.01, timeout=1) == {"behavior": "deny", "message": "action was cancelled"}
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", keep)["status"] == "pending"
    assert expire_orphaned(db, set()) == 1
    with pytest.raises(ValueError):
        decide(db, aid, approve=True)


def test_expire_orphaned_releases_a_blocked_waiter(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)
    out = []
    t = threading.Thread(
        target=lambda: out.append(check_permission(db, ctx, "Bash", {"command": IN_CMD}, waiter(db))), daemon=True
    )
    t.start()
    deadline = time.monotonic() + 5
    while not pending_actions(db) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert expire_orphaned(db, set()) == 1
    t.join(5)
    assert out == [{"behavior": "deny", "message": "action was cancelled"}]


def test_cancel_for_run(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    other = make_ctx(db, tmp_path, "run-b", "Lab B")
    aid = pending_one(db, ctx, IN_CMD)
    keep = pending_one(db, other, IN_CMD)
    assert cancel_for_run(db, ctx.run_id) == 1
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", aid)["status"] == "cancelled"
    assert wait_for_decision(db, aid, timeout=1) == {"behavior": "deny", "message": "action was cancelled"}
    assert db.get("SELECT status FROM gate_actions WHERE id = ?", keep)["status"] == "pending"
    assert cancel_for_run(db, ctx.run_id) == 0


def test_wait_timeout_expires_and_denies(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, IN_CMD)
    start = time.monotonic()
    reply = wait_for_decision(db, aid, poll=0.01, timeout=0.1)
    assert time.monotonic() - start < 2
    assert reply["behavior"] == "deny"
    a = db.get("SELECT status, decided_at FROM gate_actions WHERE id = ?", aid)
    assert a["status"] == "expired" and a["decided_at"]
    with pytest.raises(ValueError):
        decide(db, aid, approve=True)


def test_wait_unknown_action_denies(db):
    assert wait_for_decision(db, 424242, timeout=0.1)["behavior"] == "deny"


def test_declaration_consumed_once(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, IN_CMD)
    decl = db.get("SELECT used_at, action_id FROM gate_declarations WHERE run_id = ?", ctx.run_id)
    assert decl["used_at"] and decl["action_id"] == aid
    # Same command again without a new declaration: denied.
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, no_wait)
    assert reply == {"behavior": "deny", "message": DECLARE_FIRST}
    # A fresh declaration unlocks exactly one more.
    assert pending_one(db, ctx, IN_CMD) != aid


def test_webfetch_offscope_host_auto_allowed(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "WebFetch", {"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-1", "prompt": "x"}, no_wait)
    assert reply["behavior"] == "allow"
    a = last_action(db)
    assert (a["status"], a["verdict"]) == ("auto_allowed", "out")
    assert json.loads(a["hosts"]) == ["nvd.nist.gov"]


def test_webfetch_in_scope_is_gated(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    url = "http://localhost:3000/rest/products"
    assert check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, no_wait)["message"] == DECLARE_FIRST
    declare(db, ctx, url)
    t, errors = decide_when_pending(db, ctx.run_id, approve=True)
    reply = check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, waiter(db))
    t.join(5)
    assert not errors
    assert reply["behavior"] == "allow"
    assert last_action(db)["verdict"] == "in"


def test_write_outside_workdir_auto_denied(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    for tool in ("Write", "Edit"):
        reply = check_permission(db, ctx, tool, {"file_path": str(tmp_path / "elsewhere.md"), "content": "x"}, no_wait)
        assert reply == {"behavior": "deny", "message": "writes are limited to research/juice-lab/ (absolute paths)"}
        assert last_action(db)["status"] == "auto_denied"
    # relative paths are refused too
    assert check_permission(db, ctx, "Write", {"file_path": "research/juice-lab/a.md"}, no_wait)["behavior"] == "deny"
    assert check_permission(db, ctx, "Write", {}, no_wait)["behavior"] == "deny"


def test_write_inside_workdir_auto_allowed(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "Write", {"file_path": str(ctx.workdir / "notes.md"), "content": "x"}, no_wait)
    assert reply["behavior"] == "allow"
    assert last_action(db)["status"] == "auto_allowed"


def test_notebookedit_outside_workdir_denied(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "NotebookEdit", {"notebook_path": str(tmp_path / "x.ipynb"), "new_source": "1"}, no_wait)
    assert reply["behavior"] == "deny"
    assert last_action(db)["status"] == "auto_denied"
    ok = check_permission(db, ctx, "NotebookEdit", {"notebook_path": str(ctx.workdir / "x.ipynb"), "new_source": "1"}, no_wait)
    assert ok["behavior"] == "allow"


def test_other_tools_auto_allowed_and_recorded(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "Read", {"file_path": "/etc/hosts"}, no_wait)
    assert reply["behavior"] == "allow"
    a = last_action(db)
    assert (a["tool_name"], a["status"], a["verdict"]) == ("Read", "auto_allowed", "none")


def test_exception_in_rules_denies(db, tmp_path, monkeypatch):
    import hub.gate_service as gs

    ctx = make_ctx(db, tmp_path)

    def boom(*a, **k):
        raise RuntimeError("rules bug")

    monkeypatch.setattr(gs, "classify_bash", boom)
    reply = check_permission(db, ctx, "Bash", {"command": "ls"}, no_wait)
    assert reply == {"behavior": "deny", "message": "gate error: RuntimeError"}
    a = last_action(db)
    assert (a["status"], a["message"]) == ("auto_denied", "gate error: RuntimeError")


def test_exception_in_rules_denies_even_if_recording_fails(db, tmp_path, monkeypatch):
    import hub.gate_service as gs

    ctx = make_ctx(db, tmp_path)
    monkeypatch.setattr(gs, "classify_bash", lambda *a, **k: 1 / 0)
    monkeypatch.setattr(gs, "_record", lambda *a, **k: 1 / 0)
    assert check_permission(db, ctx, "Bash", {"command": "ls"}, no_wait) == {
        "behavior": "deny", "message": "gate error: ZeroDivisionError"}


def test_exception_in_wait_denies(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)

    def bad_wait(action_id):
        raise OSError("database is locked")

    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, bad_wait)
    assert reply == {"behavior": "deny", "message": "gate error: OSError"}
    assert pending_actions(db) == []  # the orphaned pending action is expired
    statuses = [r["status"] for r in db.all("SELECT status FROM gate_actions ORDER BY id")]
    assert statuses == ["expired", "auto_denied"]


def test_malformed_wait_reply_denies(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    declare(db, ctx, IN_CMD)
    reply = check_permission(db, ctx, "Bash", {"command": IN_CMD}, lambda aid: {"behavior": "maybe"})
    assert reply["behavior"] == "deny"


def test_wait_allows_only_approved_rows(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    check_permission(db, ctx, "Bash", {"command": "ls"}, no_wait)
    auto = last_action(db)
    assert auto["status"] == "auto_allowed"
    assert wait_for_decision(db, auto["id"], timeout=0.1)["behavior"] == "deny"
    check_permission(db, ctx, "Bash", {"command": IN_CMD}, no_wait)
    assert wait_for_decision(db, last_action(db)["id"], timeout=0.1)["behavior"] == "deny"


def test_wait_bound_to_run(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, IN_CMD)
    decide(db, aid, approve=True)
    assert wait_for_decision(db, aid, timeout=0.1, run_id="other-run")["behavior"] == "deny"
    assert wait_for_decision(db, aid, timeout=0.1, run_id=ctx.run_id)["behavior"] == "allow"


def test_none_verdict_needs_scope_ack(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    aid = pending_one(db, ctx, IN_CMD)
    db.run("UPDATE gate_actions SET verdict = 'none' WHERE id = ?", aid)
    with pytest.raises(GateRefused):
        decide(db, aid, approve=True)
    assert decide(db, aid, approve=True, scope_ack=True)["status"] == "approved"


def test_multiedit_is_a_write_tool(db, tmp_path):
    ctx = make_ctx(db, tmp_path)
    reply = check_permission(db, ctx, "MultiEdit", {"file_path": str(tmp_path / "x.md"), "edits": []}, no_wait)
    assert reply["behavior"] == "deny"
    assert last_action(db)["status"] == "auto_denied"
    assert check_permission(db, ctx, "MultiEdit", {"file_path": str(ctx.workdir / "x.md")}, no_wait)["behavior"] == "allow"


# ---- R14: WebFetch auto-allows only plain, unrelated DNS names ----


def _ctx_with_scope(db, tmp_path, scope, run_id="run-wf"):
    e = create_engagement(db, f"wf {run_id}", "lab", scope, "", "my own lab")
    add_stage(db, e["id"], "web", run_id, True)
    return context_for_run(db, run_id, tmp_path)


@pytest.mark.parametrize(
    "scope,url",
    [
        (["app.example.com:443"], "https://app.example.com/"),
        (["127.0.0.1:3000"], "http://localhost:3000/"),
        (["127.0.0.1:3000"], "http://127.1:3000/"),
        (["127.0.0.1:3000"], "http://2130706433:3000/"),
        (["127.0.0.1:3000"], "http://[::ffff:127.0.0.1]:3000/"),
        (["127.0.0.1:3000"], "http://127.0.0.1.nip.io:3000/"),
        (["127.0.0.1:3000"], "http://0x7f.1:3000/"),
        (["127.0.0.1:3000"], "http://127.0.0.1:8080/"),
        (["app.example.com"], "https://example.com/"),
        (["app.example.com"], "https://api.app.example.com/"),
    ],
)
def test_webfetch_aliases_and_port_mismatches_are_gated(db, tmp_path, scope, url):
    ctx = _ctx_with_scope(db, tmp_path, scope)
    # Undeclared: denied (never auto-allowed), recorded with verdict unknown.
    reply = check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, no_wait)
    assert (reply["behavior"], reply["message"]) == ("deny", DECLARE_FIRST)
    assert (last_action(db)["status"], last_action(db)["verdict"]) == ("auto_denied", "unknown")
    # Declared: goes pending with verdict unknown, so approving it needs scopeAck.
    declare(db, ctx, url)
    t, errors = decide_when_pending(db, ctx.run_id, approve=True)
    waited = threading.Thread(target=lambda: check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, waiter(db)), daemon=True)
    waited.start()
    t.join(5)
    assert len(errors) == 1 and isinstance(errors[0], GateRefused)
    a = db.get("SELECT * FROM gate_actions WHERE run_id = ? AND status = 'pending'", ctx.run_id)
    assert a is not None and a["verdict"] == "unknown"
    decide(db, a["id"], False)
    waited.join(5)


@pytest.mark.parametrize("url", ["https://nvd.nist.gov/vuln/detail/CVE-2024-1", "https://github.com/juice-shop/juice-shop"])
def test_webfetch_research_sites_still_auto_allowed(db, tmp_path, url):
    ctx = _ctx_with_scope(db, tmp_path, ["127.0.0.1:3000"])
    assert check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, no_wait)["behavior"] == "allow"
    assert (last_action(db)["status"], last_action(db)["verdict"]) == ("auto_allowed", "out")


def test_webfetch_exact_in_scope_url_gated_as_in(db, tmp_path):
    ctx = _ctx_with_scope(db, tmp_path, ["127.0.0.1:3000"])
    url = "http://127.0.0.1:3000/rest/products"
    assert check_permission(db, ctx, "WebFetch", {"url": url, "prompt": "x"}, no_wait)["message"] == DECLARE_FIRST
    assert last_action(db)["verdict"] == "in"
