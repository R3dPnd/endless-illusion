# Endless Illusion — Control Plane (UI)

A local React UI for **triggering** and **monitoring** the Endless Illusion
agents. It talks to a tiny Express backend that spawns the `claude` CLI from the
repo root (so `CLAUDE.md` + `.claude/agents/` load) and streams Claude Code's
`stream-json` events to the browser over SSE.

```
browser (React) ──/api──▶ server.mjs ──spawn──▶ claude -p --output-format stream-json
       ▲                        │                         │
       └────────── SSE ◀────────┴──── parsed events ◀──────┘
```

## Run it

```bash
cd ui
npm install
npm run dev
```

- Client: http://localhost:5173
- API:    http://127.0.0.1:8787 (localhost-only)

`npm run dev` runs both together. To run them separately: `npm run server` and
`npm run client`.

Requires the `claude` CLI on your PATH and already authenticated (the backend
shells out to it). Override the binary with `CLAUDE_BIN=/path/to/claude`.

## How it works

- **`GET /api/agents`** — reads `../agents/*.policy.json` for the roster.
- **`POST /api/runs`** — starts a run. The prompt (task/scope/authorization) is
  passed to `claude` via **stdin**, so no user input ever reaches the command
  line. Returns a run id.
- **`GET /api/runs/:id/events`** — Server-Sent Events: session init, assistant
  text, tool calls, subagent delegations, and the final result (with cost and
  `subagent_stats`).
- **`POST /api/runs/:id/stop`** — kills the `claude` process.

### Routing

- Select **Dann of Thursday** → the run is *orchestrated*: Dann routes to the
  specialist subagents (you'll see `→ delegate` events in the monitor).
- Select any specialist → it runs *directly*, with its dossier + the shared
  Rules of Engagement appended as the system prompt.

### Safety model (mirrors the policy files)

- **Passive by default.** Every run starts with the agent's `default_safe`
  toolset — no `Bash`, no live traffic.
- **Active tools are gated.** The active toolset (which adds `Bash`) is attached
  *only* when all three hold: the agent is active-capable, you've entered
  authorization text, and you tick the confirm box. The backend re-checks this;
  the UI toggle alone can't arm it.
- **Localhost-only.** The server binds to `127.0.0.1`. Don't expose it to a
  network without adding authentication — it can trigger real agent runs.

## Notes

- Runs are kept in memory; restarting the server clears history.
- Stopping kills the top `claude` process; deeply nested children may linger
  briefly on Windows.
