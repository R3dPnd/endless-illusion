# Endless Illusion — Control Plane (UI)

A local React UI for **triggering**, **monitoring**, and **remembering** the
Endless Illusion agents. It talks to an Express backend that spawns the `claude`
CLI from the repo root (so `CLAUDE.md` + `.claude/agents/` load), streams Claude
Code's `stream-json` events to the browser over SSE, and archives every run to a
local SQLite database.

Tabs: **Console** (agent channel, trigger, monitor) · **Bounties** (program
pipeline) · **Archive** (past runs, findings, CVE notes, submissions).

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
  toolset — no `Bash`, no live traffic. Sessions are restricted with `--tools`
  and `--strict-mcp-config`; `--allowedTools` alone only pre-approves tools and
  never withheld them. Orchestrated runs run as `--agent dann-of-thursday`.
- **Active tools are gated.** The active toolset (which adds `Bash`) is attached
  *only* when all three hold: the agent is active-capable, you've entered
  authorization text, and you tick the confirm box. The backend re-checks this;
  the UI toggle alone can't arm it.
- **Cross-site guard.** POSTs must be JSON from the UI's origin, so a web page
  you visit can't start runs or confirm scope on your localhost server.
- **Localhost-only.** The server binds to `127.0.0.1`. Don't expose it to a
  network without adding authentication — it can trigger real agent runs.

## Persistence

- Everything lives in `data/endless-illusion.db` at the repo root (gitignored,
  owner-only). Override the directory with `EI_DATA_DIR`.
- The hub records every run, its event stream, subagent reports, and final
  results. Runs still marked running at startup become `interrupted`.
- **Agent memory:** each run mounts one `ui/mcp/ei-memory.mjs` server per
  participating agent. Every agent can read everything (`find_prior_work`,
  `search_reports`, `get_cve_note`, `list_programs`, `get_scope`, …) but can
  only append to its own tables (see `ui/db/ownership.mjs`). Records are
  append-only; corrections supersede.
- **Bounties:** Saudade and Dahlia record program *leads*; you Track or Dismiss
  them; Sen *proposes* scope; only you can **Confirm** it into a dated snapshot.
  Only confirmed scope can be linked to a run (Trigger → Program).
- After changing a policy or the ownership map, run
  `node ui/scripts/sync-agent-tools.mjs` to regenerate the agents' tool lists.

## Tests

`npm test` (Vitest) covers the database, ownership enforcement through the MCP
server, archiving, the bounty APIs, the CSRF guard, and agent configs.

## Notes

- Stopping kills the top `claude` process; deeply nested children may linger
  briefly on Windows.
