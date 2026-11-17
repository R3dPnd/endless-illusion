"""
Operator actions on the bounty pipeline (called from the UI only):
lead -> tracked program -> confirmed scope snapshot. Agents can only add
leads and proposals; nothing here is reachable from an MCP tool.
"""

import time
from datetime import datetime

from . import now_iso
from .read import list_programs, parse_json
from .redact import clip, redact
from .url import normalize_url


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


STALE_MS = 30 * 24 * 60 * 60 * 1000


def _blank(s):
    return not isinstance(s, str) or not s.strip()


def add_program(db, name=None, url=None, platform=None, policyText=None, source="manual", **_):
    if _blank(name) or _blank(url):
        raise HttpError(400, "name and url are required")
    key = normalize_url(url)
    if db.get("SELECT 1 FROM programs WHERE normalized_url = ?", key):
        raise HttpError(409, f"a program for {key} already exists")
    platform = platform.strip() if isinstance(platform, str) and platform.strip() else None
    row_id, _ = db.run(
        "INSERT INTO programs (name, platform, url, normalized_url, policy_text, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        name.strip(),
        platform,
        url.strip(),
        key,
        redact(clip(policyText if isinstance(policyText, str) else "")),
        source,
        now_iso(),
    )
    return row_id


def _assert_undecided_lead(db, normalized_url):
    latest = db.get("SELECT * FROM program_leads WHERE normalized_url = ? ORDER BY id DESC LIMIT 1", normalized_url)
    if not latest:
        raise HttpError(404, f"no lead for {normalized_url}")
    if db.get("SELECT 1 FROM lead_decisions WHERE normalized_url = ?", normalized_url):
        raise HttpError(409, f"lead {normalized_url} was already decided")
    return latest


def track_lead(db, normalized_url):
    """Promote a lead to a tracked program (or link it to an existing one with the same URL)."""
    with db.transaction():
        lead = _assert_undecided_lead(db, normalized_url)
        existing = db.get("SELECT id FROM programs WHERE normalized_url = ?", normalized_url)
        program_id = (
            existing["id"]
            if existing
            else add_program(db, name=lead["name"], url=lead["url"], platform=lead["platform"], policyText="", source="lead")
        )
        db.run(
            "INSERT INTO lead_decisions (normalized_url, decision, program_id, decided_at) VALUES (?, 'tracked', ?, ?)",
            normalized_url,
            program_id,
            now_iso(),
        )
        return program_id


def dismiss_lead(db, normalized_url):
    with db.transaction():
        _assert_undecided_lead(db, normalized_url)
        db.run("INSERT INTO lead_decisions (normalized_url, decision, decided_at) VALUES (?, 'dismissed', ?)", normalized_url, now_iso())


def _undecided_proposal(db, proposal_id):
    p = db.get("SELECT * FROM scope_proposals WHERE id = ?", proposal_id)
    if not p:
        raise HttpError(404, f"no proposal {proposal_id}")
    if db.get("SELECT 1 FROM proposal_decisions WHERE proposal_id = ?", proposal_id):
        raise HttpError(409, f"proposal {proposal_id} was already decided")
    return p


def confirm_proposal(db, proposal_id):
    """The only way a scope snapshot (the authorization basis) comes into existence."""
    with db.transaction():
        p = _undecided_proposal(db, proposal_id)
        now = now_iso()
        snap_id, _ = db.run(
            "INSERT INTO scope_snapshots (program_id, proposal_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?, ?, ?, ?, ?, ?)",
            p["program_id"],
            p["id"],
            p["in_scope"],
            p["out_of_scope"],
            p["exclusions"],
            now,
        )
        db.run("INSERT INTO proposal_decisions (proposal_id, decision, decided_at) VALUES (?, 'confirmed', ?)", p["id"], now)
        return snap_id


def reject_proposal(db, proposal_id):
    with db.transaction():
        _undecided_proposal(db, proposal_id)
        db.run("INSERT INTO proposal_decisions (proposal_id, decision, decided_at) VALUES (?, 'rejected', ?)", proposal_id, now_iso())


def _unique(values):
    return list(dict.fromkeys(values))


def _lead_details(db, lead):
    rows = db.all("SELECT agent, run_id, created_at FROM program_leads WHERE normalized_url = ? ORDER BY id", lead["normalized_url"])
    return {
        "normalizedUrl": lead["normalized_url"],
        "name": lead["name"],
        "platform": lead["platform"],
        "url": lead["url"],
        "foundVia": lead["found_via"],
        "scopeSummary": lead["scope_summary"],
        "sightings": lead["sightings"],
        "agents": _unique(r["agent"] for r in rows),
        "runIds": _unique(r["run_id"] for r in rows if r["run_id"]),
        "firstSeen": rows[0]["created_at"] if rows else None,
        "lastSeen": rows[-1]["created_at"] if rows else None,
    }


def _open_proposals(db, program_id):
    rows = db.all(
        """SELECT p.* FROM scope_proposals p
           WHERE p.program_id = ? AND NOT EXISTS (SELECT 1 FROM proposal_decisions d WHERE d.proposal_id = p.id)
           ORDER BY p.id DESC""",
        program_id,
    )
    return [
        {
            "id": p["id"],
            "agent": p["agent"],
            "runId": p["run_id"],
            "createdAt": p["created_at"],
            "inScope": parse_json(p["in_scope"], []),
            "outOfScope": parse_json(p["out_of_scope"], []),
            "exclusions": parse_json(p["exclusions"], []),
            "sourceExcerpt": p["source_excerpt"],
        }
        for p in rows
    ]


def _program_shape(p):
    return {
        "id": p["id"],
        "name": p["name"],
        "platform": p["platform"],
        "url": p["url"],
        "normalizedUrl": p["normalized_url"],
        "source": p["source"],
        "createdAt": p["created_at"],
    }


def _epoch_ms(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000


def list_bounties(db, now=None):
    """The whole pipeline in the shapes the Bounties page renders."""
    now = now if now is not None else time.time() * 1000
    stages = list_programs(db)

    def policy(pid):
        row = db.get("SELECT policy_text FROM programs WHERE id = ?", pid)
        return row["policy_text"] if row else ""

    return {
        "leads": [_lead_details(db, lead) for lead in stages["leads"]],
        "tracked": [{**_program_shape(p), "policyText": policy(p["id"]), "proposals": _open_proposals(db, p["id"])} for p in stages["tracked"]],
        "confirmed": [
            {
                **_program_shape(p),
                "proposals": _open_proposals(db, p["id"]),
                "snapshot": {
                    "id": p["scope"]["id"],
                    "inScope": p["scope"]["in_scope"],
                    "outOfScope": p["scope"]["out_of_scope"],
                    "exclusions": p["scope"]["exclusions"],
                    "confirmedAt": p["scope"]["confirmed_at"],
                    "stale": now - _epoch_ms(p["scope"]["confirmed_at"]) > STALE_MS,
                },
            }
            for p in stages["confirmed"]
        ],
    }


def require_confirmed_snapshot(db, program_id):
    """Latest confirmed snapshot id for a program, or raise 400 — used to link a run."""
    try:
        pid = int(program_id)
    except (TypeError, ValueError):
        raise HttpError(400, f"program {program_id} has no confirmed scope") from None
    snap = db.get("SELECT id FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC, id DESC LIMIT 1", pid)
    if not snap:
        raise HttpError(400, f"program {program_id} has no confirmed scope")
    return snap["id"]
