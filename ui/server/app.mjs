import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openDb } from "../db/index.mjs";
import { markInterrupted } from "../db/archive.mjs";
import { loadPolicies } from "./policies.mjs";
import { createRunner } from "./runner.mjs";

const DEFAULT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/** Build the hub: database, run manager, and HTTP routes. Listening is the caller's job. */
export function createApp({
  repoRoot = DEFAULT_ROOT,
  dataDir = path.join(repoRoot, "data"),
  dbFile = path.join(dataDir, "endless-illusion.db"),
  claudeBin = "claude",
} = {}) {
  const db = openDb(dbFile);
  const interrupted = markInterrupted(db);
  if (interrupted) console.log(`[archive] marked ${interrupted} unfinished run(s) interrupted`);

  const runner = createRunner({ db, dbFile, dataDir, claudeBin, repoRoot });
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/api/agents", async (_req, res) => {
    try {
      res.json(await loadPolicies(path.join(repoRoot, "agents")));
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/runs", async (req, res) => {
    try {
      const run = await runner.start(req.body ?? {});
      res.json({ id: run.id, agent: run.agent, status: run.status, tools: run.tools, activeEngaged: run.activeEngaged });
    } catch (err) {
      res.status(400).json({ error: err.message });
    }
  });

  app.get("/api/runs/:id/events", (req, res) => {
    const run = runner.get(req.params.id);
    if (!run) return res.status(404).end();
    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
    res.write("retry: 2000\n\n");
    for (const evt of run.events) res.write(`data: ${JSON.stringify(evt)}\n\n`);
    if (run.status !== "running") {
      res.write("event: done\ndata: {}\n\n");
      return res.end();
    }
    const onEvent = (evt) => res.write(`data: ${JSON.stringify(evt)}\n\n`);
    const onDone = () => {
      res.write("event: done\ndata: {}\n\n");
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
    const run = runner.stop(req.params.id);
    if (!run) return res.status(404).json({ error: "no such run" });
    res.json({ status: run.status });
  });

  return { app, db, runner };
}
