import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AGENTS, serverName } from "../db/ownership.mjs";
import { qualifiedToolsFor, SHARED_READ_TOOLS, toolNamesFor } from "../mcp/tool-names.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const DEFS = path.join(ROOT, ".claude", "agents");

function toolsOf(agent) {
  const md = readFileSync(path.join(DEFS, `${agent}.md`), "utf8");
  const line = md.match(/^---\n[\s\S]*?^tools:\s*(.+)$[\s\S]*?^---$/m)?.[1];
  return line ? line.split(",").map((t) => t.trim()).filter(Boolean) : [];
}

const policy = (agent) => JSON.parse(readFileSync(path.join(ROOT, "agents", `${agent}.policy.json`), "utf8"));

describe("agent definitions", () => {
  it("include a definition for every agent, Dann included", () => {
    for (const a of AGENTS) expect(existsSync(path.join(DEFS, `${a}.md`)), a).toBe(true);
    expect(readdirSync(DEFS).filter((f) => f.endsWith(".md")).sort()).toEqual(AGENTS.map((a) => `${a}.md`).sort());
  });

  it.each(AGENTS)("%s lists only its passive tools, its own memory tools, and the shared notes", (agent) => {
    const tools = toolsOf(agent);
    const allowed = new Set([...policy(agent).tools.default_safe, ...qualifiedToolsFor(agent), ...SHARED_READ_TOOLS]);
    for (const t of tools) expect(allowed.has(t), `${agent}: ${t}`).toBe(true);
  });

  it.each(AGENTS)("%s can call all of its own write tools", (agent) => {
    const tools = new Set(toolsOf(agent));
    for (const w of toolNamesFor(agent).write) expect(tools.has(`mcp__${serverName(agent)}__${w}`), `${agent}: ${w}`).toBe(true);
  });

  it.each(AGENTS)("%s has no other agent's memory tools", (agent) => {
    const others = AGENTS.filter((a) => a !== agent).map((a) => `mcp__${serverName(a)}__`);
    for (const t of toolsOf(agent)) for (const o of others) expect(t.startsWith(o), `${agent}: ${t}`).toBe(false);
  });

  it.each(AGENTS)("%s can read the shared notes and preloads the RoE quickref", (agent) => {
    const tools = new Set(toolsOf(agent));
    for (const t of SHARED_READ_TOOLS) expect(tools.has(t), `${agent}: ${t}`).toBe(true);
    expect(readFileSync(path.join(DEFS, `${agent}.md`), "utf8")).toMatch(/^---\n[\s\S]*?^skills:\n(?:  - .+\n)*  - roe-quickref\n[\s\S]*?^---$/m);
  });

  it("gives no specialist Bash by default", () => {
    for (const a of AGENTS) expect(toolsOf(a)).not.toContain("Bash");
  });

  it("lets Dann delegate with the CLI's Agent tool", () => {
    expect(toolsOf("dann-of-thursday")).toContain("Agent");
    expect(policy("dann-of-thursday").tools.default_safe).toContain("Agent");
  });
});
