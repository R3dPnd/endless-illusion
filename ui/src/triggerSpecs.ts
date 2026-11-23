import type { AgentPolicy } from "./types";

/**
 * Per-agent Trigger form. Each agent shows only the inputs its job uses, with
 * labels in its own terms. Every field folds into the three things a run
 * carries (task, scope, authorization), so the hub API is unchanged.
 */
export interface TriggerField {
  key: string;
  label: string;
  placeholder: string;
  rows?: number;
  required?: boolean;
  /** Where the value goes. "task" fields are appended to the task under their label. */
  into: "scope" | "authorization" | "task";
}

export interface TriggerSpec {
  taskLabel: string;
  taskPlaceholder: string;
  taskRows?: number;
  fields: TriggerField[];
  /** Offer the confirmed-program picker (it fills scope and authorization). */
  program: boolean;
  submitLabel: string;
}

const SCOPE = (label: string, placeholder: string, required = false): TriggerField => ({ key: "scope", label, placeholder, into: "scope", required });
const AUTH = (label = "Authorization"): TriggerField => ({
  key: "authorization",
  label,
  placeholder: "Bounty program + link, signed SOW reference, or owner's written permission. Leave blank for passive-only.",
  into: "authorization",
});

export const TRIGGER_SPECS: Record<string, TriggerSpec> = {
  "dann-of-thursday": {
    taskLabel: "Objective",
    taskPlaceholder: "What should the team accomplish? Dann routes it to the right specialists.",
    fields: [SCOPE("Scope / target(s)", "In-scope assets, domains, IP ranges, exclusions…"), AUTH()],
    program: true,
    submitLabel: "Brief Dann",
  },
  "saudade-of-sunday": {
    taskLabel: "What to map",
    taskPlaceholder: "e.g. Map the public attack surface of example.com",
    fields: [
      SCOPE("Target(s)", "Domains, organizations, IP ranges — plus anything off-limits", true),
      AUTH("Authorization — active recon only"),
    ],
    program: true,
    submitLabel: "Start recon",
  },
  "diablo-of-monday": {
    taskLabel: "Test objective",
    taskPlaceholder: "e.g. Review authentication and session handling on the customer portal",
    fields: [
      SCOPE("In-scope web app(s)", "URLs/hosts in scope, plus exclusions and rate limits", true),
      { key: "roles", label: "Test accounts / roles", placeholder: "Role names the program provides (e.g. admin, member) — don't paste passwords", into: "task" },
      AUTH(),
    ],
    program: true,
    submitLabel: "Start web testing",
  },
  "metsa-of-tuesday": {
    taskLabel: "Test objective",
    taskPlaceholder: "e.g. Check object-level authorization on the orders API",
    fields: [
      SCOPE("In-scope API(s)", "Base URLs / endpoints in scope, plus exclusions and rate limits", true),
      { key: "spec", label: "API spec / docs", placeholder: "OpenAPI / GraphQL schema URL or docs link", into: "task" },
      AUTH(),
    ],
    program: true,
    submitLabel: "Start API testing",
  },
  "dahlia-of-wednesday": {
    taskLabel: "Technology, version, or CVE",
    taskPlaceholder: "e.g. nginx 1.24.0 + OpenSSL 3.0.2 — or CVE-2024-3094",
    taskRows: 2,
    fields: [{ key: "focus", label: "What do you want to know?", placeholder: "e.g. Anything exploited in the wild? Which fix version should we target?", rows: 2, into: "task" }],
    program: false,
    submitLabel: "Research known issues",
  },
  "sin-of-friday": {
    taskLabel: "PoC or advisory to analyze",
    taskPlaceholder: "CVE id, advisory link, or public PoC URL",
    taskRows: 2,
    fields: [
      {
        key: "purpose",
        label: "Defensive purpose",
        placeholder: "e.g. Write detections for our WAF; judge patch urgency",
        rows: 2,
        required: true,
        into: "task",
      },
    ],
    program: false,
    submitLabel: "Analyze",
  },
  "sen-of-saturday": {
    taskLabel: "Request",
    taskPlaceholder: "e.g. Is api.example.com in scope for Program X? — or: Draft a report for finding #12",
    fields: [SCOPE("Program & assets in question", "Program link or name, and the assets/findings involved")],
    program: true,
    submitLabel: "Ask Sen",
  },
};

/** Spec for any agent; unknown agents get the full generic form. */
export function specFor(agent: AgentPolicy | undefined): TriggerSpec {
  return (
    (agent && TRIGGER_SPECS[agent.agent]) ?? {
      taskLabel: "Task",
      taskPlaceholder: "What should this agent do?",
      fields: [SCOPE("Scope / target(s)", "In-scope assets, domains, IP ranges, exclusions…"), AUTH()],
      program: true,
      submitLabel: "Trigger agent",
    }
  );
}

export interface ComposedRun {
  task: string;
  scope: string;
  authorization: string;
}

/** Fold the visible fields into a run. Fields the agent doesn't show are never sent. */
export function composeRun(spec: TriggerSpec, task: string, values: Record<string, string>): ComposedRun {
  const val = (f: TriggerField) => (values[f.key] ?? "").trim();
  const extras = spec.fields.filter((f) => f.into === "task" && val(f)).map((f) => `${f.label}:\n${val(f)}`);
  const join = (into: TriggerField["into"]) =>
    spec.fields
      .filter((f) => f.into === into)
      .map(val)
      .filter(Boolean)
      .join("\n\n");
  return { task: [task.trim(), ...extras].join("\n\n"), scope: join("scope"), authorization: join("authorization") };
}

/** Required fields (and the task) are filled in. */
export function isComplete(spec: TriggerSpec, task: string, values: Record<string, string>): boolean {
  return task.trim().length > 0 && spec.fields.every((f) => !f.required || (values[f.key] ?? "").trim().length > 0);
}
