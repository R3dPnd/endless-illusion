# Persistence: run archive, agent memory, and bounty tracking

- **Date:** 2026-10-15
- **Status:** Approved in conversation; implementation authorized
- **Scope:** `ui/` (server + React app), new `ui/db/` and `ui/mcp/` modules (plain ESM `.mjs`,
  no build step, sharing `ui/package.json`), agent definitions

## 1. Goals

1. **Agents build on prior work.** Before researching, an agent can look up what
   earlier runs already found (assets, findings, CVE notes, reports) and cite it.
2. **Track bug bounty programs** through a pipeline:
   discovered lead → tracked program → operator-confirmed scope snapshot.
   Manual entry ships first; the model leaves room for platform sync later.
3. **Persist everything the agents produce:** every run, its event stream,
   subagent reports, final results, and structured records each agent writes.

Non-goals (YAGNI): editing records in the UI, charts/dashboards, user
accounts, platform sync (designed for, not built), multi-machine deployment.

## 2. Decisions made

| Question | Decision |
|---|---|
| How programs enter the tracker | Manual first; platform sync later (model supports `source = 'sync'`) |
| Storage | SQLite (`node:sqlite`, Node ≥ 22.5; repo uses Node 26) |
| Agent access | MCP tools with **read + write**, each agent writing **only its own domain's tables** |
| Program discovery | Saudade and Dahlia may create **program leads** shown in the UI |
| Authorization basis | Only the **operator** can confirm a scope snapshot; agents can only propose |

## 3. Data model

Database file: `data/endless-illusion.db` (gitignored, mode `0600`), WAL mode,
`busy_timeout = 5000`. Schema lives in `ui/db/migrations/NNN-*.sql`, tracked with
`PRAGMA user_version`, applied idempotently at startup by any process that opens
the database.

### 3.1 Ownership

Every table is readable by every agent. Writes:

| Writer | Tables |
|---|---|
| Hub server | `runs`, `run_events`, `reports` |
| Operator (UI) | `programs`, `lead_decisions`, `proposal_decisions`, `scope_snapshots` |
| saudade-of-sunday | `assets`, `asset_observations`, `program_leads` (shared) |
| dahlia-of-wednesday | `cve_notes`, `program_leads` (shared) |
| diablo-of-monday | `web_findings` |
| metsa-of-tuesday | `api_endpoints`, `api_findings` |
| sin-of-friday | `exploit_analyses` |
| sen-of-saturday | `scope_proposals`, `submissions` |
| dann-of-thursday | `engagements`, `run_engagements` |

This map is defined once in code (`ui/db/ownership.mjs`) and drives the MCP tool
registry, the agent configs, and the tests.

### 3.2 Common columns on agent-written tables

`id INTEGER PRIMARY KEY`, `agent TEXT NOT NULL`, `run_id TEXT`,
`created_at TEXT NOT NULL` (ISO-8601 UTC), `supersedes INTEGER NULL`
(references a prior row in the same table). Agent writes are **append-only**:
no UPDATE or DELETE tools exist. A correction is a new row with `supersedes` set;
reads return the latest row in each supersede chain unless history is requested.

### 3.3 Tables

Hub:
- `runs(id TEXT PK, agent, task, scope, authorization, active_engaged INT,
  tools JSON, status TEXT CHECK IN ('running','done','error','stopped','interrupted'),
  program_id NULL, snapshot_id NULL, cost_usd REAL NULL, duration_ms INT NULL,
  started_at, ended_at NULL)`
- `run_events(run_id, seq INT, ts INT, event JSON, PRIMARY KEY(run_id, seq))`
- `reports(id, run_id, agent, kind CHECK IN ('subagent_report','final'), text,
  meta JSON, created_at)` + FTS5 index `reports_fts(text)`

Bounty pipeline:
- `program_leads(+common, name, platform NULL, url, normalized_url, found_via,
  scope_summary)` — one row per sighting; the UI groups by `normalized_url`
- `lead_decisions(normalized_url PK, decision CHECK IN ('tracked','dismissed'),
  program_id NULL, decided_at)`
- `programs(id, name, platform NULL, url, normalized_url UNIQUE, policy_text,
  source CHECK IN ('manual','lead','sync'), created_at)`
- `scope_proposals(+common, program_id, in_scope JSON, out_of_scope JSON,
  exclusions JSON, source_excerpt)` — scope items are `{asset, type, notes}`
- `proposal_decisions(proposal_id PK, decision CHECK IN ('confirmed','rejected'), decided_at)`
- `scope_snapshots(id, program_id, proposal_id, in_scope JSON, out_of_scope JSON,
  exclusions JSON, confirmed_at)`

Agent domains (all `+common`):
- `assets(host, kind CHECK IN ('domain','subdomain','ip','url','service'), details JSON, engagement_id NULL)`
- `asset_observations(asset_host, port NULL, service NULL, technology NULL, evidence)`
- `web_findings` / `api_findings(target, title, status CHECK IN ('confirmed','suspected','not_reproduced'),
  severity CHECK IN ('info','low','medium','high','critical'), description, reproduction,
  impact, remediation, evidence, program_id NULL, engagement_id NULL)`
- `api_endpoints(base_url, method, path, auth NULL, notes NULL)`
- `cve_notes(cve_id, product, affected_versions, fixed_version NULL, cvss NULL,
  kev INT, public_exploit INT, summary, sources JSON)`
- `exploit_analyses(cve_id NULL, title, mechanism, preconditions, detection, mitigation, sources JSON)`
- `submissions(program_id, title, severity, body_markdown, finding_refs JSON)`
- `engagements(name, program_id NULL)`, `run_engagements(run_id, engagement_id)`

FTS5 also indexes finding/note text so `search_reports` covers structured records.

## 4. MCP server (`ui/mcp/ei-memory.mjs`)

A Node stdio MCP server. Each run's MCP config starts **one instance per agent**:
`ei-<short>` (e.g. `ei-dahlia`) launched with `--agent <id>` and env `EI_RUN_ID`.

- **Read tools** (every instance): `find_prior_work(target)`,
  `search_reports(query, agent?, since?)`, `get_report(id)`, `get_cve_note(cve)`,
  `list_programs(stage?)`, `get_scope(program)` (latest *confirmed* snapshot only,
  with its date — never proposals).
- **Write tools** (only the instance's own agent): one tool per owned table,
  e.g. `save_cve_note`, `record_program_lead`, `propose_scope`. Each is a fixed,
  parameterized INSERT into exactly one table. **There is no raw-SQL tool.**
- Every write: validates input against a strict schema (enums, required fields,
  64 KB text cap), redacts secrets, stamps `agent` + `run_id`, re-checks
  `ownership[agent]` includes the table, then inserts.
- Read results are capped in size, carry `run_id` + date for citation, and are
  framed as **data, not instructions** (stored text often came from targets).

## 5. Enforcement of write domains

1. **By construction:** write tools are per-table and parameterized.
2. **Per-agent server instance:** an instance exposes only its agent's write
   tools and re-checks ownership on every write.
3. **Per-agent tool lists:** each `.claude/agents/<name>.md` `tools:` names only
   its own `mcp__ei-<short>__*` tools. Orchestrated runs launch with
   `--agent dann-of-thursday` (new definition) so Dann's main thread is limited
   to its own list; MCP servers come only from the generated `--mcp-config`
   (`--strict-mcp-config`).

**Verification gate — run 2026-10-15 on Claude Code 2.1.300:**
- (a) A subagent's `tools:` list **does** restrict MCP tools (forbidden tool: "No such tool available"). ✅
- (b) `--agent <name>` **does** restrict the main thread to that definition's `tools:`. ✅
- (c) `--allowedTools` **does not restrict** anything in `-p` mode — it only
  pre-approves. A run with `--allowedTools Read,Grep,Glob` executed `Bash`.
  `--tools <list>` **does** remove tools from the session. ❌ → fixed below.

Consequences:
- The hub restricts sessions with **`--tools`** (built-ins) and
  **`--strict-mcp-config`** (MCP), never `--allowedTools` alone. This also
  closes a pre-existing hole: "passive" runs could use `Bash` and the operator's
  global MCP servers (e.g. a browser).
- Orchestrated runs launch with `--agent dann-of-thursday`.

## 6. Hub server changes (`ui/server.mjs`)

- Opens the DB at startup; marks any `running` runs `interrupted`.
- `startRun`: inserts `runs`; writes a per-run MCP config file to
  `data/run-configs/<id>.json` and passes it with `--strict-mcp-config`;
  restricts built-ins with `--tools` (and pre-approves the same set plus the
  run's `mcp__ei-*` tools with `--allowedTools`); accepts optional `programId` (must have a confirmed snapshot;
  stores `program_id` + `snapshot_id`).
- On each stream event: append to `run_events`. On subagent `tool_result` for a
  delegation and on `result`: insert `reports` (hand-back wrapper stripped,
  shared `cleanReport` logic). On close: update status, cost, duration.
- Archive write failures are logged and pushed to the client as a `warn` event;
  they never stop a run.
- New endpoints:
  - `GET /api/runs?agent=&status=&program=&q=` — list; `GET /api/runs/:id/events`
    replays from DB when the run isn't live.
  - `GET /api/bounties` — `{ leads, tracked, confirmed }`
  - `POST /api/programs` (manual add), `POST /api/leads/track` and
    `POST /api/leads/dismiss` (body `{ normalizedUrl }`), `POST /api/proposals/:id/confirm`,
    `POST /api/proposals/:id/reject`
  - `GET /api/findings`, `GET /api/cve-notes`, `GET /api/submissions`,
    `GET /api/submissions/:id/export` (markdown via `templates/engagement-report.md`)
- Mutating endpoints require `Content-Type: application/json` and an `Origin`
  matching the UI's (CSRF guard for a localhost server).

## 7. UI

Tabs **Console · Bounties · Archive**, state in the URL hash, built from
`components/ui/` primitives, colored by the selected agent.

- **Console:** unchanged, plus a **Program** picker in Trigger listing only
  confirmed programs; choosing one fills Scope and Authorization from the
  snapshot and sends `programId`.
- **Bounties:** three columns. *Discovered* (lead cards: name, platform, finder
  in agent color, found via, unverified scope, sighting count, run link;
  Track / Dismiss). *Tracked* ("Ask Sen for scope" starts a passive Sen run;
  "Review proposal" shows proposal beside source → Confirm / Reject).
  *Scope confirmed* (snapshot date; "re-verify scope" flag after 30 days;
  "Use in Trigger"). "Add program" for manual entry. Polls every 5 s while a
  run is active and on window focus.
- **Archive:** Runs (filters + full-text search; opening replays read-only into
  Channel + Monitor), Findings (by severity), CVE notes, Submissions (+ export).

## 8. Agent behavior

Each dossier and subagent definition gains a **"Check prior work first"** step:
call `find_prior_work` / `search_reports` before external research, cite reused
records by `run_id` and date, and re-verify time-sensitive facts older than
7 days (e.g. KEV status, scope). Saudade and Dahlia record program leads they
encounter passively. Sen proposes scope; it never claims scope is confirmed.

## 9. Security

- Write domains enforced per §5; covered by tests.
- Secret redaction before every persist (bearer tokens, JWTs, AWS-style keys,
  `password=`/`token=`/`secret=` values) — hub and MCP writes alike.
- Scope snapshots are operator-only; agents cannot widen authorization.
- `data/` gitignored; DB created `0600`.
- Active-tool gate unchanged (authorization text + confirm); program link is
  optional but recorded when used.

## 10. Testing

Vitest in `ui/` (new).
- **Ownership matrix:** spawn each agent's MCP instance, list tools, assert the
  write set equals `ownership[agent]`; a cross-domain write is rejected.
- **Config:** every subagent's `tools:` ⊆ its own server's tools;
  Dann's tool list has no other agent's write tools.
- **Archive integration:** fake `claude` via `CLAUDE_BIN` replays a sanitized
  recorded run; assert `runs`, `run_events`, `reports` rows.
- **Unit:** migrations, redaction, supersede-chain reads, lead → tracked →
  snapshot flow, CSRF guard, replay of a stored run through `buildChat`.

## 11. Rollout order

1. Verification gate (§5) → 2. `db/` + migrations → 3. MCP server + ownership
tests → 4. hub archive + run history API → 5. bounty API → 6. UI tabs
(Archive, Bounties, Trigger picker) → 7. agent definitions + dossier updates.
