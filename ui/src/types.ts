export interface AgentPolicy {
  agent: string;
  day?: string;
  role: string;
  model?: string;
  classification: string;
  needs_authorization: boolean | string;
  tools: {
    default_safe: string[];
    authorized_active: string[];
  };
  notes?: string;
}

export type RunEvent =
  | { kind: "meta"; agent: string; orchestrated: boolean; activeEngaged: boolean; tools: string[]; ts: number }
  | { kind: "claude"; data: ClaudeEvent; ts: number }
  | { kind: "stdout"; text: string; ts: number }
  | { kind: "stderr"; text: string; ts: number }
  | { kind: "error"; text: string; ts: number }
  | { kind: "warn"; text: string; ts: number }
  | { kind: "closed"; code: number | null; status: string; ts: number };

// A loose shape for Claude Code's stream-json events.
export interface ClaudeEvent {
  type: string;
  subtype?: string;
  message?: {
    content?: Array<
      | { type: "text"; text: string }
      | { type: "tool_use"; id?: string; name: string; input?: unknown }
      | { type: "tool_result"; tool_use_id?: string; content?: unknown; is_error?: boolean }
      | { type: string; [k: string]: unknown }
    >;
  };
  result?: string;
  total_cost_usd?: number;
  duration_ms?: number;
  num_turns?: number;
  is_error?: boolean;
  subagent_stats?: { spawned?: number; by_type?: Record<string, number> };
  /** Set on messages emitted from inside a subagent (the delegating tool_use id). */
  parent_tool_use_id?: string | null;
  tools?: string[];
  model?: string;
  cwd?: string;
  [k: string]: unknown;
}

export interface StartRunResponse {
  id: string;
  agent: string;
  status: string;
  tools: string[];
  activeEngaged: boolean;
}

// ---- archive ----

export interface RunSummary {
  id: string;
  agent: string;
  task: string;
  scope: string;
  status: "running" | "done" | "error" | "stopped" | "interrupted";
  active_engaged: boolean;
  tools: string[];
  program_id: number | null;
  snapshot_id: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
  started_at: string;
  ended_at: string | null;
}

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface Finding {
  id: number;
  kind: "web" | "api";
  agent: string;
  run_id: string | null;
  created_at: string;
  target: string;
  title: string;
  status: "confirmed" | "suspected" | "not_reproduced";
  severity: Severity;
  description: string;
  impact: string;
  remediation: string;
}

export interface CveNote {
  id: number;
  agent: string;
  run_id: string | null;
  created_at: string;
  cve_id: string;
  product: string;
  affected_versions: string;
  fixed_version: string | null;
  cvss: string | null;
  kev: boolean;
  public_exploit: boolean;
  summary: string;
  sources: string[];
}

export interface Submission {
  id: number;
  agent: string;
  run_id: string | null;
  created_at: string;
  program_id: number;
  program_name: string;
  program_url: string;
  title: string;
  severity: Severity;
  body_markdown: string;
}

// ---- bounties ----

export interface ScopeItem {
  asset: string;
  type?: string;
  notes?: string;
}

export interface Lead {
  normalizedUrl: string;
  name: string;
  platform: string | null;
  url: string;
  foundVia: string;
  scopeSummary: string;
  sightings: number;
  agents: string[];
  runIds: string[];
  firstSeen: string;
  lastSeen: string;
}

export interface Proposal {
  id: number;
  agent: string;
  runId: string | null;
  createdAt: string;
  inScope: ScopeItem[];
  outOfScope: ScopeItem[];
  exclusions: string[];
  sourceExcerpt: string;
}

export interface Program {
  id: number;
  name: string;
  platform: string | null;
  url: string;
  normalizedUrl: string;
  source: "manual" | "lead" | "sync";
  createdAt: string;
  proposals: Proposal[];
  policyText?: string;
}

export interface ConfirmedProgram extends Program {
  snapshot: {
    id: number;
    inScope: ScopeItem[];
    outOfScope: ScopeItem[];
    exclusions: string[];
    confirmedAt: string;
    stale: boolean;
  };
}

export interface Bounties {
  leads: Lead[];
  tracked: Program[];
  confirmed: ConfirmedProgram[];
}
