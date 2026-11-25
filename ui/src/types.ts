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

/** Bounty-board fields agents supply via record_program_lead (bounty-scout skill). */
export interface BoardDetails {
  programType: "bounty" | "vdp" | null;
  rewards: string | null;
  maxRewardUsd: number | null;
  assetTypes: string[];
  details: string | null;
  programUpdated: string | null;
  sources: string[];
  /** Unverified, agent-written; only a confirmed snapshot is authoritative. */
  scopeSummary: string;
}

export interface Lead extends BoardDetails {
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

export interface Program extends BoardDetails {
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
    /** In-scope hosts the hub derives from this snapshot: exactly what a bounty engagement gets. */
    scopeHosts: string[];
  };
}

export interface Bounties {
  leads: Lead[];
  tracked: Program[];
  confirmed: ConfirmedProgram[];
}

// ---- engagements ------------------------------------------------------------

export type StageName = "discovery" | "planning" | "web" | "api" | "analysis" | "reporting" | "research";
export type StageStatus = "locked" | "ready" | "running" | "awaiting-approval" | "done" | "failed" | "stopped" | "skipped";
export type ScopeVerdict = "in" | "out" | "unknown" | "none";

export interface Engagement {
  id: number;
  slug: string;
  name: string;
  kind: "lab" | "bounty";
  scope_hosts: string[];
  scope_notes: string;
  authorization: string;
  program_id: number | null;
  snapshot_id: number | null;
  created_at: string;
}

export interface StageView {
  stage: StageName;
  agent: string;
  status: StageStatus;
  runId: string | null;
  stageId: number | null;
  armed: boolean;
  canArm: boolean;
  pending: number;
  history: string[];
  planError: string | null;
  canStart: boolean;
}

export interface PlanStage {
  include: boolean;
  targets?: string[];
  focus?: string;
}
export interface Plan {
  stages: Partial<Record<StageName, PlanStage>>;
  research?: string[];
}
/** A plan_drafts row (the draft) or an ops_plans row (the approved plan). */
export interface PlanRow {
  id: number;
  plan: Plan;
  /** ops_plans only: the plan_drafts id it approved. Compare this with the draft's `id`, never the two ids. */
  draft_id?: number;
}

/** A gated action waiting on the operator (also the shape /api/gate/pending returns). */
export interface GateAction {
  id: number;
  engagement_id: number;
  run_id: string;
  stage: StageName;
  tool_name: string;
  target: string;
  why: string;
  technique: string;
  risk: string;
  hosts: string[];
  verdict: ScopeVerdict;
  created_at: string;
}

export interface EngagementQuestion {
  id: number;
  stage: StageName;
  action_id: number | null;
  kind: "ask" | "explain";
  question: string;
  technique: string | null;
  answer: string | null;
  created_at: string;
}

export interface EngagementDetail {
  engagement: Engagement;
  stages: StageView[];
  plan: { draft: PlanRow | null; approved: PlanRow | null };
  pending: GateAction[];
  questions: EngagementQuestion[];
}

export interface PendingGate {
  count: number;
  items: GateAction[];
}
