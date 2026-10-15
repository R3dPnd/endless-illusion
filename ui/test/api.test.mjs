import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createApp } from "../server/app.mjs";
import { insertAgentRow } from "../db/write.mjs";
import { createRun, appendEvent, finishRun } from "../db/archive.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ORIGIN = "http://localhost:5173";
let ctx;
let server;
let base;

beforeAll(async () => {
  const work = mkdtempSync(path.join(tmpdir(), "ei-api-"));
  ctx = createApp({ dataDir: path.join(work, "data"), claudeBin: path.join(HERE, "fixtures", "fake-claude.mjs") });
  await new Promise((r) => (server = ctx.app.listen(0, "127.0.0.1", r)));
  base = `http://127.0.0.1:${server.address().port}`;
});
afterAll(() => server?.close());

const get = (p) => fetch(base + p).then(async (r) => ({ status: r.status, body: r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text() }));
const post = (p, body, headers = {}) =>
  fetch(base + p, { method: "POST", headers: { "content-type": "application/json", origin: ORIGIN, ...headers }, body: JSON.stringify(body ?? {}) })
    .then(async (r) => ({ status: r.status, body: await r.json().catch(() => null) }));

const lead = (name, url, agent = "saudade-of-sunday") =>
  insertAgentRow(ctx.db, { agent, runId: "seed", table: "program_leads", fields: { name, url, found_via: "security.txt", scope_summary: "unverified" } });

async function trackedProgram(name, url) {
  lead(name, url);
  const res = await post("/api/leads/track", { normalizedUrl: url.replace(/^https:\/\//, "") });
  expect(res.status).toBe(200);
  return res.body.programId;
}

const propose = (programId, asset = "app.example.com") =>
  insertAgentRow(ctx.db, { agent: "sen-of-saturday", runId: "seed", table: "scope_proposals", fields: {
    program_id: programId, in_scope: [{ asset, type: "domain" }], out_of_scope: [], exclusions: ["no DoS"] } }).id;

describe("cross-site guard", () => {
  it("rejects non-JSON posts", async () => {
    const r = await fetch(`${base}/api/runs`, { method: "POST", headers: { "content-type": "text/plain", origin: ORIGIN }, body: "{}" });
    expect(r.status).toBe(415);
  });

  it("rejects posts from another origin", async () => {
    const r = await post("/api/proposals/1/confirm", {}, { origin: "https://evil.example" });
    expect(r.status).toBe(403);
  });
});

describe("bounty pipeline", () => {
  it("moves a lead to tracked", async () => {
    lead("Alpha", "https://hackerone.com/alpha");
    lead("Alpha", "https://www.hackerone.com/alpha/", "dahlia-of-wednesday");
    let b = (await get("/api/bounties")).body;
    const l = b.leads.find((x) => x.normalizedUrl === "hackerone.com/alpha");
    expect(l.sightings).toBe(2);
    expect(l.agents.sort()).toEqual(["dahlia-of-wednesday", "saudade-of-sunday"]);
    expect((await post("/api/leads/track", { normalizedUrl: "hackerone.com/alpha" })).status).toBe(200);
    b = (await get("/api/bounties")).body;
    expect(b.leads.some((x) => x.normalizedUrl === "hackerone.com/alpha")).toBe(false);
    expect(b.tracked.some((p) => p.name === "Alpha")).toBe(true);
  });

  it("hides a dismissed lead", async () => {
    lead("Beta", "https://bugcrowd.com/beta");
    expect((await post("/api/leads/dismiss", { normalizedUrl: "bugcrowd.com/beta" })).status).toBe(200);
    const b = (await get("/api/bounties")).body;
    expect(b.leads.some((x) => x.normalizedUrl === "bugcrowd.com/beta")).toBe(false);
    expect(b.tracked.some((p) => p.name === "Beta")).toBe(false);
  });

  it("adds a program manually", async () => {
    const r = await post("/api/programs", { name: "Gamma", url: "https://intigriti.com/gamma", policyText: "Scope: *.gamma.io" });
    expect(r.status).toBe(200);
    expect((await post("/api/programs", { name: "Gamma again", url: "https://www.intigriti.com/gamma/" })).status).toBe(409);
  });

  it("confirms a proposal into a snapshot exactly once", async () => {
    const pid = await trackedProgram("Delta", "https://hackerone.com/delta");
    const prop = propose(pid);
    let b = (await get("/api/bounties")).body;
    expect(b.tracked.find((p) => p.id === pid).proposals.map((p) => p.id)).toEqual([prop]);
    expect((await post(`/api/proposals/${prop}/confirm`)).status).toBe(200);
    expect((await post(`/api/proposals/${prop}/confirm`)).status).toBe(409);
    b = (await get("/api/bounties")).body;
    const c = b.confirmed.find((p) => p.id === pid);
    expect(c.snapshot.inScope[0].asset).toBe("app.example.com");
    expect(c.snapshot.stale).toBe(false);
  });

  it("creates no snapshot for a rejected proposal", async () => {
    const pid = await trackedProgram("Epsilon", "https://hackerone.com/epsilon");
    const prop = propose(pid);
    expect((await post(`/api/proposals/${prop}/reject`)).status).toBe(200);
    expect(ctx.db.prepare("SELECT count(*) n FROM scope_snapshots WHERE program_id = ?").get(pid).n).toBe(0);
  });

  it("flags scope confirmed more than 30 days ago as stale", async () => {
    const pid = await trackedProgram("Zeta", "https://hackerone.com/zeta");
    const old = new Date(Date.now() - 40 * 86400000).toISOString();
    ctx.db.prepare("INSERT INTO scope_snapshots(program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?, '[]', '[]', '[]', ?)").run(pid, old);
    const c = (await get("/api/bounties")).body.confirmed.find((p) => p.id === pid);
    expect(c.snapshot.stale).toBe(true);
  });
});

describe("runs linked to programs", () => {
  it("refuses a program without confirmed scope", async () => {
    const pid = await trackedProgram("Eta", "https://hackerone.com/eta");
    expect((await post("/api/runs", { agent: "sin-of-friday", task: "x", programId: pid })).status).toBe(400);
  });

  it("records the snapshot a run was authorized under", async () => {
    const pid = await trackedProgram("Theta", "https://hackerone.com/theta");
    const prop = propose(pid);
    const snap = (await post(`/api/proposals/${prop}/confirm`)).body.snapshotId;
    const r = await post("/api/runs", { agent: "sin-of-friday", task: "x", programId: pid });
    expect(r.status).toBe(200);
    const row = ctx.db.prepare("SELECT program_id, snapshot_id FROM runs WHERE id = ?").get(r.body.id);
    expect(row).toEqual({ program_id: pid, snapshot_id: snap });
  });
});

describe("runs linked to programs (forgery)", () => {
  it("ignores a snapshotId supplied by the client", async () => {
    const pid = await trackedProgram("Kappa", "https://hackerone.com/kappa");
    const real = (await post(`/api/proposals/${propose(pid)}/confirm`)).body.snapshotId;
    const r = await post("/api/runs", { agent: "sin-of-friday", task: "x", programId: pid, snapshotId: 9999 });
    expect(ctx.db.prepare("SELECT snapshot_id FROM runs WHERE id = ?").get(r.body.id).snapshot_id).toBe(real);
  });
});

describe("archive endpoints", () => {
  it("replays a stored run that is no longer live", async () => {
    createRun(ctx.db, { id: "old-run", agent: "sin-of-friday", task: "old task", tools: ["Read"] });
    appendEvent(ctx.db, "old-run", 0, { kind: "meta", agent: "sin-of-friday", ts: 1 });
    appendEvent(ctx.db, "old-run", 1, { kind: "closed", code: 0, status: "done", ts: 2 });
    finishRun(ctx.db, "old-run", { status: "done" });
    const r = await fetch(`${base}/api/runs/old-run/events`);
    const body = await r.text();
    expect(body).toContain('"kind":"meta"');
    expect(body).toContain("event: done");
    const list = (await get("/api/runs?agent=sin-of-friday")).body;
    expect(list.some((x) => x.id === "old-run")).toBe(true);
  });

  it("lists findings by severity", async () => {
    const f = (title, severity) => ({ target: "app.example.com", title, status: "suspected", severity, description: "d" });
    insertAgentRow(ctx.db, { agent: "diablo-of-monday", runId: "seed", table: "web_findings", fields: f("Low one", "low") });
    insertAgentRow(ctx.db, { agent: "metsa-of-tuesday", runId: "seed", table: "api_findings", fields: f("Critical one", "critical") });
    const list = (await get("/api/findings")).body;
    expect(list.map((x) => x.title).slice(0, 2)).toEqual(["Critical one", "Low one"]);
    expect(list[0].kind).toBe("api");
  });

  it("exports a submission as markdown", async () => {
    const pid = await trackedProgram("Iota", "https://hackerone.com/iota");
    const { id } = insertAgentRow(ctx.db, { agent: "sen-of-saturday", runId: "seed", table: "submissions", fields: {
      program_id: pid, title: "IDOR in invoices", severity: "high", body_markdown: "## Steps\n1. ..." } });
    const r = await get(`/api/submissions/${id}/export`);
    expect(r.status).toBe(200);
    expect(r.body).toContain("IDOR in invoices");
    expect(r.body).toContain("Iota");
  });
});
