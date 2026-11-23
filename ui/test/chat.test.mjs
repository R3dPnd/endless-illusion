import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildChat } from "../src/chat.ts";

// Recorded claude streams, shared with the hub tests (tests/fixtures at the repo root).
const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "tests", "fixtures");
const events = (file) => [
  { kind: "meta", agent: "dann-of-thursday", orchestrated: true, activeEngaged: false, tools: [], ts: 0 },
  ...readFileSync(path.join(FIXTURES, file), "utf8").trim().split("\n").map((l, i) => ({ kind: "claude", data: JSON.parse(l), ts: i + 1 })),
];

describe("buildChat", () => {
  it("shows the SubagentHandback message as the subagent's report", () => {
    const { messages } = buildChat(events("run-events-handback.jsonl"), "Check prior work");
    const report = messages.find((m) => m.kind === "report");
    expect(report.from).toBe("dahlia-of-wednesday");
    expect(report.to).toBe("dann-of-thursday");
    expect(report.text).toBe("One stored note: CVE-2021-44228, CVSS 10.0, KEV since 2021-12-10.");
    expect(report.meta).toBe("4 tool uses · 21s");
    expect(messages.some((m) => m.text.includes("delivered to you as a message"))).toBe(false);
  });

  it("still reads reports embedded in the delegation result (older CLI)", () => {
    const report = buildChat(events("run-events.jsonl"), "x").messages.find((m) => m.kind === "report");
    expect(report.text).toContain("CVE-2021-44228 is a JNDI lookup RCE");
  });
});

describe("buildThread", () => {
  it("keeps earlier runs when another agent is triggered or a reply is sent", async () => {
    const { buildThread } = await import("../src/chat.ts");
    const first = { id: "s1", runId: "r1", task: "Check prior work", events: events("run-events.jsonl") };
    const second = { id: "s2", runId: "r2", task: "Go deeper", events: events("run-events.jsonl") };
    const { messages } = buildThread([first, second]);
    const prompts = messages.filter((m) => m.kind === "prompt").map((m) => m.text);
    expect(prompts).toEqual(["Check prior work", "Go deeper"]);
    expect(new Set(messages.map((m) => m.key)).size).toBe(messages.length);
  });

  it("shows a pending reply and a refused one in the channel", async () => {
    const { buildThread } = await import("../src/chat.ts");
    const pending = { id: "s1", runId: null, task: "and then?", events: [] };
    expect(buildThread([pending]).messages.map((m) => m.text)).toEqual(["and then?"]);
    const refused = { ...pending, events: [{ kind: "error", text: "that run is still going", ts: 1 }] };
    const msgs = buildThread([refused]).messages;
    expect(msgs[1]).toMatchObject({ from: "hub", isError: true, text: "that run is still going" });
  });
});
