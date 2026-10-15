/**
 * Read helpers shared by the MCP server and the hub API. Agent tables are
 * append-only, so "current" rows are those no later row supersedes.
 */

const MAX_FIELD = 4000;

const SEARCH_SOURCES = {
  report: "reports",
  web_finding: "web_findings",
  api_finding: "api_findings",
  cve_note: "cve_notes",
  exploit_analysis: "exploit_analyses",
  submission: "submissions",
};

const current = (table, alias = "t") =>
  `NOT EXISTS (SELECT 1 FROM ${table} s WHERE s.supersedes = ${alias}.id)`;

/** Shorten long text fields so tool results stay small. */
function trimRow(row) {
  if (!row) return row;
  const out = { ...row };
  for (const [k, v] of Object.entries(out)) {
    if (typeof v === "string" && v.length > MAX_FIELD) out[k] = `${v.slice(0, MAX_FIELD)}…[truncated]`;
  }
  return out;
}

const parseJson = (s, fallback) => {
  try {
    return JSON.parse(s);
  } catch {
    return fallback;
  }
};

const likeEscape = (s) => s.replace(/[\\%_]/g, (c) => `\\${c}`);

/** Everything already known about a host, domain, product, or URL fragment. */
export function findPriorWork(db, target, limit = 20) {
  const needle = String(target ?? "").trim();
  const empty = { assets: [], observations: [], web_findings: [], api_findings: [], api_endpoints: [], cve_notes: [], program_leads: [] };
  if (!needle) return empty;
  const like = `%${likeEscape(needle)}%`;
  const q = (table, cols) =>
    db
      .prepare(
        `SELECT * FROM ${table} t WHERE (${cols.map((c) => `t.${c} LIKE ? ESCAPE '\\'`).join(" OR ")}) AND ${current(table)}
         ORDER BY t.id DESC LIMIT ?`,
      )
      .all(...cols.map(() => like), limit)
      .map(trimRow);
  return {
    assets: q("assets", ["host"]),
    observations: q("asset_observations", ["asset_host", "technology"]),
    web_findings: q("web_findings", ["target", "title"]),
    api_findings: q("api_findings", ["target", "title"]),
    api_endpoints: q("api_endpoints", ["base_url", "path"]),
    cve_notes: q("cve_notes", ["product", "cve_id"]),
    program_leads: q("program_leads", ["url", "name"]),
  };
}

/** Turn free text into a safe FTS5 query: each word becomes a quoted term. */
function toFtsQuery(query) {
  const words = String(query ?? "").match(/[\p{L}\p{N}_.-]+/gu) ?? [];
  return words.map((w) => `"${w}"`).join(" ");
}

/** Full-text search over reports and structured records, newest-relevant first. */
export function searchReports(db, { query, agent, since, limit = 20 }) {
  const fts = toFtsQuery(query);
  if (!fts) return [];
  const hits = db
    .prepare(
      `SELECT kind, ref_id, title, snippet(search_fts, 3, '[', ']', '…', 16) AS snippet
       FROM search_fts WHERE search_fts MATCH ? ORDER BY rank LIMIT 200`,
    )
    .all(fts);
  const results = [];
  for (const hit of hits) {
    const table = SEARCH_SOURCES[hit.kind];
    const src = db.prepare(`SELECT agent, run_id, created_at FROM ${table} WHERE id = ?`).get(hit.ref_id);
    if (!src) continue;
    if (agent && src.agent !== agent) continue;
    if (since && src.created_at < since) continue;
    results.push({ kind: hit.kind, id: Number(hit.ref_id), title: hit.title, snippet: hit.snippet, ...src });
    if (results.length >= limit) break;
  }
  return results;
}

export function getReport(db, id) {
  return trimRow(db.prepare("SELECT * FROM reports WHERE id = ?").get(id) ?? null);
}

/** Current note for a CVE id (case-insensitive), with sources parsed. */
export function getCveNote(db, cveId) {
  const row = db
    .prepare(`SELECT * FROM cve_notes t WHERE upper(t.cve_id) = upper(?) AND ${current("cve_notes")} ORDER BY t.id DESC LIMIT 1`)
    .get(String(cveId ?? ""));
  if (!row) return null;
  return trimRow({ ...row, kev: !!row.kev, public_exploit: !!row.public_exploit, sources: parseJson(row.sources, []) });
}

function findProgram(db, ref) {
  if (Number.isInteger(ref) || /^\d+$/.test(String(ref))) {
    return db.prepare("SELECT * FROM programs WHERE id = ?").get(Number(ref)) ?? null;
  }
  const s = String(ref ?? "").trim().toLowerCase();
  if (!s) return null;
  return (
    db.prepare("SELECT * FROM programs WHERE lower(name) = ? OR normalized_url = ?").get(s, s) ??
    db.prepare("SELECT * FROM programs WHERE normalized_url LIKE ? ESCAPE '\\' ORDER BY id LIMIT 1").get(`%${likeEscape(s)}%`) ??
    null
  );
}

function latestSnapshot(db, programId) {
  const snap = db
    .prepare("SELECT * FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC, id DESC LIMIT 1")
    .get(programId);
  if (!snap) return null;
  return {
    id: snap.id,
    proposal_id: snap.proposal_id,
    in_scope: parseJson(snap.in_scope, []),
    out_of_scope: parseJson(snap.out_of_scope, []),
    exclusions: parseJson(snap.exclusions, []),
    confirmed_at: snap.confirmed_at,
  };
}

/** The operator-confirmed scope for a program. Proposals are never returned. */
export function getScope(db, programRef) {
  const program = findProgram(db, programRef);
  if (!program) return { program: null, confirmed: null };
  return {
    program: { id: program.id, name: program.name, url: program.url, platform: program.platform },
    confirmed: latestSnapshot(db, program.id),
  };
}

function listLeads(db) {
  return db
    .prepare(
      `SELECT l.normalized_url, l.name, l.platform, l.url, l.found_via, l.scope_summary,
              (SELECT count(*) FROM program_leads x WHERE x.normalized_url = l.normalized_url) AS sightings,
              l.created_at
       FROM program_leads l
       WHERE NOT EXISTS (SELECT 1 FROM lead_decisions d WHERE d.normalized_url = l.normalized_url)
         AND l.id = (SELECT max(id) FROM program_leads x WHERE x.normalized_url = l.normalized_url)
       ORDER BY l.id DESC`,
    )
    .all()
    .map(trimRow);
}

/** Programs by pipeline stage: "leads", "tracked", or "confirmed"; all three when omitted. */
export function listPrograms(db, stage) {
  const programs = db.prepare("SELECT id, name, platform, url, normalized_url, source, created_at FROM programs ORDER BY id").all();
  const withScope = programs.map((p) => ({ ...p, scope: latestSnapshot(db, p.id) }));
  const stages = {
    leads: () => listLeads(db),
    tracked: () => withScope.filter((p) => !p.scope).map(({ scope, ...p }) => p),
    confirmed: () => withScope.filter((p) => p.scope),
  };
  if (stage) {
    if (!stages[stage]) throw new Error(`unknown stage ${stage}`);
    return stages[stage]();
  }
  return { leads: stages.leads(), tracked: stages.tracked(), confirmed: stages.confirmed() };
}
