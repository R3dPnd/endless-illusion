import { nowIso } from "./index.mjs";
import { clip, redact, redactDeep } from "./redact.mjs";

/**
 * The hub's record of every run: the run row, its raw event stream, and the
 * reports extracted from it. Written by the server only — never by agents.
 */

const clean = (s) => redact(clip(String(s ?? "")));

export function createRun(db, run) {
  db.prepare(
    `INSERT INTO runs (id, agent, task, scope, authorization, active_engaged, tools, status, program_id, snapshot_id, started_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)`,
  ).run(
    run.id,
    run.agent,
    clean(run.task),
    clean(run.scope),
    clean(run.authorization),
    run.activeEngaged ? 1 : 0,
    JSON.stringify(run.tools ?? []),
    run.programId ?? null,
    run.snapshotId ?? null,
    nowIso(),
  );
}

/** Append one stream event. Each string inside is redacted before serializing, so the JSON stays valid. */
export function appendEvent(db, runId, seq, evt) {
  const stored = JSON.stringify(redactDeep(evt));
  db.prepare("INSERT INTO run_events (run_id, seq, ts, event) VALUES (?, ?, ?, ?)").run(runId, seq, evt.ts ?? Date.now(), stored);
}

export function addReport(db, { runId, agent, kind, text, meta }) {
  const r = db
    .prepare("INSERT INTO reports (run_id, agent, kind, text, meta, created_at) VALUES (?, ?, ?, ?, ?, ?)")
    .run(runId, agent, kind, clean(text), meta ? JSON.stringify(meta) : null, nowIso());
  return { id: Number(r.lastInsertRowid) };
}

export function finishRun(db, runId, { status, costUsd, durationMs }) {
  db.prepare("UPDATE runs SET status = ?, cost_usd = ?, duration_ms = ?, ended_at = ? WHERE id = ?").run(
    status,
    costUsd ?? null,
    durationMs ?? null,
    nowIso(),
    runId,
  );
}

/** Runs still marked running when the server starts can't be live: mark them interrupted. */
export function markInterrupted(db) {
  const r = db.prepare("UPDATE runs SET status = 'interrupted', ended_at = ? WHERE status = 'running'").run(nowIso());
  return Number(r.changes);
}

const toRun = (row) => (row ? { ...row, active_engaged: !!row.active_engaged, tools: JSON.parse(row.tools) } : null);

export function getRun(db, id) {
  return toRun(db.prepare("SELECT * FROM runs WHERE id = ?").get(id));
}

export function listRuns(db, { agent, status, programId, q, limit = 50 } = {}) {
  const where = [];
  const params = [];
  const add = (clause, value) => {
    where.push(clause);
    params.push(value);
  };
  if (agent) add("agent = ?", agent);
  if (status) add("status = ?", status);
  if (programId) add("program_id = ?", Number(programId));
  if (q) {
    where.push("(task LIKE ? ESCAPE '\\' OR scope LIKE ? ESCAPE '\\')");
    const like = `%${String(q).replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
    params.push(like, like);
  }
  const sql = `SELECT * FROM runs ${where.length ? `WHERE ${where.join(" AND ")}` : ""} ORDER BY started_at DESC, rowid DESC LIMIT ?`;
  return db.prepare(sql).all(...params, Math.min(Number(limit) || 50, 200)).map(toRun);
}

export function getRunEvents(db, id) {
  return db
    .prepare("SELECT event FROM run_events WHERE run_id = ? ORDER BY seq")
    .all(id)
    .map((r) => JSON.parse(r.event));
}
