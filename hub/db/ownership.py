"""
Which tables each agent may write. The single source for the MCP tool
registry, agent definitions, and tests. Every agent may read every table;
hub tables (runs, run_events, reports) and operator tables (programs,
lead_decisions, proposal_decisions, scope_snapshots) belong to no agent.
"""

OWNERSHIP = {
    "saudade-of-sunday": ["assets", "asset_observations", "program_leads"],
    "diablo-of-monday": ["web_findings"],
    "metsa-of-tuesday": ["api_endpoints", "api_findings"],
    "dahlia-of-wednesday": ["cve_notes", "program_leads"],
    "dann-of-thursday": ["engagements", "run_engagements"],
    "sin-of-friday": ["exploit_analyses"],
    "sen-of-saturday": ["scope_proposals", "submissions"],
}

AGENTS = list(OWNERSHIP)

AGENT_SHORT = {a: a.split("-")[0] for a in AGENTS}


def server_name(agent):
    """MCP server name for an agent's memory instance, e.g. "ei-dahlia"."""
    return f"ei-{AGENT_SHORT[agent]}"


class OwnershipError(PermissionError):
    pass


def assert_owns(agent, table):
    if table not in OWNERSHIP.get(agent, []):
        raise OwnershipError(f"agent {agent} may not write table {table}")
