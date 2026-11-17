"""
The hub's record of every run: the run row, its raw event stream, and the
reports extracted from it. Written by the server only — never by agents.
"""

import json
import re
import time

from . import now_iso
from .redact import clip, redact, redact_deep


def _clean(s):
    return redact(clip(str(s if s is not None else "")))


def to_json(value):
    """Compact JSON matching JSON.stringify, so stored rows read the same from either side."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def create_run(db, run):
    db.run(
        """INSERT INTO runs (id, agent, task, scope, authorization, active_engaged, tools, status, program_id, snapshot_id, started_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
        run["id"],
        run["agent"],
        _clean(run.get("task")),
        _clean(run.get("scope")),
        _clean(run.get("authorization")),
        1 if run.get("activeEngaged") else 0,
        to_json(run.get("tools") or []),
        run.get("programId"),
        run.get("snapshotId"),
        now_iso(),
    )


def append_event(db, run_id, seq, evt):
    """Append one stream event. Each string inside is redacted before serializing, so the JSON stays valid."""
    stored = to_json(redact_deep(evt))
    db.run("INSERT INTO run_events (run_id, seq, ts, event) VALUES (?, ?, ?, ?)", run_id, seq, evt.get("ts") or int(time.time() * 1000), stored)


def add_report(db, run_id, agent, kind, text, meta=None):
    row_id, _ = db.run(
        "INSERT INTO reports (run_id, agent, kind, text, meta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        run_id,
        agent,
        kind,
        _clean(text),
        to_json(meta) if meta else None,
        now_iso(),
    )
    return {"id": row_id}


def finish_run(db, run_id, status, cost_usd=None, duration_ms=None):
    db.run("UPDATE runs SET status = ?, cost_usd = ?, duration_ms = ?, ended_at = ? WHERE id = ?", status, cost_usd, duration_ms, now_iso(), run_id)


def mark_interrupted(db):
    """Runs still marked running when the server starts can't be live: mark them interrupted."""
    _, changes = db.run("UPDATE runs SET status = 'interrupted', ended_at = ? WHERE status = 'running'", now_iso())
    return changes


def _to_run(row):
    if not row:
        return None
    return {**row, "active_engaged": bool(row["active_engaged"]), "tools": json.loads(row["tools"])}


def get_run(db, run_id):
    return _to_run(db.get("SELECT * FROM runs WHERE id = ?", run_id))


def _int_or(value, fallback):
    try:
        n = int(float(value))
        return n or fallback
    except (TypeError, ValueError):
        return fallback


def list_runs(db, agent=None, status=None, programId=None, q=None, limit=50, **_):
    where, params = [], []
    if agent:
        where.append("agent = ?")
        params.append(agent)
    if status:
        where.append("status = ?")
        params.append(status)
    if programId:
        where.append("program_id = ?")
        params.append(_int_or(programId, 0))
    if q:
        where.append("(task LIKE ? ESCAPE '\\' OR scope LIKE ? ESCAPE '\\')")
        like = "%" + re.sub(r"[\\%_]", lambda m: "\\" + m.group(0), str(q)) + "%"
        params += [like, like]
    sql = f"SELECT * FROM runs {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY started_at DESC, rowid DESC LIMIT ?"
    return [_to_run(r) for r in db.all(sql, *params, min(_int_or(limit, 50), 200))]


def get_run_events(db, run_id):
    return [json.loads(r["event"]) for r in db.all("SELECT event FROM run_events WHERE run_id = ? ORDER BY seq", run_id)]
