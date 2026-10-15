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
