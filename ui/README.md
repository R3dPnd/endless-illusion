# Endless Illusion — Control Plane

A local app for **triggering**, **monitoring**, and **remembering** the
Endless Illusion agents.

- **`hub/`** (repo root, Python, stdlib + pywebview): the server that spawns
  the `claude` CLI from the repo root (so `CLAUDE.md` + `.claude/agents/`
  load), streams Claude Code's `stream-json` events over SSE, archives every
  run to SQLite, runs each agent's memory MCP server, and hosts the desktop
  window.
- **`ui/`** (this folder, React + TypeScript): the client the hub serves.

Tabs: **Console** (agent channel, trigger, monitor) · **Bounties** (program
pipeline) · **Archive** (past runs, findings, CVE notes, submissions).

```
desktop window (pywebview / WebView2)
  └─ React client ──/api──▶ hub (Python, in-process) ──spawn──▶ claude -p --output-format stream-json
            ▲                       │                                 │
            └──────── SSE ◀─────────┴──────── parsed events ◀─────────┘
```

## Run it

From the repo root:

```bash
python pnd.py              # desktop app (creates .venv, builds the client when stale)
python pnd.py --dev        # desktop window on the Vite dev server (hot reload)
python pnd.py --web        # browser setup: hub API on :8787 + Vite on :5173
python pnd.py --test       # hub tests (pytest) + client tests (vitest)
python pnd.py --sync       # regenerate .claude/agents tool lists first
```

On Windows, `ei` (from `C:\Git\pnd\pnd-scripts`) runs `pnd.py` from any
prompt. `scripts/install-shortcut.ps1` adds Start-menu and desktop shortcuts.

Requires Python 3.11+, and the `claude` CLI on your PATH and authenticated
(override with `CLAUDE_BIN`). Node is needed only to build or serve the
client; once `ui/dist` is built the desktop app runs on Python alone.

Desktop keys: **F11** fullscreen, **Ctrl +/−/0** UI scale, **F5** reload
(`--debug` adds devtools on **F12**). Window size and position are restored.

## Display adaptation

The **◧ 100%** button in the header opens display settings. Each control has
an *Auto* mode resolved from the display the page detects (logical size, OS
scale, touch), re-resolved on resize or when the window moves to a monitor
with a different scale:

| Profile | Detected when | Auto choices |
|---|---|---|
| handheld | ≤1366×800 logical + touch | compact density, reduced effects, large touch targets |
| compact | ≤1366×800 logical, no touch | compact density |
| desktop | everything else | comfortable (compact under 900px tall) |
| large | ≥2400 logical px wide | 125–150% scale, spacious density |

Overrides: scale (60–200%), density, effects (full / reduced = no scanlines /
off = no glow or animation), touch-target size, and a readable body font.
Prefs persist in `%APPDATA%\EndlessIllusion` (desktop) or `localStorage`
(browser). On short, wide windows the Console fits one screen —
agents | trigger | channel over monitor — and each panel scrolls on its own.

## How it works

- **`GET /api/agents`** — reads `agents/*.policy.json` for the roster.
- **`POST /api/runs`** — starts a run. The prompt (task/scope/authorization) is
  passed to `claude` via **stdin**, so no user input ever reaches the command
  line. Returns a run id.
- **`GET /api/runs/:id/events`** — Server-Sent Events: session init, assistant
  text, tool calls, subagent delegations, and the final result. Finished runs
  replay from the archive.
- **`POST /api/runs/:id/stop`** — kills the `claude` process tree.

### Routing

- Select **Dann of Thursday** → the run is *orchestrated*: Dann routes to the
  specialist subagents (you'll see `→ delegate` events in the monitor).
- Select any specialist → it runs *directly*, with its dossier + the shared
  Rules of Engagement appended as the system prompt.

### Safety model (mirrors the policy files)

- **Passive by default.** Every run starts with the agent's `default_safe`
  toolset — no `Bash`, no live traffic. Sessions are restricted with `--tools`
  and `--strict-mcp-config`; `--allowedTools` alone only pre-approves tools and
  never withholds them. Orchestrated runs run as `--agent dann-of-thursday`.
- **Active tools are gated.** The active toolset (which adds `Bash`) is attached
  *only* when all three hold: the agent is active-capable, you've entered
  authorization text, and you tick the confirm box. The hub re-checks this;
  the UI toggle alone can't arm it.
- **Cross-site guard.** POSTs must be JSON from the UI's origin, so a web page
  you visit can't start runs or confirm scope on your localhost server.
- **Localhost-only.** The hub binds to `127.0.0.1`. Don't expose it to a
  network without adding authentication — it can trigger real agent runs.

## Persistence

- Everything lives in `data/endless-illusion.db` at the repo root (gitignored).
  Override the directory with `EI_DATA_DIR`. Schema: `hub/migrations/`.
- The hub records every run, its event stream, subagent reports, and final
  results. Runs still marked running at startup become `interrupted`.
- **Agent memory:** each run mounts one `hub/memory.py` MCP server per
  participating agent. Every agent can read everything (`find_prior_work`,
  `search_reports`, `get_cve_note`, `list_programs`, `get_scope`, …) but can
  only append to its own tables (see `hub/db/ownership.py`). Records are
  append-only; corrections supersede.
- **Bounties:** Saudade and Dahlia record program *leads*; you Track or Dismiss
  them; Sen *proposes* scope; only you can **Confirm** it into a dated snapshot.
  Only confirmed scope can be linked to a run (Trigger → Program).
- After changing a policy or the ownership map, run
  `python -m hub.sync_agent_tools` to regenerate the agents' tool lists.

## Tests

`python pnd.py --test` runs both suites. `tests/` (pytest) covers the
database, ownership enforcement through the MCP server over stdio, archiving
with a fake `claude`, the HTTP API and CSRF guard, and the agent configs.
`ui/test/` (vitest) covers the client's chat builder.
