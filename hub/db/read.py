"""
Read helpers shared by the MCP server and the hub API. Agent tables are
append-only, so "current" rows are those no later row supersedes.
"""

import json
import re

MAX_FIELD = 4000

SEARCH_SOURCES = {
    "report": "reports",
    "web_finding": "web_findings",
    "api_finding": "api_findings",
    "cve_note": "cve_notes",
    "exploit_analysis": "exploit_analyses",
    "submission": "submissions",
}


def current(table, alias="t"):
    return f"NOT EXISTS (SELECT 1 FROM {table} s WHERE s.supersedes = {alias}.id)"


def trim_row(row):
    """Shorten long text fields so tool results stay small."""
    if not row:
        return row
    return {k: (f"{v[:MAX_FIELD]}…[truncated]" if isinstance(v, str) and len(v) > MAX_FIELD else v) for k, v in row.items()}


def parse_json(s, fallback):
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return fallback


def like_escape(s):
    return re.sub(r"[\\%_]", lambda m: "\\" + m.group(0), s)


def find_prior_work(db, target, limit=20):
    """Everything already known about a host, domain, product, or URL fragment."""
    needle = str(target if target is not None else "").strip()
    empty = {k: [] for k in ("assets", "observations", "web_findings", "api_findings", "api_endpoints", "cve_notes", "program_leads")}
    if not needle:
        return empty
    like = f"%{like_escape(needle)}%"

    def q(table, cols):
        where = " OR ".join(f"t.{c} LIKE ? ESCAPE '\\'" for c in cols)
        sql = f"SELECT * FROM {table} t WHERE ({where}) AND {current(table)} ORDER BY t.id DESC LIMIT ?"
        return [trim_row(r) for r in db.all(sql, *([like] * len(cols)), limit)]

    return {
        "assets": q("assets", ["host"]),
        "observations": q("asset_observations", ["asset_host", "technology"]),
        "web_findings": q("web_findings", ["target", "title"]),
        "api_findings": q("api_findings", ["target", "title"]),
        "api_endpoints": q("api_endpoints", ["base_url", "path"]),
        "cve_notes": q("cve_notes", ["product", "cve_id"]),
        "program_leads": q("program_leads", ["url", "name"]),
    }


def to_fts_query(query):
    """Turn free text into a safe FTS5 query: each word becomes a quoted term."""
    words = re.findall(r"[\w.-]+", str(query or ""))
    return " ".join(f'"{w}"' for w in words)


def search_reports(db, query, agent=None, since=None, limit=20):
    """Full-text search over reports and structured records, newest-relevant first."""
    fts = to_fts_query(query)
    if not fts:
        return []
    hits = db.all(
        "SELECT kind, ref_id, title, snippet(search_fts, 3, '[', ']', '…', 16) AS snippet "
        "FROM search_fts WHERE search_fts MATCH ? ORDER BY rank LIMIT 200",
        fts,
    )
    results = []
    for hit in hits:
        table = SEARCH_SOURCES.get(hit["kind"])
        src = table and db.get(f"SELECT agent, run_id, created_at FROM {table} WHERE id = ?", hit["ref_id"])
        if not src:
            continue
        if agent and src["agent"] != agent:
            continue
        if since and src["created_at"] < since:
            continue
        results.append({"kind": hit["kind"], "id": int(hit["ref_id"]), "title": hit["title"], "snippet": hit["snippet"], **src})
        if len(results) >= limit:
            break
    return results


def get_report(db, report_id):
    return trim_row(db.get("SELECT * FROM reports WHERE id = ?", report_id))


def get_cve_note(db, cve_id):
    """Current note for a CVE id (case-insensitive), with sources parsed."""
    row = db.get(
        f"SELECT * FROM cve_notes t WHERE upper(t.cve_id) = upper(?) AND {current('cve_notes')} ORDER BY t.id DESC LIMIT 1",
        str(cve_id or ""),
    )
    if not row:
        return None
    return trim_row({**row, "kev": bool(row["kev"]), "public_exploit": bool(row["public_exploit"]), "sources": parse_json(row["sources"], [])})


def _find_program(db, ref):
    if (isinstance(ref, int) and not isinstance(ref, bool)) or re.fullmatch(r"\d+", str(ref)):
        return db.get("SELECT * FROM programs WHERE id = ?", int(ref))
    s = str(ref or "").strip().lower()
    if not s:
        return None
    return db.get("SELECT * FROM programs WHERE lower(name) = ? OR normalized_url = ?", s, s) or db.get(
        "SELECT * FROM programs WHERE normalized_url LIKE ? ESCAPE '\\' ORDER BY id LIMIT 1", f"%{like_escape(s)}%"
    )


def latest_snapshot(db, program_id):
    snap = db.get("SELECT * FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC, id DESC LIMIT 1", program_id)
    if not snap:
        return None
    return {
        "id": snap["id"],
        "proposal_id": snap["proposal_id"],
        "in_scope": parse_json(snap["in_scope"], []),
        "out_of_scope": parse_json(snap["out_of_scope"], []),
        "exclusions": parse_json(snap["exclusions"], []),
        "confirmed_at": snap["confirmed_at"],
    }


def get_scope(db, program_ref):
    """The operator-confirmed scope for a program. Proposals are never returned."""
    program = _find_program(db, program_ref)
    if not program:
        return {"program": None, "confirmed": None}
    return {
        "program": {k: program[k] for k in ("id", "name", "url", "platform")},
        "confirmed": latest_snapshot(db, program["id"]),
    }


def _list_leads(db):
    rows = db.all(
        """SELECT l.normalized_url, l.name, l.platform, l.url, l.found_via,
                  coalesce((SELECT x.scope_summary FROM program_leads x
                            WHERE x.normalized_url = l.normalized_url AND x.scope_summary <> ''
                            ORDER BY x.id DESC LIMIT 1), '') AS scope_summary,
                  (SELECT count(*) FROM program_leads x WHERE x.normalized_url = l.normalized_url) AS sightings,
                  l.created_at
           FROM program_leads l
           WHERE NOT EXISTS (SELECT 1 FROM lead_decisions d WHERE d.normalized_url = l.normalized_url)
             AND l.id = (SELECT max(id) FROM program_leads x WHERE x.normalized_url = l.normalized_url)
           ORDER BY l.id DESC"""
    )
    return [trim_row(r) for r in rows]


STAGES = ("leads", "tracked", "confirmed")


def list_programs(db, stage=None):
    """Programs by pipeline stage: "leads", "tracked", or "confirmed"; all three when omitted."""
    if stage and stage not in STAGES:
        raise ValueError(f"unknown stage {stage}")
    programs = db.all("SELECT id, name, platform, url, normalized_url, source, created_at FROM programs ORDER BY id")
    with_scope = [{**p, "scope": latest_snapshot(db, p["id"])} for p in programs]
    stages = {
        "leads": lambda: _list_leads(db),
        "tracked": lambda: [{k: v for k, v in p.items() if k != "scope"} for p in with_scope if not p["scope"]],
        "confirmed": lambda: [p for p in with_scope if p["scope"]],
    }
    if stage:
        return stages[stage]()
    return {name: fn() for name, fn in stages.items()}
