import { describe, it, expect } from "vitest";
import { buildSessionArgs } from "../server/session.mjs";

const valueOf = (args, flag) => args[args.indexOf(flag) + 1];

describe("buildSessionArgs", () => {
  it("restricts built-ins with --tools and isolates MCP", () => {
    const a = buildSessionArgs({ tools: ["Read", "Grep"] });
    expect(valueOf(a, "--tools")).toBe("Read,Grep");
    expect(a).toContain("--strict-mcp-config");
  });

  it("never offers Bash unless listed", () => {
    const a = buildSessionArgs({ tools: ["Read"] });
    expect(a.join(" ")).not.toMatch(/Bash/);
  });

  it("pre-approves MCP tools and passes the config + agent", () => {
    const a = buildSessionArgs({
      tools: ["Task"],
      mcpConfigPath: "/x.json",
      mcpTools: ["mcp__ei-dann__list_programs"],
      agentDef: "dann-of-thursday",
    });
    expect(valueOf(a, "--mcp-config")).toBe("/x.json");
    expect(valueOf(a, "--allowedTools")).toBe("Task,mcp__ei-dann__list_programs");
    expect(valueOf(a, "--agent")).toBe("dann-of-thursday");
  });
});
