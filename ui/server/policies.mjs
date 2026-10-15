import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

/** Agent policies from agents/*.policy.json, orchestrator first then by weekday. */
export async function loadPolicies(agentsDir) {
  const files = (await readdir(agentsDir)).filter((f) =>
    f.endsWith(".policy.json")
  );
  const policies = [];
  for (const f of files) {
    try {
      const raw = await readFile(path.join(agentsDir, f), "utf8");
      policies.push(JSON.parse(raw));
    } catch (err) {
      console.error(`[policy] failed to read ${f}:`, err.message);
    }
  }
  // Orchestrator first, then by day order.
  const order = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
  ];
  policies.sort((a, b) => {
    if (a.role === "orchestrator") return -1;
    if (b.role === "orchestrator") return 1;
    return order.indexOf(a.day) - order.indexOf(b.day);
  });
  return policies;
}

export async function getPolicy(agentsDir, agent) {
  const policies = await loadPolicies(agentsDir);
  return policies.find((p) => p.agent === agent) || null;
}
