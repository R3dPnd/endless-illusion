import { Router } from "express";
import { readFileSync } from "node:fs";
import path from "node:path";
import { getRun, listRuns } from "../db/archive.mjs";
import { HttpError } from "../db/bounties.mjs";
import { handle } from "./routes-bounties.mjs";

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const current = (table) => `NOT EXISTS (SELECT 1 FROM ${table} s WHERE s.supersedes = t.id)`;
const parse = (s, fallback) => {
  try {
    return JSON.parse(s);
  } catch {
    return fallback;
  }
};

function findings(db) {
  const rows = ["web", "api"].flatMap((kind) =>
    db.prepare(`SELECT * FROM ${kind}_findings t WHERE ${current(`${kind}_findings`)}`).all().map((r) => ({ ...r, kind })),
  );
  return rows.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.created_at.localeCompare(a.created_at));
}

function cveNotes(db) {
  return db
    .prepare(`SELECT * FROM cve_notes t WHERE ${current("cve_notes")} ORDER BY t.created_at DESC`)
    .all()
    .map((r) => ({ ...r, kev: !!r.kev, public_exploit: !!r.public_exploit, sources: parse(r.sources, []) }));
}

function submissions(db) {
  return db
    .prepare(
      `SELECT t.*, p.name AS program_name, p.url AS program_url FROM submissions t
       JOIN programs p ON p.id = t.program_id
       WHERE ${current("submissions")} ORDER BY t.created_at DESC`,
    )
    .all()
    .map((r) => ({ ...r, finding_refs: parse(r.finding_refs, []) }));
}

/** Fill the engagement-report header for a submission and append Sen's body. */
function exportSubmission(db, repoRoot, id) {
  const sub = submissions(db).find((s) => s.id === id);
  if (!sub) throw new HttpError(404, `no submission ${id}`);
  const snap = db
    .prepare("SELECT id, confirmed_at FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC LIMIT 1")
    .get(sub.program_id);
  const template = readFileSync(path.join(repoRoot, "templates", "engagement-report.md"), "utf8");
  const header = template.slice(0, template.indexOf("## Summary")).trimEnd();
  const filled = header
    .replace("<name>", `${sub.program_name} — ${sub.title}`)
    .replace("<YYYY-MM-DD>", sub.created_at.slice(0, 10))
    .replace("<codenames>", sub.agent)
    .replace("<in-scope assets>", sub.program_url)
    .replace(
      "<contract / bounty program + link / written permission reference>",
      snap ? `${sub.program_name} (${sub.program_url}), scope snapshot #${snap.id} confirmed ${snap.confirmed_at.slice(0, 10)}` : `${sub.program_name} (${sub.program_url}) — no confirmed scope snapshot`,
    )
    .replace("<summary>", "See program scope snapshot.");
  return `${filled}\n\n## ${sub.title}\n\n- **Severity:** ${sub.severity}\n\n${sub.body_markdown}\n`;
}

export function archiveRoutes(db, repoRoot) {
  const r = Router();
  r.get("/runs", handle((req) => listRuns(db, req.query)));
  r.get(
    "/runs/:id",
    handle((req) => {
      const run = getRun(db, req.params.id);
      if (!run) throw new HttpError(404, "no such run");
      const reports = db.prepare("SELECT id, agent, kind, text, meta, created_at FROM reports WHERE run_id = ? ORDER BY id").all(run.id);
      return { ...run, reports: reports.map((x) => ({ ...x, meta: parse(x.meta, null) })) };
    }),
  );
  r.get("/findings", handle(() => findings(db)));
  r.get("/cve-notes", handle(() => cveNotes(db)));
  r.get("/submissions", handle(() => submissions(db)));
  r.get("/submissions/:id/export", (req, res) => {
    try {
      const md = exportSubmission(db, repoRoot, Number(req.params.id));
      res.type("text/markdown").set("Content-Disposition", `attachment; filename="submission-${req.params.id}.md"`).send(md);
    } catch (err) {
      res.status(err instanceof HttpError ? err.status : 500).json({ error: err.message });
    }
  });
  return r;
}
