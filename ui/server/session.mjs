import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { serverName } from "../db/ownership.mjs";
import { SHARED_SERVER } from "../mcp/tool-names.mjs";

/**
 * argv for `claude -p`. `--tools` withholds tools from the session;
 * `--allowedTools` only pre-approves them, so it is never the restriction.
 */
export function buildSessionArgs({ tools, mcpConfigPath, mcpTools = [], agentDef, systemPrompt }) {
  const args = [
    "-p",
    "--output-format", "stream-json",
    "--verbose",
    "--tools", tools.join(","),
    "--strict-mcp-config",
  ];
  if (mcpConfigPath) args.push("--mcp-config", mcpConfigPath);
  args.push("--allowedTools", [...tools, ...mcpTools].join(","));
  if (agentDef) args.push("--agent", agentDef);
  if (systemPrompt) args.push("--append-system-prompt", systemPrompt);
  return args;
}

const MEMORY_SERVER = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "mcp", "ei-memory.mjs");

/**
 * The shared knowledge-base server entry from the repo's .mcp.json, or null
 * when it is not registered. Runs use --strict-mcp-config, so it must be
 * copied into each run's config to be reachable.
 */
export function loadSharedServer(repoRoot) {
  try {
    const config = JSON.parse(readFileSync(path.join(repoRoot, ".mcp.json"), "utf8"));
    return config.mcpServers?.[SHARED_SERVER] ?? null;
  } catch {
    return null;
  }
}

/**
 * Write the per-run MCP config: one ei-memory instance per participating
 * agent, each pinned to that agent's identity and this run's id, plus the
 * shared knowledge base when given.
 */
export function writeMcpConfig(dir, runId, agents, dbFile, shared = null) {
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const mcpServers = {};
  if (shared) mcpServers[SHARED_SERVER] = shared;
  for (const agent of agents) {
    mcpServers[serverName(agent)] = {
      command: process.execPath,
      args: [MEMORY_SERVER, "--agent", agent, "--db", dbFile],
      env: { EI_RUN_ID: runId },
    };
  }
  const file = path.join(dir, `${runId}.json`);
  writeFileSync(file, JSON.stringify({ mcpServers }, null, 2), { mode: 0o600 });
  return file;
}
