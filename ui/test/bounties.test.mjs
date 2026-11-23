import { describe, it, expect } from "vitest";
import { dannSession, scoutTask } from "../src/bounties.ts";

const details = { programType: "bounty", rewards: "$100 – $5,000", maxRewardUsd: 5000, assetTypes: ["web"], details: "Shop.", programUpdated: null, sources: [], scopeSummary: "*.shop.example" };
const lead = { ...details, normalizedUrl: "hackerone.com/shop", name: "Shop", platform: "HackerOne", url: "https://hackerone.com/shop", foundVia: "x", sightings: 1, agents: [], runIds: [], firstSeen: "", lastSeen: "" };
const program = { ...details, id: 7, name: "Shop", platform: "HackerOne", url: "https://hackerone.com/shop", normalizedUrl: "hackerone.com/shop", source: "lead", createdAt: "", proposals: [] };
const confirmed = { ...program, snapshot: { id: 3, inScope: [{ asset: "app.shop.example", type: "domain" }], outOfScope: [], exclusions: ["no DoS"], confirmedAt: "2026-11-01T00:00:00Z", stale: false } };

describe("dannSession", () => {
  it("keeps an unconfirmed bounty passive: no authorization, no program link", () => {
    for (const item of [{ stage: "lead", key: "l", bounty: lead }, { stage: "tracked", key: "t", bounty: program }]) {
      const s = dannSession(item);
      expect(s.authorization).toBe("");
      expect(s.programId).toBeUndefined();
      expect(s.task).toContain("$100 – $5,000");
      expect(s.task).toContain("do not contact");
    }
  });

  it("uses a confirmed snapshot as scope and authorization, and links the program", () => {
    const s = dannSession({ stage: "confirmed", key: "c", bounty: confirmed });
    expect(s.programId).toBe(7);
    expect(s.authorization).toContain("scope snapshot #3");
    expect(s.scope).toContain("app.shop.example");
    expect(s.task).toContain("Do not start active testing");
  });
});

describe("scoutTask", () => {
  it("names the skill and carries the operator's focus", () => {
    expect(scoutTask("fintech APIs")).toMatch(/bounty-scout[\s\S]*Focus: fintech APIs/);
    expect(scoutTask("  ")).not.toContain("Focus:");
  });
});
