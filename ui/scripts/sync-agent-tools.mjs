#!/usr/bin/env node
// Rewrite the `tools:` line of each .claude/agents/<agent>.md from
//   agents/<agent>.policy.json default_safe  +  the agent's own memory tools.
// Run after changing a policy or ui/db/ownership.mjs:  node ui/scripts/sync-agent-tools.mjs
// Active toolsets are never written here; they are granted per run by the hub.

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AGENTS } from "../db/ownership.mjs";
import { qualifiedToolsFor, SHARED_READ_TOOLS } from "../mcp/tool-names.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");


for (const agent of AGENTS) {
  const policy = JSON.parse(readFileSync(path.join(ROOT, "agents", `${agent}.policy.json`), "utf8"));
  const tools = [...policy.tools.default_safe, ...qualifiedToolsFor(agent), ...SHARED_READ_TOOLS];
  const file = path.join(ROOT, ".claude", "agents", `${agent}.md`);
  const md = readFileSync(file, "utf8");
  const next = md.replace(/^(---\n[\s\S]*?^)tools:.*$/m, `$1tools: ${tools.join(", ")}`);
  if (next === md && !md.includes(`tools: ${tools.join(", ")}`)) throw new Error(`${agent}: no tools line found`);
  writeFileSync(file, next);
  console.log(`${agent}: ${tools.length} tools`);
}
