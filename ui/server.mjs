// Endless Illusion — agent trigger/monitor backend.
// Spawns the `claude` CLI from the repo root (so CLAUDE.md + .claude/agents/
// load) and streams its stream-json events to the browser over SSE.
// Binds to 127.0.0.1 only. User input is passed via stdin, never argv.

import express from "express";
import { spawn } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { EventEmitter } from "node:events";
import path from "node:path";
import crypto from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const AGENTS_DIR = path.join(REPO_ROOT, "agents");
const CLAUDE_BIN = process.env.CLAUDE_BIN || "claude";
const PORT = Number(process.env.PORT || 8787);
const HOST = "127.0.0.1";

const ORCHESTRATOR = "dann-of-thursday";

/** In-memory run registry. Not persisted — fine for a local control panel. */
const runs = new Map();

// ---- policy loading -------------------------------------------------------

async function loadPolicies() {
  const files = (await readdir(AGENTS_DIR)).filter((f) =>
    f.endsWith(".policy.json")
  );
  const policies = [];
  for (const f of files) {
    try {
      const raw = await readFile(path.join(AGENTS_DIR, f), "utf8");
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

async function getPolicy(agent) {
  const policies = await loadPolicies();
  return policies.find((p) => p.agent === agent) || null;
}

// ---- prompt + invocation --------------------------------------------------

function buildPrompt({ agent, task, scope, authorization, orchestrated }) {
  const authLine = authorization?.trim()
    ? authorization.trim()
    : "NONE PROVIDED — treat this as unauthorized; passive work only.";
  const scopeLine = scope?.trim() ? scope.trim() : "(none specified)";
  const head = orchestrated
    ? "Per CLAUDE.md you are Dann of Thursday, the orchestrator. Confirm authorization, then route this to the right specialist subagent(s)."
    : `Operate strictly as the agent described in the appended dossier. Follow its Rules of Engagement.`;
  return [
    head,
    "",
    `TASK:\n${task.trim()}`,
    "",
    `SCOPE:\n${scopeLine}`,
    "",
    `AUTHORIZATION:\n${authLine}`,
    "",
    "If no authorization is established, do the passive part, refuse the active part, and say what is missing. Report honestly; distinguish confirmed from suspected.",
  ].join("\n");
}

async function startRun(body) {
  const { agent, task } = body;
  const scope = body.scope || "";
  const authorization = body.authorization || "";
  const enableActive = Boolean(body.enableActive);

  if (!agent || !task?.trim()) {
    throw new Error("agent and task are required");
  }
  const policy = await getPolicy(agent);
  if (!policy) throw new Error(`unknown agent: ${agent}`);

  const orchestrated = agent === ORCHESTRATOR;

  // ---- tool gating (mirrors the policy files) ----
  let tools;
  let activeEngaged = false;
  if (orchestrated) {
    // Union of every agent's passive toolset, plus Task to delegate.
    const policies = await loadPolicies();
    const passive = new Set(["Task"]);
    for (const p of policies) (p.tools?.default_safe || []).forEach((t) => passive.add(t));
    tools = [...passive];
  } else {
    const canGoActive =
      enableActive &&
      authorization.trim().length > 0 &&
      Array.isArray(policy.tools?.authorized_active) &&
      policy.tools.authorized_active.length > 0;
    if (canGoActive) {
      tools = policy.tools.authorized_active;
      activeEngaged = true;
    } else {
      tools = policy.tools?.default_safe || ["Read"];
    }
  }

  // ---- build CLI args (no user input here — only controlled values) ----
  const args = [
    "-p",
    "--output-format", "stream-json",
    "--verbose",
    "--allowedTools", tools.join(","),
  ];

  // For a specific (non-orchestrator) agent, append its dossier + the RoE so a
  // direct invocation carries the same persona and rules the subagent would.
  if (!orchestrated) {
    let sys = "";
    try {
      const dossier = await readFile(path.join(AGENTS_DIR, `${agent}.md`), "utf8");
      const roe = await readFile(path.join(REPO_ROOT, "RULES-OF-ENGAGEMENT.md"), "utf8");
      sys = `${dossier}\n\n---\n\n${roe}`;
    } catch (err) {
      console.error(`[dossier] ${agent}:`, err.message);
    }
    if (sys) args.push("--append-system-prompt", sys);
  }

  const prompt = buildPrompt({ agent, task, scope, authorization, orchestrated });

  const id = crypto.randomUUID();
  const emitter = new EventEmitter();
  const run = {
    id,
    agent,
    orchestrated,
    activeEngaged,
    tools,
    status: "running",
    startedAt: Date.now(),
    events: [],
    emitter,
    proc: null,
    result: null,
  };
  runs.set(id, run);

  const push = (evt) => {
    run.events.push(evt);
    emitter.emit("event", evt);
  };

  push({ kind: "meta", agent, orchestrated, activeEngaged, tools, ts: Date.now() });

  const proc = spawn(CLAUDE_BIN, args, {
    cwd: REPO_ROOT,
    windowsHide: true,
    env: process.env,
  });
  run.proc = proc;

  proc.stdin.write(prompt);
  proc.stdin.end();

  const rl = createInterface({ input: proc.stdout });
  rl.on("line", (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    try {
      const obj = JSON.parse(trimmed);
      if (obj.type === "result") run.result = obj;
      push({ kind: "claude", data: obj, ts: Date.now() });
    } catch {
      push({ kind: "stdout", text: trimmed, ts: Date.now() });
    }
  });

  let stderr = "";
  proc.stderr.on("data", (d) => {
    stderr += d.toString();
    push({ kind: "stderr", text: d.toString(), ts: Date.now() });
  });

  proc.on("error", (err) => {
    run.status = "error";
    push({ kind: "error", text: `spawn failed: ${err.message}`, ts: Date.now() });
    emitter.emit("done");
  });

  proc.on("close", (code) => {
    run.status = run.status === "stopped" ? "stopped" : code === 0 ? "done" : "error";
    run.exitCode = code;
    push({ kind: "closed", code, status: run.status, ts: Date.now() });
    emitter.emit("done");
  });

  return run;
}

// ---- HTTP -----------------------------------------------------------------

const app = express();
app.use(express.json({ limit: "1mb" }));

app.get("/api/agents", async (_req, res) => {
  try {
    res.json(await loadPolicies());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post("/api/runs", async (req, res) => {
  try {
    const run = await startRun(req.body);
    res.json({ id: run.id, agent: run.agent, status: run.status, tools: run.tools, activeEngaged: run.activeEngaged });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

app.get("/api/runs/:id/events", (req, res) => {
  const run = runs.get(req.params.id);
  if (!run) return res.status(404).end();

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.write(`retry: 2000\n\n`);

  // Replay anything already buffered, then stream live.
  for (const evt of run.events) res.write(`data: ${JSON.stringify(evt)}\n\n`);

  if (run.status !== "running") {
    res.write(`event: done\ndata: {}\n\n`);
    return res.end();
  }

  const onEvent = (evt) => res.write(`data: ${JSON.stringify(evt)}\n\n`);
  const onDone = () => {
    res.write(`event: done\ndata: {}\n\n`);
    res.end();
  };
  run.emitter.on("event", onEvent);
  run.emitter.once("done", onDone);

  req.on("close", () => {
    run.emitter.off("event", onEvent);
    run.emitter.off("done", onDone);
  });
});

app.post("/api/runs/:id/stop", (req, res) => {
  const run = runs.get(req.params.id);
  if (!run) return res.status(404).json({ error: "no such run" });
  if (run.proc && run.status === "running") {
    run.status = "stopped";
    run.proc.kill();
  }
  res.json({ status: run.status });
});

app.listen(PORT, HOST, () => {
  console.log(`Endless Illusion control plane on http://${HOST}:${PORT}`);
  console.log(`Repo root: ${REPO_ROOT}`);
  console.log(`claude bin: ${CLAUDE_BIN}`);
});
