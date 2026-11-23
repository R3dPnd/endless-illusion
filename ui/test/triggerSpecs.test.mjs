import { describe, it, expect } from "vitest";
import { TRIGGER_SPECS, composeRun, isComplete, specFor } from "../src/triggerSpecs.ts";

const policy = (agent) => ({ agent, role: "x", classification: "x", needs_authorization: false, tools: { default_safe: [], authorized_active: [] } });

describe("trigger specs", () => {
  it("covers every agent", () => {
    for (const a of ["dann-of-thursday", "saudade-of-sunday", "diablo-of-monday", "metsa-of-tuesday", "dahlia-of-wednesday", "sin-of-friday", "sen-of-saturday"]) {
      expect(TRIGGER_SPECS[a], a).toBeDefined();
    }
  });

  it("never sends scope or authorization a passive agent doesn't show", () => {
    const run = composeRun(specFor(policy("dahlia-of-wednesday")), "nginx 1.24.0", { scope: "left over", authorization: "left over", focus: "KEV?" });
    expect(run).toEqual({ task: "nginx 1.24.0\n\nWhat do you want to know?:\nKEV?", scope: "", authorization: "" });
  });

  it("folds extra fields into the task and keeps scope/authorization for testers", () => {
    const run = composeRun(specFor(policy("metsa-of-tuesday")), "Check BOLA", { scope: "api.example.com", spec: "https://x/openapi.json", authorization: "H1 program" });
    expect(run.task).toBe("Check BOLA\n\nAPI spec / docs:\nhttps://x/openapi.json");
    expect(run.scope).toBe("api.example.com");
    expect(run.authorization).toBe("H1 program");
  });

  it("requires each agent's required fields", () => {
    const sin = specFor(policy("sin-of-friday"));
    expect(isComplete(sin, "CVE-2021-44228", {})).toBe(false);
    expect(isComplete(sin, "CVE-2021-44228", { purpose: "detections" })).toBe(true);
    expect(isComplete(specFor(policy("diablo-of-monday")), "x", {})).toBe(false);
  });

  it("falls back to the generic form for an unknown agent", () => {
    expect(specFor(policy("someone-new")).fields.map((f) => f.key)).toEqual(["scope", "authorization"]);
  });
});
