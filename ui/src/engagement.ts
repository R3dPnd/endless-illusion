import type { EngagementDetail, GateAction, ScopeVerdict, StageView } from "./types";

export type StageButton = "start" | "arm" | "stop" | "skip" | "rerun" | "open";
export type CardButton = "approve" | "deny" | "denyWithReason" | "ask";

/** Which controls a stage card shows. "arm" means the "Arm active tools" tick beside Start/Re-run. */
export function stageButtons(s: StageView): StageButton[] {
  const out: StageButton[] = [];
  switch (s.status) {
    case "ready":
      out.push("start");
      if (s.canArm) out.push("arm");
      if (s.stage !== "research") out.push("skip");
      break;
    case "running":
    case "awaiting-approval":
      out.push("stop");
      break;
    case "done":
    case "failed":
    case "stopped":
      if (s.canStart !== false) {
        out.push("rerun");
        if (s.canArm) out.push("arm");
      }
      break;
    default:
      break; // locked, skipped
  }
  if (s.runId) out.push("open");
  return out;
}

/** Approve is never offered for an out-of-scope action (the hub refuses it too). */
export function cardButtons(a: GateAction): CardButton[] {
  return a.verdict === "out" ? ["deny", "denyWithReason", "ask"] : ["approve", "deny", "denyWithReason", "ask"];
}

/** Unknown and no-host verdicts need the operator's "I've checked this host is in scope" tick. */
export const approveNeedsAck = (a: GateAction): boolean => a.verdict === "unknown" || a.verdict === "none";

const LABELS: Record<ScopeVerdict, string> = {
  in: "✓ in scope",
  out: "✗ out of scope",
  unknown: "? can't tell",
  none: "no target host",
};
export const verdictLabel = (v: ScopeVerdict): string => LABELS[v];

/** The shown draft is the approved one: ops_plans.draft_id names the draft it copied (row ids of the two tables never compare). */
export const planIsApproved = (plan: EngagementDetail["plan"]): boolean =>
  !!plan.draft && !!plan.approved && plan.approved.draft_id === plan.draft.id;

/** A stage start's body. Armed is sent only when ticked AND the card offers arming: every arm is deliberate. */
export function startBody(armed: boolean, buttons: StageButton[], research: boolean, question: string): { armed?: true; question?: string } {
  return { ...(armed && buttons.includes("arm") ? { armed: true as const } : {}), ...(research ? { question: question.trim() } : {}) };
}

/** The engagement body's scopeHosts: typed lines for a lab; none for a bounty (the hub derives them from the confirmed snapshot). */
export function newEngagementHosts(kind: "lab" | "bounty", typed: string): string[] {
  if (kind === "bounty") return [];
  return typed
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

/** Pending approvals of engagements other than the selected one, per engagement (in first-seen order). */
export function pendingElsewhere(items: GateAction[], selectedId: number | null): { engagementId: number; count: number }[] {
  const counts = new Map<number, number>();
  for (const a of items) if (a.engagement_id !== selectedId) counts.set(a.engagement_id, (counts.get(a.engagement_id) ?? 0) + 1);
  return [...counts].map(([engagementId, count]) => ({ engagementId, count }));
}
