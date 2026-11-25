import { describe, expect, it } from "vitest";
import { approveNeedsAck, cardButtons, stageButtons, verdictLabel } from "./engagement";
import type { GateAction, StageView } from "./types";

const card = (verdict: GateAction["verdict"]) => ({ verdict }) as GateAction;
const stage = (s: Partial<StageView>) => s as StageView;

describe("cardButtons", () => {
  it("never offers approve for an out-of-scope action", () => {
    const b = cardButtons(card("out"));
    expect(b).not.toContain("approve");
    expect(b).toContain("deny");
    expect(b).toContain("denyWithReason");
  });
  it("offers everything otherwise", () => {
    expect(cardButtons(card("in"))).toEqual(["approve", "deny", "denyWithReason", "ask"]);
  });
});

describe("approveNeedsAck", () => {
  it("is true for unknown and none, false for in", () => {
    expect(approveNeedsAck(card("unknown"))).toBe(true);
    expect(approveNeedsAck(card("none"))).toBe(true);
    expect(approveNeedsAck(card("in"))).toBe(false);
  });
});

describe("stageButtons", () => {
  it("is empty when locked", () => expect(stageButtons(stage({ status: "locked" }))).toEqual([]));
  it("offers start and arm when ready and armable", () => {
    const b = stageButtons(stage({ status: "ready", canArm: true }));
    expect(b).toContain("start");
    expect(b).toContain("arm");
  });
  it("omits arm when not armable", () => {
    expect(stageButtons(stage({ status: "ready", canArm: false }))).not.toContain("arm");
  });
  it("offers stop when running", () => expect(stageButtons(stage({ status: "running" }))).toContain("stop"));
  it("offers open when there is a run", () => {
    expect(stageButtons(stage({ status: "done", runId: "r1" }))).toContain("open");
  });
});

describe("verdictLabel", () => {
  it("labels all four verdicts", () => {
    expect(verdictLabel("in")).toBe("✓ in scope");
    expect(verdictLabel("out")).toBe("✗ out of scope");
    expect(verdictLabel("unknown")).toBe("? can't tell");
    expect(verdictLabel("none")).toBe("no target host");
  });
});

// ---- final-review fixes ----

import { pendingElsewhere, planIsApproved, startBody } from "./engagement";
import type { EngagementDetail } from "./types";

const plan = (draft: { id: number } | null, approved: { id: number; draft_id: number } | null) =>
  ({ draft: draft && { ...draft, plan: { stages: {} } }, approved: approved && { ...approved, plan: { stages: {} } } }) as EngagementDetail["plan"];

describe("planIsApproved (I2)", () => {
  it("compares the approved plan's draft_id with the draft's id, not the two row ids", () => {
    expect(planIsApproved(plan({ id: 7 }, { id: 1, draft_id: 7 }))).toBe(true);
    expect(planIsApproved(plan({ id: 7 }, { id: 7, draft_id: 3 }))).toBe(false); // same number, different tables
    expect(planIsApproved(plan({ id: 8 }, { id: 1, draft_id: 7 }))).toBe(false); // a newer draft
    expect(planIsApproved(plan(null, { id: 1, draft_id: 7 }))).toBe(false);
    expect(planIsApproved(plan({ id: 7 }, null))).toBe(false);
  });
});

describe("startBody (D1)", () => {
  it("sends armed only when ticked AND the arm control is offered", () => {
    expect(startBody(true, ["start", "arm"], false, "")).toEqual({ armed: true });
    expect(startBody(true, ["rerun"], false, "")).toEqual({}); // a stale tick on a card that cannot arm
    expect(startBody(false, ["start", "arm"], false, "")).toEqual({});
  });
  it("adds the trimmed question for research", () => {
    expect(startBody(false, ["start"], true, "  what?  ")).toEqual({ question: "what?" });
  });
});

describe("pendingElsewhere (M4)", () => {
  const a = (id: number, engagement_id: number) => ({ id, engagement_id }) as GateAction;
  it("counts pending actions per engagement other than the selected one", () => {
    expect(pendingElsewhere([a(1, 1), a(2, 2), a(3, 2), a(4, 3)], 1)).toEqual([
      { engagementId: 2, count: 2 },
      { engagementId: 3, count: 1 },
    ]);
    expect(pendingElsewhere([a(1, 1)], 1)).toEqual([]);
    expect(pendingElsewhere([a(1, 1)], null)).toEqual([{ engagementId: 1, count: 1 }]);
  });
});
