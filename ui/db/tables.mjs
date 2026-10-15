/**
 * Agent-writable tables: the MCP tool that appends to each, and its columns.
 *
 * Column spec: { type, optional?, values? } where type is
 * "text" | "int" | "bool" | "json" | "enum". The writer stamps agent, run_id,
 * and created_at; every table also accepts an optional `supersedes` id.
 */
const text = { type: "text" };
const textOpt = { type: "text", optional: true };
const intOpt = { type: "int", optional: true };
const enumOf = (...values) => ({ type: "enum", values });

const severity = enumOf("info", "low", "medium", "high", "critical");
const findingStatus = enumOf("confirmed", "suspected", "not_reproduced");

const findingColumns = {
  target: text,
  title: text,
  status: findingStatus,
  severity,
  description: text,
  reproduction: textOpt,
  impact: textOpt,
  remediation: textOpt,
  evidence: textOpt,
  program_id: intOpt,
  engagement_id: intOpt,
};

export const WRITE_TABLES = {
  assets: {
    tool: "record_asset",
    description: "Record a discovered asset (domain, subdomain, IP, URL, or service).",
    columns: {
      host: text,
      kind: enumOf("domain", "subdomain", "ip", "url", "service"),
      details: { type: "json", optional: true },
      engagement_id: intOpt,
    },
  },
  asset_observations: {
    tool: "record_observation",
    description: "Record what was observed on an asset (port, service, technology) and the evidence.",
    columns: { asset_host: text, port: intOpt, service: textOpt, technology: textOpt, evidence: textOpt },
  },
  program_leads: {
    tool: "record_program_lead",
    description:
      "Record a bug bounty or disclosure program you came across. A lead is informational only and never authorizes testing.",
    columns: { name: text, platform: textOpt, url: text, found_via: text, scope_summary: textOpt },
  },
  web_findings: {
    tool: "save_web_finding",
    description: "Save a web application finding; status separates confirmed from suspected.",
    columns: findingColumns,
  },
  api_endpoints: {
    tool: "record_api_endpoint",
    description: "Record an API endpoint taken from a schema or seen during authorized testing.",
    columns: { base_url: text, method: text, path: text, auth: textOpt, notes: textOpt },
  },
  api_findings: {
    tool: "save_api_finding",
    description: "Save an API finding; status separates confirmed from suspected.",
    columns: findingColumns,
  },
  cve_notes: {
    tool: "save_cve_note",
    description: "Save a researched CVE: affected range, fix version, CVSS, KEV status, public exploit, and sources.",
    columns: {
      cve_id: text,
      product: text,
      affected_versions: text,
      fixed_version: textOpt,
      cvss: textOpt,
      kev: { type: "bool" },
      public_exploit: { type: "bool" },
      summary: text,
      sources: { type: "json" },
    },
  },
  exploit_analyses: {
    tool: "save_exploit_analysis",
    description: "Save a defensive explanation of a public PoC: mechanism, preconditions, detection, mitigation.",
    columns: {
      cve_id: textOpt,
      title: text,
      mechanism: text,
      preconditions: textOpt,
      detection: textOpt,
      mitigation: textOpt,
      sources: { type: "json", optional: true },
    },
  },
  scope_proposals: {
    tool: "propose_scope",
    description:
      "Propose structured scope for a tracked program. It does not count as authorization until the operator confirms it.",
    columns: {
      program_id: { type: "int" },
      in_scope: { type: "json" },
      out_of_scope: { type: "json" },
      exclusions: { type: "json" },
      source_excerpt: textOpt,
    },
  },
  submissions: {
    tool: "draft_submission",
    description: "Draft a submission-ready report for a tracked program.",
    columns: {
      program_id: { type: "int" },
      title: text,
      severity,
      body_markdown: text,
      finding_refs: { type: "json", optional: true },
    },
  },
  engagements: {
    tool: "create_engagement",
    description: "Create an engagement that groups related runs.",
    columns: { name: text, program_id: intOpt },
  },
  run_engagements: {
    tool: "link_run_to_engagement",
    description: "Link a run to an engagement.",
    columns: { linked_run_id: text, engagement_id: { type: "int" } },
  },
};
