import { describe, it, expect } from "vitest";
import { mkdtempSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { openDb } from "../db/index.mjs";
import { migrate } from "../db/migrate.mjs";
import { OWNERSHIP, assertOwns, serverName } from "../db/ownership.mjs";
import { redact, clip } from "../db/redact.mjs";

const tableNames = (db) =>
  db.prepare("SELECT name FROM sqlite_master WHERE type IN ('table','virtual table') OR type='table'").all().map((r) => r.name);

describe("migrations", () => {
  it("sets user_version and is idempotent", () => {
    const db = openDb(":memory:");
    expect(db.prepare("PRAGMA user_version").get().user_version).toBe(1);
    expect(migrate(db)).toBe(1);
  });

  it("creates every owned table plus hub and operator tables", () => {
    const names = tableNames(openDb(":memory:"));
    const expected = new Set([
      ...Object.values(OWNERSHIP).flat(),
      "runs", "run_events", "reports",
      "programs", "lead_decisions", "proposal_decisions", "scope_snapshots",
      "search_fts",
    ]);
    for (const t of expected) expect(names).toContain(t);
  });
});

describe("on-disk database", () => {
  it("is created owner-only (0600) in WAL mode", () => {
    const file = path.join(mkdtempSync(path.join(tmpdir(), "ei-db-")), "data", "ei.db");
    const db = openDb(file);
    expect(statSync(file).mode & 0o777).toBe(0o600);
    expect(db.prepare("PRAGMA journal_mode").get().journal_mode).toBe("wal");
  });
});

describe("ownership", () => {
  it("allows an agent its own tables only", () => {
    expect(() => assertOwns("dahlia-of-wednesday", "cve_notes")).not.toThrow();
    expect(() => assertOwns("dahlia-of-wednesday", "web_findings")).toThrow(/may not write/);
  });

  it("gives no agent the operator's scope tables", () => {
    for (const agent of Object.keys(OWNERSHIP)) {
      for (const t of ["scope_snapshots", "programs", "lead_decisions", "proposal_decisions", "runs", "reports"]) {
        expect(() => assertOwns(agent, t)).toThrow();
      }
    }
  });

  it("lets both Saudade and Dahlia record program leads", () => {
    expect(() => assertOwns("saudade-of-sunday", "program_leads")).not.toThrow();
    expect(() => assertOwns("dahlia-of-wednesday", "program_leads")).not.toThrow();
    expect(() => assertOwns("diablo-of-monday", "program_leads")).toThrow();
  });

  it("names one MCP server per agent", () => {
    expect(serverName("dahlia-of-wednesday")).toBe("ei-dahlia");
    expect(serverName("metsa-of-tuesday")).toBe("ei-metsa");
  });
});

describe("redaction", () => {
  it.each([
    ["Authorization: Bearer abc.def.ghi", "abc.def.ghi"],
    ["jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig-part_1 here", "eyJhbGciOiJIUzI1NiJ9"],
    ["key AKIAABCDEFGHIJKLMNOP leaked", "AKIAABCDEFGHIJKLMNOP"],
    ["password=hunter2&x=1", "hunter2"],
    ["token: s3cr3tvalue", "s3cr3tvalue"],
    ["secret=topsecret", "topsecret"],
  ])("masks %s", (input, leaked) => {
    const out = redact(input);
    expect(out).toContain("[REDACTED]");
    expect(out).not.toContain(leaked);
  });

  it("leaves ordinary security text alone", () => {
    const s = "CVE-2026-1234 affects nginx 1.24.0; see https://nvd.nist.gov/vuln/detail/CVE-2026-1234";
    expect(redact(s)).toBe(s);
  });

  it("clips text to 64 KB", () => {
    expect(clip("x".repeat(70000)).length).toBe(65536);
    expect(clip("short")).toBe("short");
  });
});
