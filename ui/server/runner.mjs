import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { EventEmitter } from "node:events";
import path from "node:path";
import crypto from "node:crypto";
import { AGENTS, OWNERSHIP } from "../db/ownership.mjs";
import { addReport, appendEvent, createRun, finishRun } from "../db/archive.mjs";
import { qualifiedToolsFor } from "../mcp/tool-names.mjs";
import { cleanReport, DELEGATE_TOOLS, resultText } from "../shared/report.mjs";
import { getPolicy, loadPolicies } from "./policies.mjs";
import { buildPrompt } from "./prompt.mjs";
import { buildSessionArgs, writeMcpConfig } from "./session.mjs";

export const ORCHESTRATOR = "dann-of-thursday";

/** Decide the built-in toolset for a run (mirrors agents/*.policy.json). */
async function resolveTools({ agentsDir, agent, orchestrated, enableActive, authorization, policy }) {
  if (orchestrated) {
    // Union of every agent's passive toolset, plus Agent to delegate.
    const passive = new Set(["Agent"]);
    for (const p of await loadPolicies(agentsDir)) (p.tools?.default_safe || []).forEach((t) => passive.add(t));
    return { tools: [...passive], activeEngaged: false };
  }
  const canGoActive =
    enableActive &&
    authorization.trim().length > 0 &&
    Array.isArray(policy.tools?.authorized_active) &&
    policy.tools.authorized_active.length > 0;
  if (canGoActive) return { tools: policy.tools.authorized_active, activeEngaged: true };
  return { tools: policy.tools?.default_safe || ["Read"], activeEngaged: false };
}

/**
 * Spawns claude runs, streams their events to listeners, and archives every
 * run, event, and report. Archive failures surface as "warn" events and never
 * stop a run.
 */
export function createRunner({ db, dbFile, dataDir, claudeBin, repoRoot }) {
  const agentsDir = path.join(repoRoot, "agents");
  const live = new Map();

  async function start(body) {
    const { agent, task } = body;
    const scope = body.scope || "";
    const authorization = body.authorization || "";
    if (!agent || !task?.trim()) throw new Error("agent and task are required");
    const policy = await getPolicy(agentsDir, agent);
    if (!policy) throw new Error(`unknown agent: ${agent}`);

    const orchestrated = agent === ORCHESTRATOR;
    const { tools, activeEngaged } = await resolveTools({
      agentsDir, agent, orchestrated, enableActive: Boolean(body.enableActive), authorization, policy,
    });

    // Direct runs carry the agent's dossier + the RoE, as the subagent would.
    let systemPrompt;
    if (!orchestrated) {
      try {
        const dossier = await readFile(path.join(agentsDir, `${agent}.md`), "utf8");
        const roe = await readFile(path.join(repoRoot, "RULES-OF-ENGAGEMENT.md"), "utf8");
        systemPrompt = `${dossier}\n\n---\n\n${roe}`;
      } catch (err) {
        console.error(`[dossier] ${agent}:`, err.message);
      }
    }

    const id = crypto.randomUUID();
    const memoryAgents = orchestrated ? AGENTS : OWNERSHIP[agent] ? [agent] : [];
    const mcpConfigPath = memoryAgents.length
      ? writeMcpConfig(path.join(dataDir, "run-configs"), id, memoryAgents, dbFile)
      : undefined;
    const args = buildSessionArgs({
      tools,
      mcpConfigPath,
      mcpTools: memoryAgents.flatMap(qualifiedToolsFor),
      agentDef: orchestrated ? ORCHESTRATOR : undefined,
      systemPrompt,
    });

    const run = {
      id, agent, orchestrated, activeEngaged, tools,
      status: "running", events: [], emitter: new EventEmitter(), proc: null, result: null,
      programId: body.programId ?? null, snapshotId: body.snapshotId ?? null,
    };
    live.set(id, run);

    let seq = 0;
    const archive = (what, fn) => {
      try {
        fn();
      } catch (err) {
        console.error(`[archive] ${what}:`, err.message);
        const warn = { kind: "warn", text: `archive ${what} failed: ${err.message}`, ts: Date.now() };
        run.events.push(warn);
        run.emitter.emit("event", warn);
      }
    };
    const push = (evt) => {
      run.events.push(evt);
      run.emitter.emit("event", evt);
      const n = seq++;
      archive("event", () => appendEvent(db, id, n, evt));
    };

    archive("run", () =>
      createRun(db, { id, agent, task, scope, authorization, activeEngaged, tools, programId: run.programId, snapshotId: run.snapshotId }),
    );
    push({ kind: "meta", agent, orchestrated, activeEngaged, tools, ts: Date.now() });

    const delegations = new Map(); // tool_use id -> subagent id
    const collectReports = (data) => {
      const content = Array.isArray(data.message?.content) ? data.message.content : [];
      if (data.type === "assistant") {
        for (const b of content) {
          if (b.type === "tool_use" && DELEGATE_TOOLS.has(b.name) && b.input?.subagent_type) delegations.set(b.id, b.input.subagent_type);
        }
      } else if (data.type === "user") {
        for (const b of content) {
          const sub = b.type === "tool_result" && delegations.get(b.tool_use_id);
          if (!sub) continue;
          const { text, meta } = cleanReport(resultText(b.content));
          if (text) archive("report", () => addReport(db, { runId: id, agent: sub, kind: "subagent_report", text, meta: meta ? { stats: meta } : null }));
        }
      } else if (data.type === "result" && typeof data.result === "string") {
        archive("report", () =>
          addReport(db, {
            runId: id, agent, kind: "final", text: data.result,
            meta: { cost_usd: data.total_cost_usd, duration_ms: data.duration_ms, num_turns: data.num_turns, is_error: !!data.is_error },
          }),
        );
      }
    };

    const proc = spawn(claudeBin, args, { cwd: repoRoot, windowsHide: true, env: process.env });
    run.proc = proc;
    proc.stdin.on("error", () => {}); // child may exit before reading the prompt
    proc.stdin.end(buildPrompt({ agent, task, scope, authorization, orchestrated }));

    createInterface({ input: proc.stdout }).on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let obj;
      try {
        obj = JSON.parse(trimmed);
      } catch {
        push({ kind: "stdout", text: trimmed, ts: Date.now() });
        return;
      }
      if (obj.type === "result") run.result = obj;
      push({ kind: "claude", data: obj, ts: Date.now() });
      collectReports(obj);
    });

    proc.stderr.on("data", (d) => push({ kind: "stderr", text: d.toString(), ts: Date.now() }));

    const finish = () => {
      archive("finish", () =>
        finishRun(db, id, { status: run.status, costUsd: run.result?.total_cost_usd, durationMs: run.result?.duration_ms }),
      );
      run.emitter.emit("done");
    };

    proc.on("error", (err) => {
      run.status = "error";
      push({ kind: "error", text: `spawn failed: ${err.message}`, ts: Date.now() });
      finish();
    });

    proc.on("close", (code) => {
      if (run.status === "error") return; // spawn failure already finished the run
      run.status = run.status === "stopped" ? "stopped" : code === 0 ? "done" : "error";
      push({ kind: "closed", code, status: run.status, ts: Date.now() });
      finish();
    });

    return run;
  }

  function stop(id) {
    const run = live.get(id);
    if (!run) return null;
    if (run.proc && run.status === "running") {
      run.status = "stopped";
      run.proc.kill();
    }
    return run;
  }

  return { start, stop, get: (id) => live.get(id) };
}
