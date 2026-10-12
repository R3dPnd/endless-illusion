import type { AgentPolicy } from "./types";

export function prettyName(agent: string): string {
  return agent
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** CSS modifier for the classification badge. */
export function classTag(classification: string): string {
  if (classification.includes("active")) return "active";
  if (classification.includes("passive")) return "passive";
  if (classification.includes("orchestr")) return "orch";
  return "muted";
}

/** Whether this agent can ever run active (Bash) tooling. */
export function canGoActive(a: AgentPolicy | undefined): boolean {
  return !!a && Array.isArray(a.tools?.authorized_active) && a.tools.authorized_active.length > 0;
}

export function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString();
}
