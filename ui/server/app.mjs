import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openDb } from "../db/index.mjs";
import { getRun, getRunEvents, markInterrupted } from "../db/archive.mjs";
import { HttpError, requireConfirmedSnapshot } from "../db/bounties.mjs";
import { requireJsonSameOrigin } from "./csrf.mjs";
import { archiveRoutes } from "./routes-archive.mjs";
import { bountyRoutes } from "./routes-bounties.mjs";
import { loadPolicies } from "./policies.mjs";
import { createRunner } from "./runner.mjs";

const DEFAULT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/** Build the hub: database, run manager, and HTTP routes. Listening is the caller's job. */
export function createApp({
  repoRoot = DEFAULT_ROOT,
  dataDir = path.join(repoRoot, "data"),
  dbFile = path.join(dataDir, "endless-illusion.db"),
  claudeBin = "claude",
  allowedOrigins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8787", "http://127.0.0.1:8787"],
} = {}) {
  const db = openDb(dbFile);
  const interrupted = markInterrupted(db);
  if (interrupted) console.log(`[archive] marked ${interrupted} unfinished run(s) interrupted`);

  const runner = createRunner({ db, dbFile, dataDir, claudeBin, repoRoot });
  const app = express();
  app.use("/api", requireJsonSameOrigin(allowedOrigins));
  app.use(express.json({ limit: "1mb" }));
  app.use("/api", bountyRoutes(db));
  app.use("/api", archiveRoutes(db, repoRoot));

  app.get("/api/agents", async (_req, res) => {
    try {
      res.json(await loadPolicies(path.join(repoRoot, "agents")));
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/runs", async (req, res) => {
    try {
      const body = req.body ?? {};
      const link = body.programId != null ? { programId: Number(body.programId), snapshotId: requireConfirmedSnapshot(db, body.programId) } : {};
      const run = await runner.start(body, link);
      res.json({ id: run.id, agent: run.agent, status: run.status, tools: run.tools, activeEngaged: run.activeEngaged });
    } catch (err) {
      res.status(err instanceof HttpError ? err.status : 400).json({ error: err.message });
    }
  });

  app.get("/api/runs/:id/events", (req, res) => {
    const run = runner.get(req.params.id);
    if (!run) {
      // Not live (finished before a restart, or from an earlier session): replay from the archive.
      if (!getRun(db, req.params.id)) return res.status(404).end();
      res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
      for (const evt of getRunEvents(db, req.params.id)) res.write(`data: ${JSON.stringify(evt)}\n\n`);
      res.write("event: done\ndata: {}\n\n");
      return res.end();
    }
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
