from .db.ownership import OWNERSHIP, server_name
from .db.tables import WRITE_TABLES

# Shared read-only knowledge base (pnd-notes), granted to every agent. These
# tools only read curated notes — no writes, no target traffic — so they are
# always safe. Server registered in the repo's .mcp.json.
SHARED_SERVER = "pnd-notes"
SHARED_READ_TOOLS = [f"mcp__{SHARED_SERVER}__{t}" for t in ("list_areas", "search_notes", "get_note")]

# Read tools every agent's memory server exposes.
READ_TOOLS = ["find_prior_work", "search_reports", "get_report", "get_cve_note", "list_programs", "get_scope"]


def tool_names_for(agent):
    """Bare tool names an agent's server exposes: {"read": [...], "write": [...]}."""
    if agent not in OWNERSHIP:
        raise KeyError(f"unknown agent {agent}")
    return {"read": list(READ_TOOLS), "write": [WRITE_TABLES[t]["tool"] for t in OWNERSHIP[agent]]}


def qualified_tools_for(agent):
    """Fully qualified names as Claude Code sees them, e.g. "mcp__ei-dahlia__save_cve_note"."""
    names = tool_names_for(agent)
    return [f"mcp__{server_name(agent)}__{t}" for t in names["read"] + names["write"]]
