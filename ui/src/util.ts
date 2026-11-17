import type { Tone } from "pnd-lib-react";
import type { AgentPolicy } from "./types";

export function prettyName(agent: string): string {
  return agent
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Tag color for an agent's classification. */
export function classTag(classification: string): Tone {
  if (classification.includes("active")) return "orange";
  if (classification.includes("passive")) return "green";
  if (classification.includes("orchestr")) return "violet";
  return "muted";
}

/** Whether this agent can ever run active (Bash) tooling. */
export function canGoActive(a: AgentPolicy | undefined): boolean {
  return !!a && Array.isArray(a.tools?.authorized_active) && a.tools.authorized_active.length > 0;
}
