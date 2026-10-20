import { OWNERSHIP, serverName } from "../db/ownership.mjs";
import { WRITE_TABLES } from "../db/tables.mjs";

/**
 * Shared read-only knowledge base (pnd-notes), granted to every agent. These
 * tools only read curated notes — no writes, no target traffic — so they are
 * always safe. Server registered in the repo's .mcp.json.
 */
export const SHARED_SERVER = "pnd-notes";
export const SHARED_READ_TOOLS = ["list_areas", "search_notes", "get_note"].map((t) => `mcp__${SHARED_SERVER}__${t}`);

/** Read tools every agent's memory server exposes. */
export const READ_TOOLS = ["find_prior_work", "search_reports", "get_report", "get_cve_note", "list_programs", "get_scope"];

/** Bare tool names an agent's server exposes. */
export function toolNamesFor(agent) {
  const tables = OWNERSHIP[agent];
  if (!tables) throw new Error(`unknown agent ${agent}`);
  return { read: [...READ_TOOLS], write: tables.map((t) => WRITE_TABLES[t].tool) };
}

/** Fully qualified names as Claude Code sees them, e.g. "mcp__ei-dahlia__save_cve_note". */
export function qualifiedToolsFor(agent) {
  const { read, write } = toolNamesFor(agent);
  return [...read, ...write].map((t) => `mcp__${serverName(agent)}__${t}`);
}
