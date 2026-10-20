import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openDb } from "../db/index.mjs";
import { createRun, appendEvent, addReport, finishRun, markInterrupted, listRuns, getRunEvents, getRun } from "../db/archive.mjs";
import { cleanReport } from "../shared/report.mjs";
import { createApp } from "../server/app.mjs";
import { AGENTS } from "../db/ownership.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_LINES = readFileSync(path.join(HERE, "fixtures", "run-events.jsonl"), "utf8").trim().split("\n").length;

const baseRun = (over = {}) => ({
  id: "r1", agent: "dahlia-of-wednesday", task: "t", scope: "", authorization: "",
  activeEngaged: false, tools: ["Read"], ...over,
});

describe("archive (unit)", () => {
  it("records a run with events and reports", () => {
    const db = openDb(":memory:");
    createRun(db, baseRun());
    appendEvent(db, "r1", 0, { kind: "meta", ts: 1 });
    appendEvent(db, "r1", 1, { kind: "closed", ts: 2 });
    addReport(db, { runId: "r1", agent: "dahlia-of-wednesday", kind: "final", text: "done", meta: { cost: 1 } });
    finishRun(db, "r1", { status: "done", costUsd: 0.5, durationMs: 1000 });
    expect(getRun(db, "r1")).toMatchObject({ status: "done", cost_usd: 0.5, tools: ["Read"] });
    expect(getRunEvents(db, "r1").map((e) => e.kind)).toEqual(["meta", "closed"]);
    expect(listRuns(db, {}).map((r) => r.id)).toEqual(["r1"]);
  });

  it("redacts secrets in events without corrupting them", () => {
    const db = openDb(":memory:");
    createRun(db, baseRun({ id: "r3" }));
    const cmd = 'curl -d "password=hunter2" -H "Authorization: Bearer abc.def"';
    appendEvent(db, "r3", 0, { kind: "claude", ts: 1, data: { type: "assistant", message: { content: [{ type: "tool_use", name: "Bash", input: { command: cmd } }] } } });
    const [evt] = getRunEvents(db, "r3");
    const stored = evt.data.message.content[0].input.command;
    expect(stored).not.toContain("hunter2");
    expect(stored).not.toContain("abc.def");
    expect(stored).toContain('-H "Authorization: Bearer [REDACTED]"');
  });

  it("marks runs left running as interrupted and keeps their events", () => {
    const db = openDb(":memory:");
    createRun(db, baseRun({ id: "r2" }));
    appendEvent(db, "r2", 0, { kind: "meta", ts: 1 });
    expect(markInterrupted(db)).toBe(1);
    expect(getRun(db, "r2").status).toBe("interrupted");
    expect(getRunEvents(db, "r2")).toHaveLength(1);
  });

  it("filters runs by agent and full-text query", () => {
    const db = openDb(":memory:");
    createRun(db, baseRun({ id: "a", task: "nginx review" }));
    createRun(db, baseRun({ id: "b", agent: "sin-of-friday", task: "log4j analysis" }));
    expect(listRuns(db, { agent: "sin-of-friday" }).map((r) => r.id)).toEqual(["b"]);
    expect(listRuns(db, { q: "nginx" }).map((r) => r.id)).toEqual(["a"]);
  });
});

describe("cleanReport", () => {
  it("strips the hand-back frame and keeps stats", () => {
    const raw = "[Subagent hand-back] preamble. The report follows:\n  Line one\n  Line two\nagentId: x1 (use SendMessage with to: 'x1' to continue)\n<usage>tool_uses: 4\nduration_ms: 65000</usage>";
    expect(cleanReport(raw)).toEqual({ text: "Line one\nLine two", meta: "4 tool uses · 1m 5s" });
  });
});

describe("hub archives a run end to end", () => {
  let ctx;
  let server;
  let base;
  const work = mkdtempSync(path.join(tmpdir(), "ei-hub-"));
  const argvFile = path.join(work, "argv.json");

  beforeAll(async () => {
    process.env.FAKE_ARGV_FILE = argvFile;
    ctx = createApp({ dbFile: path.join(work, "data", "ei.db"), dataDir: path.join(work, "data"), claudeBin: path.join(HERE, "fixtures", "fake-claude.mjs") });
    await new Promise((r) => (server = ctx.app.listen(0, "127.0.0.1", r)));
    base = `http://127.0.0.1:${server.address().port}`;
  });
  afterAll(() => server?.close());

  async function runToCompletion(body) {
    const res = await fetch(`${base}/api/runs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    expect(res.status).toBe(200);
    const { id } = await res.json();
    for (let i = 0; i < 100 && getRun(ctx.db, id)?.status === "running"; i++) await new Promise((r) => setTimeout(r, 50));
    return id;
  }

  it("stores the run, its events, and its reports", async () => {
    const id = await runToCompletion({ agent: "dann-of-thursday", task: "Summarize Log4Shell" });
    const run = getRun(ctx.db, id);
    expect(run.status).toBe("done");
    expect(run.cost_usd).toBeCloseTo(0.0123);
    expect(getRunEvents(ctx.db, id)).toHaveLength(FIXTURE_LINES + 2); // + meta + closed
    const reports = ctx.db.prepare("SELECT agent, kind, text, meta FROM reports WHERE run_id = ? ORDER BY id").all(id);
    expect(reports.map((r) => [r.agent, r.kind])).toEqual([["dahlia-of-wednesday", "subagent_report"], ["dann-of-thursday", "final"]]);
    expect(reports[0].text).toBe("CVE-2021-44228 is a JNDI lookup RCE in Log4j 2.0-beta9 to 2.14.1.\nFixed in 2.17.1.");
    expect(JSON.parse(reports[0].meta).stats).toBe("4 tool uses · 1m 5s");
  });

  it("stores the SubagentHandback message as the subagent's report", async () => {
    process.env.FAKE_FIXTURE = "run-events-handback.jsonl";
    try {
      const id = await runToCompletion({ agent: "dann-of-thursday", task: "Check prior work" });
      const sub = ctx.db.prepare("SELECT agent, text, meta FROM reports WHERE run_id = ? AND kind = 'subagent_report'").all(id);
      expect(sub).toHaveLength(1);
      expect(sub[0].agent).toBe("dahlia-of-wednesday");
      expect(sub[0].text).toBe("One stored note: CVE-2021-44228, CVSS 10.0, KEV since 2021-12-10.");
      expect(JSON.parse(sub[0].meta).stats).toBe("4 tool uses · 21s");
    } finally {
      delete process.env.FAKE_FIXTURE;
    }
  });

  it("launches orchestrated runs restricted, as Dann, with every agent's memory server", async () => {
    const id = await runToCompletion({ agent: "dann-of-thursday", task: "x" });
    const argv = JSON.parse(readFileSync(argvFile, "utf8"));
    const at = (f) => argv[argv.indexOf(f) + 1];
    expect(at("--agent")).toBe("dann-of-thursday");
    expect(argv).toContain("--strict-mcp-config");
    expect(at("--tools")).not.toMatch(/Bash/);
    expect(at("--allowedTools")).toContain("mcp__pnd-notes__search_notes");
    expect(at("--append-system-prompt")).toContain("Rules of Engagement");
    const config = JSON.parse(readFileSync(at("--mcp-config"), "utf8"));
    expect(Object.keys(config.mcpServers).sort()).toEqual([...AGENTS.map((a) => `ei-${a.split("-")[0]}`), "pnd-notes"].sort());
    expect(config.mcpServers["ei-dahlia"].env.EI_RUN_ID).toBe(id);
    expect(config.mcpServers["ei-dahlia"].args).toContain("dahlia-of-wednesday");
  });

  it("gives a direct run only its own memory server", async () => {
    await runToCompletion({ agent: "sin-of-friday", task: "x" });
    const argv = JSON.parse(readFileSync(argvFile, "utf8"));
    expect(argv).not.toContain("--agent");
    const config = JSON.parse(readFileSync(argv[argv.indexOf("--mcp-config") + 1], "utf8"));
    expect(Object.keys(config.mcpServers).sort()).toEqual(["ei-sin", "pnd-notes"]);
    expect(argv[argv.indexOf("--allowedTools") + 1]).toContain("mcp__ei-sin__save_exploit_analysis");
  });
});
