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
