import { describe, it, expect, beforeEach } from "vitest";
import { openDb, nowIso } from "../db/index.mjs";
import { insertAgentRow } from "../db/write.mjs";
import { WRITE_TABLES } from "../db/tables.mjs";
import { OWNERSHIP } from "../db/ownership.mjs";
import { normalizeUrl } from "../db/url.mjs";
import { findPriorWork, searchReports, getCveNote, getScope, listPrograms } from "../db/read.mjs";

const DAHLIA = "dahlia-of-wednesday";
const SAUDADE = "saudade-of-sunday";
const DIABLO = "diablo-of-monday";
const SEN = "sen-of-saturday";

const cve = (over = {}) => ({
  cve_id: "CVE-2021-44228", product: "Apache Log4j", affected_versions: "2.0-beta9 to 2.14.1",
  kev: true, public_exploit: true, summary: "JNDI lookup RCE in nginx-fronted apps", sources: ["https://nvd.nist.gov"], ...over,
});

let db;
beforeEach(() => { db = openDb(":memory:"); });

function addProgram(name = "Acme", url = "https://hackerone.com/acme") {
  return Number(db.prepare("INSERT INTO programs(name, url, normalized_url, source, created_at) VALUES (?,?,?, 'manual', ?)")
    .run(name, url, normalizeUrl(url), nowIso()).lastInsertRowid);
}

describe("WRITE_TABLES", () => {
  it("defines a tool for every owned table", () => {
    for (const t of new Set(Object.values(OWNERSHIP).flat())) {
      expect(WRITE_TABLES[t]?.tool, t).toMatch(/^[a-z_]+$/);
    }
  });
});

describe("insertAgentRow", () => {
  it("stamps agent and run id", () => {
    const { id } = insertAgentRow(db, { agent: DAHLIA, runId: "run-1", table: "cve_notes", fields: cve() });
    const row = db.prepare("SELECT * FROM cve_notes WHERE id = ?").get(id);
    expect(row.agent).toBe(DAHLIA);
    expect(row.run_id).toBe("run-1");
    expect(row.kev).toBe(1);
    expect(JSON.parse(row.sources)).toEqual(["https://nvd.nist.gov"]);
  });

  it("refuses another agent's table", () => {
    expect(() => insertAgentRow(db, { agent: DAHLIA, runId: "r", table: "web_findings", fields: {} })).toThrow(/may not write/);
  });

  it("rejects unknown columns", () => {
    expect(() => insertAgentRow(db, { agent: DAHLIA, runId: "r", table: "cve_notes", fields: cve({ agent: "sen-of-saturday" }) })).toThrow(/unknown field/);
  });

  it("rejects bad enum values", () => {
    expect(() => insertAgentRow(db, { agent: DIABLO, runId: "r", table: "web_findings",
      fields: { target: "a.example", title: "x", status: "confirmed", severity: "apocalyptic", description: "d" } })).toThrow(/severity/);
  });

  it("rejects missing required fields", () => {
    expect(() => insertAgentRow(db, { agent: DAHLIA, runId: "r", table: "cve_notes", fields: { cve_id: "CVE-1" } })).toThrow(/required/);
  });

  it("redacts secrets in stored text", () => {
    const { id } = insertAgentRow(db, { agent: DIABLO, runId: "r", table: "web_findings", fields: {
      target: "app.example.com", title: "Token in response", status: "confirmed", severity: "high",
      description: "Response leaks Authorization: Bearer sk_live_123456", evidence: "password=hunter2" } });
    const row = db.prepare("SELECT description, evidence FROM web_findings WHERE id = ?").get(id);
    expect(row.description).not.toContain("sk_live_123456");
    expect(row.evidence).not.toContain("hunter2");
  });

  it("only supersedes an existing row in the same table", () => {
    expect(() => insertAgentRow(db, { agent: DAHLIA, runId: "r", table: "cve_notes", fields: cve({ supersedes: 999 }) })).toThrow(/supersedes/);
  });

  it("derives normalized_url for program leads", () => {
    const { id } = insertAgentRow(db, { agent: SAUDADE, runId: "r", table: "program_leads",
      fields: { name: "Acme", url: "https://HackerOne.com/acme/", found_via: "security.txt" } });
    expect(db.prepare("SELECT normalized_url FROM program_leads WHERE id = ?").get(id).normalized_url).toBe("hackerone.com/acme");
  });
});

describe("readers", () => {
  it("returns the latest note in a supersede chain", () => {
    const a = insertAgentRow(db, { agent: DAHLIA, runId: "r1", table: "cve_notes", fields: cve({ cvss: "9.0" }) });
    insertAgentRow(db, { agent: DAHLIA, runId: "r2", table: "cve_notes", fields: cve({ cvss: "10.0", supersedes: a.id }) });
    expect(getCveNote(db, "cve-2021-44228").cvss).toBe("10.0");
  });

  it("finds records by full-text search with agent filter", () => {
    insertAgentRow(db, { agent: DAHLIA, runId: "r1", table: "cve_notes", fields: cve() });
    const hits = searchReports(db, { query: "nginx" });
    expect(hits.map((h) => h.kind)).toContain("cve_note");
    expect(searchReports(db, { query: "nginx", agent: DIABLO })).toHaveLength(0);
  });

  it("tolerates FTS syntax characters in queries", () => {
    expect(() => searchReports(db, { query: 'log4j "AND (OR' })).not.toThrow();
  });

  it("finds prior work for a target across domains", () => {
    insertAgentRow(db, { agent: SAUDADE, runId: "r", table: "assets", fields: { host: "api.example.com", kind: "subdomain" } });
    insertAgentRow(db, { agent: DIABLO, runId: "r", table: "web_findings", fields: {
      target: "https://www.example.com/login", title: "Open redirect", status: "suspected", severity: "low", description: "d" } });
    insertAgentRow(db, { agent: SAUDADE, runId: "r", table: "program_leads", fields: { name: "Example", url: "https://example.com/security", found_via: "security.txt" } });
    const w = findPriorWork(db, "example.com");
    expect(w.assets).toHaveLength(1);
    expect(w.web_findings).toHaveLength(1);
    expect(w.program_leads).toHaveLength(1);
    expect(findPriorWork(db, "%").assets).toHaveLength(0);
  });

  it("never returns a proposal as scope", () => {
    const pid = addProgram();
    insertAgentRow(db, { agent: SEN, runId: "r", table: "scope_proposals", fields: {
      program_id: pid, in_scope: [{ asset: "*.acme.com", type: "wildcard" }], out_of_scope: [], exclusions: [] } });
    expect(getScope(db, pid).confirmed).toBeNull();
    db.prepare("INSERT INTO scope_snapshots(program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?,?,?,?,?)")
      .run(pid, '[{"asset":"app.acme.com","type":"domain"}]', "[]", "[]", nowIso());
    expect(getScope(db, "acme").confirmed.in_scope[0].asset).toBe("app.acme.com");
  });

  it("groups repeat lead sightings by normalized URL", () => {
    insertAgentRow(db, { agent: SAUDADE, runId: "r1", table: "program_leads", fields: { name: "Acme", url: "https://hackerone.com/acme", found_via: "security.txt" } });
    insertAgentRow(db, { agent: DAHLIA, runId: "r2", table: "program_leads", fields: { name: "Acme VDP", url: "https://www.HackerOne.com/acme/", found_via: "advisory" } });
    const leads = listPrograms(db, "leads");
    expect(leads).toHaveLength(1);
    expect(leads[0].sightings).toBe(2);
    expect(leads[0].name).toBe("Acme VDP");
  });

  it("keeps the latest non-empty scope summary across sightings", () => {
    insertAgentRow(db, { agent: SAUDADE, runId: "r1", table: "program_leads", fields: { name: "Acme", url: "https://hackerone.com/acme", found_via: "security.txt", scope_summary: "*.acme.com per policy" } });
    insertAgentRow(db, { agent: DAHLIA, runId: "r2", table: "program_leads", fields: { name: "Acme", url: "https://hackerone.com/acme", found_via: "advisory" } });
    expect(listPrograms(db, "leads")[0].scope_summary).toBe("*.acme.com per policy");
  });

  it("lists programs by stage", () => {
    insertAgentRow(db, { agent: DAHLIA, runId: "r", table: "program_leads", fields: { name: "Lead Co", url: "https://bugcrowd.com/leadco", found_via: "advisory" } });
    addProgram();
    expect(listPrograms(db, "leads").map((l) => l.name)).toEqual(["Lead Co"]);
    expect(listPrograms(db, "tracked").map((p) => p.name)).toEqual(["Acme"]);
    expect(listPrograms(db, "confirmed")).toEqual([]);
  });
});
