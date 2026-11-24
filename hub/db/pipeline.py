"""Engagement pipeline: engagements, operator-started stages, and plan approval."""

import json
import re

from . import now_iso
from .bounties import HttpError, require_confirmed_snapshot

KINDS = ("lab", "bounty")
FINISHED = ("done", "failed", "stopped", "skipped")


def _engagement(row):
    if row is not None:
        row["scope_hosts"] = json.loads(row["scope_hosts"] or "[]")
    return row


def _slug(db, name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "engagement"
    slug, n = base, 1
    while db.get("SELECT 1 AS x FROM ops_engagements WHERE slug = ?", slug):
        n += 1
        slug = f"{base}-{n}"
    return slug


def create_engagement(db, name, kind, scope_hosts, scope_notes, authorization, program_id=None, snapshot_id=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("engagement name is required")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    hosts = [h.strip() for h in (scope_hosts or []) if isinstance(h, str) and h.strip()]
    if kind == "bounty":
        if program_id is None:
            raise ValueError("a bounty engagement needs a program")
        try:
            snapshot_id = require_confirmed_snapshot(db, program_id)
        except HttpError as err:
            raise ValueError(str(err)) from err
    else:
        if not hosts:
            raise ValueError("a lab engagement needs at least one host")
        program_id = snapshot_id = None
    with db.transaction():
        eid, _ = db.run(
            "INSERT INTO ops_engagements (slug, name, kind, scope_hosts, scope_notes, authorization, program_id, snapshot_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            _slug(db, name), name, kind, json.dumps(hosts), scope_notes or "", authorization or "", program_id, snapshot_id, now_iso(),
        )
    return get_engagement(db, eid)


def get_engagement(db, id):
    return _engagement(db.get("SELECT * FROM ops_engagements WHERE id = ?", id))


def list_engagements(db):
    return [_engagement(r) for r in db.all("SELECT * FROM ops_engagements ORDER BY id DESC")]


def add_stage(db, engagement_id, stage, run_id, armed, question=None):
    """Record a stage on start (run_id set, running) or skip (no run: caller then sets 'skipped')."""
    status = "running" if run_id else "ready"
    sid, _ = db.run(
        "INSERT INTO ops_stages (engagement_id, stage, status, run_id, armed, question, created_at) VALUES (?,?,?,?,?,?,?)",
        engagement_id, stage, status, run_id, 1 if armed else 0, question, now_iso(),
    )
    return sid


def set_stage_status(db, stage_id, status):
    db.run("UPDATE ops_stages SET status = ?, finished_at = ? WHERE id = ?", status, now_iso() if status in FINISHED else None, stage_id)


def stage_rows(db, engagement_id):
    return db.all("SELECT * FROM ops_stages WHERE engagement_id = ? ORDER BY id", engagement_id)


def _plan(row):
    if row is not None:
        row["plan"] = json.loads(row["plan"] or "{}")
    return row


def latest_plan_draft(db, engagement_id):
    return _plan(db.get("SELECT * FROM plan_drafts WHERE engagement_id = ? ORDER BY id DESC LIMIT 1", engagement_id))


def approve_plan(db, engagement_id):
    with db.transaction():
        draft = db.get("SELECT id, plan FROM plan_drafts WHERE engagement_id = ? ORDER BY id DESC LIMIT 1", engagement_id)
        if not draft:
            raise ValueError("no plan draft to approve")
        pid, _ = db.run(
            "INSERT INTO ops_plans (engagement_id, draft_id, plan, approved_at) VALUES (?,?,?,?)",
            engagement_id, draft["id"], draft["plan"], now_iso(),
        )
    return pid


def approved_plan(db, engagement_id):
    return _plan(db.get("SELECT * FROM ops_plans WHERE engagement_id = ? ORDER BY id DESC LIMIT 1", engagement_id))
