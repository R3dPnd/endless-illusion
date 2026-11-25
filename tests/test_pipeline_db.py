import pytest

from hub.db import now_iso
from hub.db.ownership import OwnershipError, assert_owns
from hub.db.pipeline import (
    add_stage,
    approve_plan,
    approved_plan,
    create_engagement,
    latest_plan_draft,
    list_engagements,
    set_stage_status,
    stage_rows,
)
from hub.db.validate import ValidationError
from hub.db.write import insert_agent_row


def lab(db, name="Juice Shop Lab"):
    return create_engagement(db, name, "lab", ["juice.local"], "", "my own lab")


def test_create_lab_engagement_slugs_name(db):
    e = lab(db)
    assert e["slug"] == "juice-shop-lab"
    assert e["scope_hosts"] == ["juice.local"]
    assert lab(db)["slug"] == "juice-shop-lab-2"
    assert lab(db, "Juice  Shop Lab!")["slug"] == "juice-shop-lab-3"
    assert len(list_engagements(db)) == 3


def test_empty_name_rejected(db):
    with pytest.raises(ValueError):
        create_engagement(db, "  ", "lab", ["a.local"], "", "")


def test_bounty_requires_confirmed_snapshot(db):
    pid, _ = db.run(
        "INSERT INTO programs (name, url, normalized_url, source, created_at) VALUES ('P','https://p','p','manual',?)", now_iso()
    )
    with pytest.raises(ValueError):
        create_engagement(db, "Bounty", "bounty", [], "", "", program_id=pid)
    sid, _ = db.run(
        "INSERT INTO scope_snapshots (program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?,?,?,?,?)",
        pid, '[{"asset": "app.p.example"}]', "[]", "[]", now_iso(),
    )
    assert create_engagement(db, "Bounty", "bounty", [], "", "", program_id=pid)["snapshot_id"] == sid


def test_lab_requires_hosts(db):
    with pytest.raises(ValueError):
        create_engagement(db, "Lab", "lab", [], "", "")


def test_agent_cannot_write_operator_tables():
    with pytest.raises(OwnershipError):
        assert_owns("dann-of-thursday", "ops_plans")


def test_stages(db):
    e = lab(db)
    sid = add_stage(db, e["id"], "discovery", "run-1", True)
    assert stage_rows(db, e["id"])[0]["status"] == "running"
    set_stage_status(db, sid, "done")
    row = stage_rows(db, e["id"])[0]
    assert row["status"] == "done" and row["finished_at"]


def test_dann_saves_plan_draft_and_operator_approves(db):
    e = lab(db)
    plan = {"stages": {"web": {"include": True, "targets": ["juice.local"], "focus": "xss"}}, "research": []}
    add_stage(db, e["id"], "planning", "run-1", False)
    insert_agent_row(db, "dann-of-thursday", "run-1", "plan_drafts", {"engagement_id": e["id"], "summary": "s", "plan": plan})
    assert latest_plan_draft(db, e["id"])["plan"] == plan
    assert approved_plan(db, e["id"]) is None
    approve_plan(db, e["id"], latest_plan_draft(db, e["id"])["id"])
    assert approved_plan(db, e["id"])["plan"] == plan


def test_plan_draft_must_target_the_runs_own_engagement(db):
    """M2: a plan draft is accepted only for the engagement whose stage the writing run belongs to."""
    mine, other = lab(db), create_engagement(db, "Other Lab", "lab", ["10.0.0.9"], "", "lab")
    add_stage(db, mine["id"], "planning", "run-p", False)
    plan = {"stages": {}, "research": []}
    with pytest.raises(ValidationError, match="engagement"):
        insert_agent_row(db, "dann-of-thursday", "run-p", "plan_drafts", {"engagement_id": other["id"], "plan": plan})
    for run_id in (None, "no-stage-run"):  # a Console run (no stage row) cannot write a plan draft either
        with pytest.raises(ValidationError, match="engagement"):
            insert_agent_row(db, "dann-of-thursday", run_id, "plan_drafts", {"engagement_id": mine["id"], "plan": plan})
    assert db.get("SELECT COUNT(*) AS n FROM plan_drafts")["n"] == 0
    insert_agent_row(db, "dann-of-thursday", "run-p", "plan_drafts", {"engagement_id": mine["id"], "plan": plan})
    assert latest_plan_draft(db, mine["id"])["run_id"] == "run-p"


def test_approve_plan_without_draft_raises(db):
    with pytest.raises(ValueError):
        approve_plan(db, lab(db)["id"], 1)


def test_approve_plan_only_the_latest_draft(db):
    """I3: approving names a draft id, which must still be the latest one (else HttpError 409)."""
    from hub.db.bounties import HttpError

    e = lab(db)
    add_stage(db, e["id"], "planning", "run-q", False)
    first = insert_agent_row(db, "dann-of-thursday", "run-q", "plan_drafts", {"engagement_id": e["id"], "plan": {"stages": {}}})["id"]
    second = insert_agent_row(db, "dann-of-thursday", "run-q", "plan_drafts", {"engagement_id": e["id"], "plan": {"stages": {}}})["id"]
    for stale in (first, True, str(second), None):
        with pytest.raises(HttpError) as err:
            approve_plan(db, e["id"], stale)
        assert err.value.status == 409
    assert approved_plan(db, e["id"]) is None
    approve_plan(db, e["id"], second)
    assert approved_plan(db, e["id"])["draft_id"] == second
