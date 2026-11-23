import type { BoardDetails, ConfirmedProgram, Lead, Program, ScopeItem } from "./types";

const item = (s: ScopeItem) => `- ${s.asset}${s.type ? ` (${s.type})` : ""}${s.notes ? ` — ${s.notes}` : ""}`;

/** Scope text for the Trigger form, straight from a confirmed snapshot. */
export function scopeText(p: ConfirmedProgram): string {
  const { inScope, outOfScope, exclusions } = p.snapshot;
  return [
    "In scope:",
    ...(inScope.length ? inScope.map(item) : ["- (none listed)"]),
    ...(outOfScope.length ? ["", "Out of scope:", ...outOfScope.map(item)] : []),
    ...(exclusions.length ? ["", "Exclusions:", ...exclusions.map((e) => `- ${e}`)] : []),
  ].join("\n");
}

/** Authorization line naming the exact snapshot a run relies on. */
export function authorizationText(p: ConfirmedProgram): string {
  return `${p.name}${p.platform ? ` on ${p.platform}` : ""} (${p.url}), scope snapshot #${p.snapshot.id} confirmed ${p.snapshot.confirmedAt.slice(0, 10)}`;
}

// ---- bounty board → Dann ----------------------------------------------------

/** What a card on the board is, wherever it sits in the pipeline. */
export type BoardItem =
  | { stage: "lead"; key: string; bounty: Lead }
  | { stage: "tracked"; key: string; bounty: Program }
  | { stage: "confirmed"; key: string; bounty: ConfirmedProgram };

export interface DannSession {
  task: string;
  scope: string;
  authorization: string;
  programId?: number;
}

const facts = (b: BoardDetails & { name: string; url: string; platform: string | null }) =>
  [
    `Program: ${b.name}${b.platform ? ` (${b.platform})` : ""} — ${b.url}`,
    b.programType && `Type: ${b.programType === "vdp" ? "vulnerability disclosure (no bounty)" : "paid bounty"}`,
    b.rewards && `Rewards: ${b.rewards}`,
    b.assetTypes.length > 0 && `Asset types: ${b.assetTypes.join(", ")}`,
    b.scopeSummary && `Scope (unverified, from a lead): ${b.scopeSummary}`,
    b.details && `Notes: ${b.details}`,
  ].filter(Boolean) as string[];

/**
 * The default brief for a Dann session about a board item. Only a confirmed
 * snapshot supplies scope and authorization (and links the run to the program);
 * everything else is explicitly passive.
 */
export function dannSession(item: BoardItem): DannSession {
  const b = item.bounty;
  const known = facts(b).join("\n");
  if (item.stage === "confirmed") {
    return {
      task:
        `Plan an engagement for the bug bounty program below, within its confirmed scope snapshot.\n\n${known}\n\n` +
        `Check what we already have (find_prior_work, get_scope), have Saudade map the in-scope attack surface from public sources ` +
        `and Dahlia research known issues in the technologies found, then propose a prioritized test plan. ` +
        `Do not start active testing; I'll arm it separately once I've reviewed the plan.`,
      scope: scopeText(item.bounty),
      authorization: authorizationText(item.bounty),
      programId: item.bounty.id,
    };
  }
  return {
    task:
      `Brief me on this bug bounty program and whether it's worth pursuing.\n\n${known}\n\n` +
      `Using passive public research only: check what we already have (find_prior_work), confirm rewards, scope and rules from ` +
      `the program's own pages, and note anything notable (recent changes, exclusions, safe harbor). ` +
      `${item.stage === "lead" ? "Recommend whether I should track it. " : "Have Sen propose structured scope if none is pending. "}` +
      `No scope has been confirmed, so do not contact any of the program's assets.`,
    scope: `No confirmed scope. Passive research about ${b.name} (${b.url}) only.`,
    authorization: "",
  };
}

/** The Saudade run behind the board's "Scout bounties" button. */
export function scoutTask(focus: string): string {
  const f = focus.trim();
  return (
    `Use the bounty-scout skill to find bug bounty programs for the operator's bounty board and record each one with ` +
    `record_program_lead, including rewards, asset types, details, and sources.` +
    (f ? `\n\nFocus: ${f}` : "\n\nNo particular focus: prefer active, paid programs with clear published scope.") +
    `\n\nPassive research only: read public directories and program pages; never contact a program's assets.`
  );
}
