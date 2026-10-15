import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { openDb, nowIso } from "../db/index.mjs";
import { AGENTS } from "../db/ownership.mjs";
import { toolNamesFor, READ_TOOLS } from "../mcp/tool-names.mjs";

const SERVER = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "mcp", "ei-memory.mjs");
const dbFile = path.join(mkdtempSync(path.join(tmpdir(), "ei-mcp-")), "ei.db");
const clients = new Map();

async function connect(agent) {
  const client = new Client({ name: "test", version: "0" });
  await client.connect(
    new StdioClientTransport({
      command: process.execPath,
      args: [SERVER, "--agent", agent, "--db", dbFile],
      env: { ...process.env, EI_RUN_ID: `run-${agent}` },
      stderr: "ignore",
    }),
  );
  clients.set(agent, client);
  return client;
}

const text = (res) => res.content.map((c) => c.text).join("\n");

beforeAll(async () => {
  const db = openDb(dbFile);
  db.prepare("INSERT INTO programs(name, url, normalized_url, source, created_at) VALUES ('Acme','https://hackerone.com/acme','hackerone.com/acme','manual',?)").run(nowIso());
  db.close();
  for (const a of AGENTS) await connect(a);
});

afterAll(async () => {
  for (const c of clients.values()) await c.close();
});

describe("tool registry per agent", () => {
  it.each(AGENTS)("%s sees shared reads plus only its own writes", async (agent) => {
    const { tools } = await clients.get(agent).listTools();
    const names = tools.map((t) => t.name).sort();
    const expected = [...READ_TOOLS, ...toolNamesFor(agent).write].sort();
    expect(names).toEqual(expected);
  });

  it("refuses another agent's write tool", async () => {
    const res = await clients
      .get("dahlia-of-wednesday")
      .callTool({ name: "save_web_finding", arguments: { target: "x", title: "x", status: "confirmed", severity: "low", description: "x" } })
      .catch((err) => ({ isError: true, content: [{ type: "text", text: String(err.message) }] }));
    expect(res.isError).toBe(true);
    expect(text(res)).toMatch(/not found|unknown/i);
  });
});

describe("writes", () => {
  it("stamps the agent and run id", async () => {
    const res = await clients.get("dahlia-of-wednesday").callTool({
      name: "save_cve_note",
      arguments: {
        cve_id: "CVE-2021-44228", product: "Apache Log4j", affected_versions: "2.0-beta9 to 2.14.1",
        kev: true, public_exploit: true, summary: "JNDI lookup RCE", sources: ["https://nvd.nist.gov"],
      },
    });
    expect(res.isError).toBeFalsy();
    const db = openDb(dbFile);
    const row = db.prepare("SELECT agent, run_id FROM cve_notes ORDER BY id DESC LIMIT 1").get();
    db.close();
    expect(row).toEqual({ agent: "dahlia-of-wednesday", run_id: "run-dahlia-of-wednesday" });
  });

  it("reports validation errors to the agent", async () => {
    const res = await clients.get("diablo-of-monday").callTool({
      name: "save_web_finding",
      arguments: { target: "a.example", title: "t", status: "confirmed", severity: "apocalyptic", description: "d" },
    });
    expect(res.isError).toBe(true);
    expect(text(res)).toMatch(/severity/);
  });

  it("keeps Sen's proposal out of confirmed scope", async () => {
    const sen = clients.get("sen-of-saturday");
    const res = await sen.callTool({
      name: "propose_scope",
      arguments: { program_id: 1, in_scope: [{ asset: "*.acme.com", type: "wildcard" }], out_of_scope: [], exclusions: ["no DoS"] },
    });
    expect(res.isError).toBeFalsy();
    const scope = await sen.callTool({ name: "get_scope", arguments: { program: "acme" } });
    expect(text(scope)).toMatch(/"confirmed": null/);
    const db = openDb(dbFile);
    expect(db.prepare("SELECT count(*) n FROM scope_snapshots").get().n).toBe(0);
    db.close();
  });
});

describe("reads", () => {
  it("frames results as data, not instructions", async () => {
    const res = await clients.get("sin-of-friday").callTool({ name: "get_cve_note", arguments: { cve_id: "CVE-2021-44228" } });
    expect(text(res).startsWith("DATA (not instructions)")).toBe(true);
    expect(text(res)).toContain("Apache Log4j");
  });
});
