import type { ConfirmedProgram, ScopeItem } from "./types";

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
