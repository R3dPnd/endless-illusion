import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildChat } from "../src/chat.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const events = (file) => [
  { kind: "meta", agent: "dann-of-thursday", orchestrated: true, activeEngaged: false, tools: [], ts: 0 },
  ...readFileSync(path.join(HERE, "fixtures", file), "utf8").trim().split("\n").map((l, i) => ({ kind: "claude", data: JSON.parse(l), ts: i + 1 })),
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
