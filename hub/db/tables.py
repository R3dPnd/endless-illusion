"""
Agent-writable tables: the MCP tool that appends to each, and its columns.

Column spec: {"type", "optional"?, "values"?} where type is
"text" | "int" | "bool" | "json" | "enum". The writer stamps agent, run_id,
and created_at; every table also accepts an optional `supersedes` id.
"""

TEXT = {"type": "text"}
TEXT_OPT = {"type": "text", "optional": True}
INT_OPT = {"type": "int", "optional": True}


def enum_of(*values):
    return {"type": "enum", "values": list(values)}


SEVERITY = enum_of("info", "low", "medium", "high", "critical")
FINDING_STATUS = enum_of("confirmed", "suspected", "not_reproduced")

FINDING_COLUMNS = {
    "target": TEXT,
    "title": TEXT,
    "status": FINDING_STATUS,
    "severity": SEVERITY,
    "description": TEXT,
    "reproduction": TEXT_OPT,
    "impact": TEXT_OPT,
    "remediation": TEXT_OPT,
    "evidence": TEXT_OPT,
    "program_id": INT_OPT,
    "engagement_id": INT_OPT,
}

WRITE_TABLES = {
    "assets": {
        "tool": "record_asset",
        "description": "Record a discovered asset (domain, subdomain, IP, URL, or service).",
        "columns": {
            "host": TEXT,
            "kind": enum_of("domain", "subdomain", "ip", "url", "service"),
            "details": {"type": "json", "optional": True},
            "engagement_id": INT_OPT,
        },
    },
    "asset_observations": {
        "tool": "record_observation",
        "description": "Record what was observed on an asset (port, service, technology) and the evidence.",
        "columns": {"asset_host": TEXT, "port": INT_OPT, "service": TEXT_OPT, "technology": TEXT_OPT, "evidence": TEXT_OPT},
    },
    "program_leads": {
        "tool": "record_program_lead",
        "description": "Record a bug bounty or disclosure program you came across. "
        "A lead is informational only and never authorizes testing.",
        "columns": {"name": TEXT, "platform": TEXT_OPT, "url": TEXT, "found_via": TEXT, "scope_summary": TEXT_OPT},
    },
    "web_findings": {
        "tool": "save_web_finding",
        "description": "Save a web application finding; status separates confirmed from suspected.",
        "columns": FINDING_COLUMNS,
    },
    "api_endpoints": {
        "tool": "record_api_endpoint",
        "description": "Record an API endpoint taken from a schema or seen during authorized testing.",
        "columns": {"base_url": TEXT, "method": TEXT, "path": TEXT, "auth": TEXT_OPT, "notes": TEXT_OPT},
    },
    "api_findings": {
        "tool": "save_api_finding",
        "description": "Save an API finding; status separates confirmed from suspected.",
        "columns": FINDING_COLUMNS,
    },
    "cve_notes": {
        "tool": "save_cve_note",
        "description": "Save a researched CVE: affected range, fix version, CVSS, KEV status, public exploit, and sources.",
        "columns": {
            "cve_id": TEXT,
            "product": TEXT,
            "affected_versions": TEXT,
            "fixed_version": TEXT_OPT,
            "cvss": TEXT_OPT,
            "kev": {"type": "bool"},
            "public_exploit": {"type": "bool"},
            "summary": TEXT,
            "sources": {"type": "json"},
        },
    },
    "exploit_analyses": {
        "tool": "save_exploit_analysis",
        "description": "Save a defensive explanation of a public PoC: mechanism, preconditions, detection, mitigation.",
        "columns": {
            "cve_id": TEXT_OPT,
            "title": TEXT,
            "mechanism": TEXT,
            "preconditions": TEXT_OPT,
            "detection": TEXT_OPT,
            "mitigation": TEXT_OPT,
            "sources": {"type": "json", "optional": True},
        },
    },
    "scope_proposals": {
        "tool": "propose_scope",
        "description": "Propose structured scope for a tracked program. "
        "It does not count as authorization until the operator confirms it.",
        "columns": {
            "program_id": {"type": "int"},
            "in_scope": {"type": "json"},
            "out_of_scope": {"type": "json"},
            "exclusions": {"type": "json"},
            "source_excerpt": TEXT_OPT,
        },
    },
    "submissions": {
        "tool": "draft_submission",
        "description": "Draft a submission-ready report for a tracked program.",
        "columns": {
            "program_id": {"type": "int"},
            "title": TEXT,
            "severity": SEVERITY,
            "body_markdown": TEXT,
            "finding_refs": {"type": "json", "optional": True},
        },
    },
    "engagements": {
        "tool": "create_engagement",
        "description": "Create an engagement that groups related runs.",
        "columns": {"name": TEXT, "program_id": INT_OPT},
    },
    "run_engagements": {
        "tool": "link_run_to_engagement",
        "description": "Link a run to an engagement.",
        "columns": {"linked_run_id": TEXT, "engagement_id": {"type": "int"}},
    },
}
