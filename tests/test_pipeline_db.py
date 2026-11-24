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
        pid, "[]", "[]", "[]", now_iso(),
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
    insert_agent_row(db, "dann-of-thursday", "run-1", "plan_drafts", {"engagement_id": e["id"], "summary": "s", "plan": plan})
    assert latest_plan_draft(db, e["id"])["plan"] == plan
    assert approved_plan(db, e["id"]) is None
    approve_plan(db, e["id"])
    assert approved_plan(db, e["id"])["plan"] == plan


def test_approve_plan_without_draft_raises(db):
    with pytest.raises(ValueError):
        approve_plan(db, lab(db)["id"])
