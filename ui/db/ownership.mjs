/**
 * Which tables each agent may write. The single source for the MCP tool
 * registry, agent definitions, and tests. Every agent may read every table;
 * hub tables (runs, run_events, reports) and operator tables (programs,
 * lead_decisions, proposal_decisions, scope_snapshots) belong to no agent.
 */
export const OWNERSHIP = {
  "saudade-of-sunday": ["assets", "asset_observations", "program_leads"],
  "diablo-of-monday": ["web_findings"],
  "metsa-of-tuesday": ["api_endpoints", "api_findings"],
  "dahlia-of-wednesday": ["cve_notes", "program_leads"],
  "dann-of-thursday": ["engagements", "run_engagements"],
  "sin-of-friday": ["exploit_analyses"],
  "sen-of-saturday": ["scope_proposals", "submissions"],
};

export const AGENTS = Object.keys(OWNERSHIP);

export const AGENT_SHORT = Object.fromEntries(AGENTS.map((a) => [a, a.split("-")[0]]));

/** MCP server name for an agent's memory instance, e.g. "ei-dahlia". */
export const serverName = (agent) => `ei-${AGENT_SHORT[agent]}`;

export function assertOwns(agent, table) {
  if (!OWNERSHIP[agent]?.includes(table)) {
    throw new Error(`agent ${agent} may not write table ${table}`);
  }
}
