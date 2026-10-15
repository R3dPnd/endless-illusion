import { nowIso } from "./index.mjs";
import { listPrograms } from "./read.mjs";
import { clip, redact } from "./redact.mjs";
import { normalizeUrl } from "./url.mjs";

/**
 * Operator actions on the bounty pipeline (called from the UI only):
 * lead → tracked program → confirmed scope snapshot. Agents can only add
 * leads and proposals; nothing here is reachable from an MCP tool.
 */

export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const STALE_MS = 30 * 24 * 60 * 60 * 1000;

const parse = (s, fallback) => {
  try {
    return JSON.parse(s);
  } catch {
    return fallback;
  }
};

function transaction(db, fn) {
  db.exec("BEGIN IMMEDIATE");
  try {
    const out = fn();
    db.exec("COMMIT");
    return out;
  } catch (err) {
    db.exec("ROLLBACK");
    throw err;
  }
}

export function addProgram(db, { name, url, platform, policyText, source = "manual" }) {
  if (!name?.trim() || !url?.trim()) throw new HttpError(400, "name and url are required");
  const key = normalizeUrl(url);
  if (db.prepare("SELECT 1 FROM programs WHERE normalized_url = ?").get(key)) {
    throw new HttpError(409, `a program for ${key} already exists`);
  }
  const r = db
    .prepare("INSERT INTO programs (name, platform, url, normalized_url, policy_text, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .run(name.trim(), platform?.trim() || null, url.trim(), key, redact(clip(policyText ?? "")), source, nowIso());
  return Number(r.lastInsertRowid);
}

function assertUndecidedLead(db, normalizedUrl) {
  const latest = db.prepare("SELECT * FROM program_leads WHERE normalized_url = ? ORDER BY id DESC LIMIT 1").get(normalizedUrl);
  if (!latest) throw new HttpError(404, `no lead for ${normalizedUrl}`);
  if (db.prepare("SELECT 1 FROM lead_decisions WHERE normalized_url = ?").get(normalizedUrl)) {
    throw new HttpError(409, `lead ${normalizedUrl} was already decided`);
  }
  return latest;
}

/** Promote a lead to a tracked program (or link it to an existing one with the same URL). */
export function trackLead(db, normalizedUrl) {
  return transaction(db, () => {
    const lead = assertUndecidedLead(db, normalizedUrl);
    const existing = db.prepare("SELECT id FROM programs WHERE normalized_url = ?").get(normalizedUrl);
    const programId = existing
      ? existing.id
      : addProgram(db, { name: lead.name, url: lead.url, platform: lead.platform, policyText: "", source: "lead" });
    db.prepare("INSERT INTO lead_decisions (normalized_url, decision, program_id, decided_at) VALUES (?, 'tracked', ?, ?)").run(
      normalizedUrl,
      programId,
      nowIso(),
    );
    return programId;
  });
}

export function dismissLead(db, normalizedUrl) {
  return transaction(db, () => {
    assertUndecidedLead(db, normalizedUrl);
    db.prepare("INSERT INTO lead_decisions (normalized_url, decision, decided_at) VALUES (?, 'dismissed', ?)").run(normalizedUrl, nowIso());
  });
}

function undecidedProposal(db, proposalId) {
  const p = db.prepare("SELECT * FROM scope_proposals WHERE id = ?").get(proposalId);
  if (!p) throw new HttpError(404, `no proposal ${proposalId}`);
  if (db.prepare("SELECT 1 FROM proposal_decisions WHERE proposal_id = ?").get(proposalId)) {
    throw new HttpError(409, `proposal ${proposalId} was already decided`);
  }
  return p;
}

/** The only way a scope snapshot (the authorization basis) comes into existence. */
export function confirmProposal(db, proposalId) {
  return transaction(db, () => {
    const p = undecidedProposal(db, proposalId);
    const now = nowIso();
    const r = db
      .prepare("INSERT INTO scope_snapshots (program_id, proposal_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?, ?, ?, ?, ?, ?)")
      .run(p.program_id, p.id, p.in_scope, p.out_of_scope, p.exclusions, now);
    db.prepare("INSERT INTO proposal_decisions (proposal_id, decision, decided_at) VALUES (?, 'confirmed', ?)").run(p.id, now);
    return Number(r.lastInsertRowid);
  });
}

export function rejectProposal(db, proposalId) {
  return transaction(db, () => {
    undecidedProposal(db, proposalId);
    db.prepare("INSERT INTO proposal_decisions (proposal_id, decision, decided_at) VALUES (?, 'rejected', ?)").run(proposalId, nowIso());
  });
}

function leadDetails(db, lead) {
  const rows = db.prepare("SELECT agent, run_id, created_at FROM program_leads WHERE normalized_url = ? ORDER BY id").all(lead.normalized_url);
  return {
    normalizedUrl: lead.normalized_url,
    name: lead.name,
    platform: lead.platform,
    url: lead.url,
    foundVia: lead.found_via,
    scopeSummary: lead.scope_summary,
    sightings: lead.sightings,
    agents: [...new Set(rows.map((r) => r.agent))],
    runIds: [...new Set(rows.map((r) => r.run_id).filter(Boolean))],
    firstSeen: rows[0]?.created_at,
    lastSeen: rows.at(-1)?.created_at,
  };
}

function openProposals(db, programId) {
  return db
    .prepare(
      `SELECT p.* FROM scope_proposals p
       WHERE p.program_id = ? AND NOT EXISTS (SELECT 1 FROM proposal_decisions d WHERE d.proposal_id = p.id)
       ORDER BY p.id DESC`,
    )
    .all(programId)
    .map((p) => ({
      id: p.id,
      agent: p.agent,
      runId: p.run_id,
      createdAt: p.created_at,
      inScope: parse(p.in_scope, []),
      outOfScope: parse(p.out_of_scope, []),
      exclusions: parse(p.exclusions, []),
      sourceExcerpt: p.source_excerpt,
    }));
}

const programShape = (p) => ({ id: p.id, name: p.name, platform: p.platform, url: p.url, normalizedUrl: p.normalized_url, source: p.source, createdAt: p.created_at });

/** The whole pipeline in the shapes the Bounties page renders. */
export function listBounties(db, now = Date.now()) {
  const { leads, tracked, confirmed } = listPrograms(db);
  const policy = (id) => db.prepare("SELECT policy_text FROM programs WHERE id = ?").get(id)?.policy_text ?? "";
  return {
    leads: leads.map((l) => leadDetails(db, l)),
    tracked: tracked.map((p) => ({ ...programShape(p), policyText: policy(p.id), proposals: openProposals(db, p.id) })),
    confirmed: confirmed.map((p) => ({
      ...programShape(p),
      proposals: openProposals(db, p.id),
      snapshot: {
        id: p.scope.id,
        inScope: p.scope.in_scope,
        outOfScope: p.scope.out_of_scope,
        exclusions: p.scope.exclusions,
        confirmedAt: p.scope.confirmed_at,
        stale: now - Date.parse(p.scope.confirmed_at) > STALE_MS,
      },
    })),
  };
}

/** Latest confirmed snapshot id for a program, or throw 400 — used to link a run. */
export function requireConfirmedSnapshot(db, programId) {
  const snap = db
    .prepare("SELECT id FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC, id DESC LIMIT 1")
    .get(Number(programId));
  if (!snap) throw new HttpError(400, `program ${programId} has no confirmed scope`);
  return snap.id;
}
