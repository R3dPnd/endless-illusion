import type { GateAction, ScopeVerdict, StageView } from "./types";

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
