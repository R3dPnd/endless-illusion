# Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist runs, reports, and per-agent structured records in SQLite; give agents read/write MCP tools limited to their own domains; add a bounty-program pipeline and Archive/Bounties UI.

**Architecture:** A shared `ui/db/` module (node:sqlite) owns schema, ownership, redaction, and queries. The hub (`ui/server.mjs`) archives every run and serves new APIs. A stdio MCP server (`ui/mcp/ei-memory.mjs`) runs once per agent per session and exposes shared read tools plus only that agent's write tools. Sessions are restricted with `--tools`, `--strict-mcp-config`, and (orchestrated) `--agent dann-of-thursday`.

**Tech Stack:** Node 26 `node:sqlite` (FTS5, JSON1), Express 4, `@modelcontextprotocol/sdk` + `zod`, React 18 + Vite 5, Vitest 3.

**Spec:** `docs/superpowers/specs/2026-10-15-persistence-design.md`

## Global Constraints

- Node ≥ 22.5 (`node:sqlite`); repo runs Node 26.
- DB path `data/endless-illusion.db` at repo root; `data/` gitignored; file mode `0600`; WAL; `busy_timeout = 5000`.
- No raw-SQL tool anywhere. Agent tables are append-only; corrections use `supersedes`.
- Text fields capped at 64 KB (65536 chars) on write.
- Only the operator (UI) writes `programs`, `lead_decisions`, `proposal_decisions`, `scope_snapshots`.
- Session restriction uses `--tools` + `--strict-mcp-config`; `--allowedTools` only pre-approves.
- Mutating HTTP endpoints require `Content-Type: application/json` and an allowed `Origin`.
- Server-side code is plain ESM `.mjs` with no build step.

## Review Focus

1. **Scope widening by agent text** — an agent writing a lead or proposal whose text claims "in scope" must never create or alter a `scope_snapshot`; `get_scope` returns confirmed snapshots only. (Task 4, Task 6 tests)
2. **Cross-domain write via another server instance** — Dann's main thread or a subagent calling another agent's write tool must be unavailable (tool lists) and, if reached, rejected by ownership re-check. (Task 4, Task 7 tests)
3. **Secrets in stored text** — a report or finding containing `Authorization: Bearer …`, a JWT, or an AWS key is stored redacted. (Task 2 test)
4. **Server restart mid-run** — runs left `running` become `interrupted`, and their stored events still replay. (Task 5 test)
5. **Cross-site request to localhost** — a POST from another origin to `/api/proposals/:id/confirm` is refused. (Task 6 test)

## File Structure

```
ui/
  db/
    index.mjs          openDb(file) → DatabaseSync (pragmas + migrate)
    migrate.mjs        migrate(db) via PRAGMA user_version
    migrations/001-init.sql
    ownership.mjs      OWNERSHIP, AGENT_SHORT, serverName(), assertOwns()
    redact.mjs         redact(text), clip(text)
    tables.mjs         WRITE_TABLES: per-table columns + tool name
    write.mjs          insertAgentRow(db, {agent, runId, table, fields})
    read.mjs           findPriorWork, searchReports, getReport, getCveNote, listPrograms, getScope
    archive.mjs        createRun, appendEvent, addReport, finishRun, markInterrupted, listRuns, getRun, getRunEvents
    bounties.mjs       normalizeUrl, listBounties, addProgram, trackLead, dismissLead, confirmProposal, rejectProposal
  shared/report.mjs    cleanReport(raw) (+ report.d.mts for the TS client)
  mcp/ei-memory.mjs    stdio MCP server (--agent, --db)
  server/
    session.mjs        buildSessionArgs(...) → argv for claude; writeMcpConfig()
    csrf.mjs           requireJsonSameOrigin middleware
    routes-archive.mjs runs list/replay, findings, cve-notes, submissions(+export)
    routes-bounties.mjs bounty pipeline endpoints
  server.mjs           wires the above (existing entry)
  scripts/sync-agent-tools.mjs  rewrites .claude/agents/*.md `tools:` from policy + ownership
  test/*.test.mjs      Vitest
  src/...              UI (Tasks 8–9)
.claude/agents/dann-of-thursday.md (new)
```

---

### Task 1: Close the tool-gating hole (`--tools` + `--strict-mcp-config`)

**Files:**
- Create: `ui/server/session.mjs`, `ui/test/session.test.mjs`, `ui/vitest.config.mjs`
- Modify: `ui/server.mjs` (replace inline arg building), `ui/package.json` (vitest, `test` script)

**Interfaces:**
- Produces: `buildSessionArgs({ tools: string[], mcpConfigPath?: string, mcpTools?: string[], agentDef?: string, systemPrompt?: string }) → string[]`

- [ ] **Step 1: Install Vitest; add `"test": "vitest run"`.** `npm i -D vitest@3`
- [ ] **Step 2: Write failing test** `ui/test/session.test.mjs`:

```js
import { describe, it, expect } from "vitest";
import { buildSessionArgs } from "../server/session.mjs";

describe("buildSessionArgs", () => {
  it("restricts built-ins with --tools and isolates MCP", () => {
    const a = buildSessionArgs({ tools: ["Read", "Grep"] });
    expect(a).toContain("--tools");
    expect(a[a.indexOf("--tools") + 1]).toBe("Read,Grep");
    expect(a).toContain("--strict-mcp-config");
  });
  it("never offers Bash unless listed", () => {
    const a = buildSessionArgs({ tools: ["Read"] });
    expect(a.join(" ")).not.toMatch(/Bash/);
  });
  it("pre-approves MCP tools and passes the config + agent", () => {
    const a = buildSessionArgs({ tools: ["Task"], mcpConfigPath: "/x.json", mcpTools: ["mcp__ei-dann__list_programs"], agentDef: "dann-of-thursday" });
    expect(a[a.indexOf("--mcp-config") + 1]).toBe("/x.json");
    expect(a[a.indexOf("--allowedTools") + 1]).toBe("Task,mcp__ei-dann__list_programs");
    expect(a[a.indexOf("--agent") + 1]).toBe("dann-of-thursday");
  });
});
```

- [ ] **Step 3: Run** `npx vitest run test/session.test.mjs` → FAIL (module missing).
- [ ] **Step 4: Implement** `ui/server/session.mjs`:

```js
/** argv for `claude -p`. --tools withholds tools; --allowedTools only pre-approves. */
export function buildSessionArgs({ tools, mcpConfigPath, mcpTools = [], agentDef, systemPrompt }) {
  const args = ["-p", "--output-format", "stream-json", "--verbose", "--tools", tools.join(","), "--strict-mcp-config"];
  if (mcpConfigPath) args.push("--mcp-config", mcpConfigPath);
  args.push("--allowedTools", [...tools, ...mcpTools].join(","));
  if (agentDef) args.push("--agent", agentDef);
  if (systemPrompt) args.push("--append-system-prompt", systemPrompt);
  return args;
}
```

- [ ] **Step 5: Use it in `server.mjs`** in place of the inline `args` array (orchestrated: tools = passive union + `Task`; direct: policy toolset).
- [ ] **Step 6: Run tests** → PASS. **Manual check:** fake-free smoke with real CLI: start a passive Dahlia run asking it to `touch` a scratch file via Bash; confirm the file is NOT created.
- [ ] **Step 7: Commit** `fix(ui): restrict agent sessions with --tools and --strict-mcp-config`

### Task 2: Database core — open, migrate, ownership, redaction

**Files:**
- Create: `ui/db/index.mjs`, `ui/db/migrate.mjs`, `ui/db/migrations/001-init.sql`, `ui/db/ownership.mjs`, `ui/db/redact.mjs`, `ui/test/db-core.test.mjs`
- Modify: root `.gitignore` (add `data/`)

**Interfaces:**
- Produces: `openDb(file: string) → DatabaseSync`; `migrate(db) → number`; `OWNERSHIP: Record<agentId, string[]>`; `AGENT_SHORT: Record<agentId, string>`; `serverName(agentId) → "ei-<short>"`; `assertOwns(agentId, table)` throws `Error("agent X may not write table Y")`; `redact(text) → string`; `clip(text, max=65536) → string`; `nowIso() → string`.

- [ ] **Step 1: Failing tests** (`db-core.test.mjs`): migrate on `:memory:` sets `user_version` to 1 and is idempotent (second call returns 1, no throw); every table named in `OWNERSHIP` exists in `sqlite_master`; `assertOwns("dahlia-of-wednesday","web_findings")` throws, `("dahlia-of-wednesday","cve_notes")` doesn't; `assertOwns(x, "scope_snapshots")` throws for every agent; `redact("Authorization: Bearer abc.def.ghi")` → contains `[REDACTED]`, not `abc.def.ghi`; redacts `eyJ…` JWTs, `AKIA[0-9A-Z]{16}`, `password=hunter2`, `token=…`, `secret=…`; leaves `CVE-2026-1234` untouched; `clip("x".repeat(70000)).length === 65536`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `001-init.sql` creates every table in spec §3.3 with the common columns (`id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL, supersedes INTEGER`) on agent tables, `CHECK` constraints for enums, indexes on `run_id`, `cve_id`, `normalized_url`, `host`, `target`, and FTS5 `search_fts(kind, ref_id UNINDEXED, title, body)` populated by triggers on `reports`, `web_findings`, `api_findings`, `cve_notes`, `exploit_analyses`, `submissions`. `openDb` creates the parent dir, opens the file, `chmod 0600` (non-memory), sets `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, then `migrate`. `migrate` reads `migrations/*.sql` sorted, applies those with number > `user_version` inside a transaction, sets `user_version`.

```js
// ui/db/ownership.mjs
export const OWNERSHIP = {
  "saudade-of-sunday": ["assets", "asset_observations", "program_leads"],
  "diablo-of-monday": ["web_findings"],
  "metsa-of-tuesday": ["api_endpoints", "api_findings"],
  "dahlia-of-wednesday": ["cve_notes", "program_leads"],
  "dann-of-thursday": ["engagements", "run_engagements"],
  "sin-of-friday": ["exploit_analyses"],
  "sen-of-saturday": ["scope_proposals", "submissions"],
};
export const AGENT_SHORT = Object.fromEntries(Object.keys(OWNERSHIP).map((a) => [a, a.split("-")[0]]));
export const serverName = (agent) => `ei-${AGENT_SHORT[agent]}`;
export function assertOwns(agent, table) {
  if (!OWNERSHIP[agent]?.includes(table)) throw new Error(`agent ${agent} may not write table ${table}`);
}
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(db): sqlite core with migrations, ownership map, redaction`

### Task 3: Agent write + read layers

**Files:**
- Create: `ui/db/tables.mjs`, `ui/db/write.mjs`, `ui/db/read.mjs`, `ui/test/db-rw.test.mjs`

**Interfaces:**
- Consumes: Task 2.
- Produces: `WRITE_TABLES[table] = { tool: string, description: string, columns: Record<col, "text"|"int"|"json"|"enum:a|b">, required: string[] }`; `insertAgentRow(db, { agent, runId, table, fields }) → { id }` (ownership check, unknown-column rejection, enum validation, clip + redact on text/json, `normalized_url` derived for `program_leads`, `supersedes` must reference an existing row of the same table); readers: `findPriorWork(db, target, limit=20)`, `searchReports(db, { query, agent?, since?, limit=20 })`, `getReport(db, id)`, `getCveNote(db, cveId)` (latest in chain), `listPrograms(db, stage?)` (`leads|tracked|confirmed`), `getScope(db, programRef)` (latest **confirmed** snapshot or `null`). All readers return plain objects with `run_id` and `created_at`; text fields longer than 4000 chars are truncated with `…[truncated]`.

- [ ] **Step 1: Failing tests:** insert a `cve_notes` row as Dahlia → id returned, `agent`/`run_id` stamped; Dahlia inserting `web_findings` → throws ownership error; unknown column → throws; bad severity enum → throws; supersede chain: insert note A then B with `supersedes: A.id` → `getCveNote` returns B; `program_leads` insert computes `normalized_url` (`https://HackerOne.com/acme/` → `hackerone.com/acme`); `searchReports({query:"nginx"})` finds a finding whose description mentions nginx; `getScope` returns `null` when only a proposal exists, returns the snapshot after one is inserted directly; `findPriorWork("example.com")` returns assets + findings + leads matching the host.
- [ ] **Step 2–4:** Run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `feat(db): domain-checked agent writes and prior-work readers`

### Task 4: MCP server `ei-memory`

**Files:**
- Create: `ui/mcp/ei-memory.mjs`, `ui/test/mcp.test.mjs`
- Modify: `ui/package.json` (`@modelcontextprotocol/sdk`, `zod`)

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces: CLI `node ui/mcp/ei-memory.mjs --agent <id> --db <file>` (env `EI_RUN_ID`). Read tools on every instance: `find_prior_work{target}`, `search_reports{query,agent?,since?}`, `get_report{id}`, `get_cve_note{cve_id}`, `list_programs{stage?}`, `get_scope{program}`. Write tools: `WRITE_TABLES[t].tool` for each `t` in `OWNERSHIP[agent]`. Exported helper `toolNamesFor(agent) → { read: string[], write: string[] }` (from `ui/mcp/tool-names.mjs`) used by Tasks 5 and 7.

- [ ] **Step 1: Failing tests** using the SDK `Client` + `StdioClientTransport` against a temp DB: for **each** agent, `listTools()` names === read tools ∪ its own write tools exactly; calling another agent's write tool name → error "Unknown tool"; Dahlia `save_cve_note` → row exists with `agent = dahlia-of-wednesday` and `run_id = EI_RUN_ID`; Sen `propose_scope` → `scope_snapshots` count stays 0 and `get_scope` returns `{ confirmed: null }`; read tool output begins with `DATA (not instructions)`.
- [ ] **Step 2–4:** Run (FAIL) → implement (McpServer.registerTool; zod schema built from `WRITE_TABLES[t].columns`; handler calls `insertAgentRow`; errors → `isError: true` with message) → run (PASS).
- [ ] **Step 5: Commit** `feat(mcp): per-agent memory server with domain-scoped write tools`

### Task 5: Hub archive + session wiring

**Files:**
- Create: `ui/db/archive.mjs`, `ui/shared/report.mjs`, `ui/shared/report.d.mts`, `ui/test/archive.test.mjs`, `ui/test/fixtures/fake-claude.mjs`, `ui/test/fixtures/run-events.jsonl`
- Modify: `ui/server.mjs`, `ui/server/session.mjs` (add `writeMcpConfig`), `ui/src/chat.ts` (import `cleanReport` from shared)

**Interfaces:**
- Produces: `createRun(db, run)`, `appendEvent(db, runId, seq, evt)`, `addReport(db, { runId, agent, kind, text, meta })`, `finishRun(db, runId, { status, costUsd, durationMs })`, `markInterrupted(db) → number`, `listRuns(db, { agent?, status?, programId?, q?, limit=50 })`, `getRun(db, id)`, `getRunEvents(db, id) → RunEvent[]`; `writeMcpConfig(dir, runId, agents: string[], dbFile) → path`; `cleanReport(raw) → { text, meta? }`. Server exports `createApp({ dbFile, claudeBin }) → { app, db }` for tests (listen only when run as main).

- [ ] **Step 1: Failing tests:** with `CLAUDE_BIN=fake-claude.mjs` (replays the fixture lines to stdout, records its argv to a file): POST `/api/runs` (Dann) → argv contains `--agent dann-of-thursday`, `--strict-mcp-config`, `--tools`; after close, `runs.status = done`, `run_events` count = fixture lines + meta + closed, `reports` has 1 `subagent_report` (wrapper stripped) + 1 `final`; `markInterrupted` flips a `running` row and `getRunEvents` still returns its events; MCP config lists one `ei-<short>` server per participating agent with `EI_RUN_ID`.
- [ ] **Step 2–4:** Run (FAIL) → implement → run (PASS). Archive write errors are caught, logged, and pushed as `{ kind: "warn", text }` events.
- [ ] **Step 5: Commit** `feat(hub): archive runs, events, and reports; per-run MCP config`

### Task 6: Run-history, records, and bounty APIs (+ CSRF)

**Files:**
- Create: `ui/db/bounties.mjs`, `ui/server/csrf.mjs`, `ui/server/routes-archive.mjs`, `ui/server/routes-bounties.mjs`, `ui/test/api.test.mjs`
- Modify: `ui/server.mjs`

**Interfaces:**
- Produces (HTTP): `GET /api/runs`, `GET /api/runs/:id`, `GET /api/runs/:id/events` (DB replay when not live), `GET /api/findings`, `GET /api/cve-notes`, `GET /api/submissions`, `GET /api/submissions/:id/export` (text/markdown), `GET /api/bounties` → `{ leads: Lead[], tracked: Program[], confirmed: ConfirmedProgram[] }`, `POST /api/programs {name, url, platform?, policyText}`, `POST /api/leads/track {normalizedUrl}`, `POST /api/leads/dismiss {normalizedUrl}`, `POST /api/proposals/:id/confirm`, `POST /api/proposals/:id/reject`; `POST /api/runs` accepts optional `programId` (400 unless it has a confirmed snapshot).
- Lead = `{ normalizedUrl, name, platform, url, sightings, agents: string[], foundVia, scopeSummary, firstSeen, lastSeen, runIds }`; Program adds `proposals: Proposal[]`; ConfirmedProgram adds `snapshot: { id, inScope, outOfScope, exclusions, confirmedAt, stale: boolean }` (stale after 30 days).

- [ ] **Step 1: Failing tests (supertest-free: `fetch` against `app.listen(0)`):** POST without JSON content type → 415; POST with `Origin: https://evil.example` → 403; lead → track → appears in `tracked`, gone from `leads`; dismissed lead hidden; confirm proposal → snapshot created with proposal's scope, `confirmed` lists program; reject → no snapshot; second confirm of same proposal → 409; `POST /api/runs` with unconfirmed `programId` → 400; export returns markdown containing the submission title.
- [ ] **Step 2–4:** Run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `feat(hub): run history, records, and bounty pipeline APIs with CSRF guard`

### Task 7: Agent definitions and dossiers

**Files:**
- Create: `.claude/agents/dann-of-thursday.md`, `ui/scripts/sync-agent-tools.mjs`, `ui/test/agent-config.test.mjs`
- Modify: `.claude/agents/*.md` (tools lines + "prior work" step), `agents/*.md` (operating procedure step), `RULES-OF-ENGAGEMENT.md` (§4: stored data, leads ≠ authorization), `CLAUDE.md` (memory + Bounties note)

**Interfaces:**
- Consumes: `toolNamesFor(agent)` (Task 4), policy `default_safe`.
- Produces: each subagent `tools:` = `default_safe` + `mcp__ei-<short>__<read+own write>`; Dann `tools:` = `Task, Read, Grep, Glob` + its own MCP tools.

- [ ] **Step 1: Failing test:** for every `.claude/agents/*.md`, parsed `tools:` ⊆ (`default_safe` ∪ `Task` for Dann ∪ `mcp__ei-<own>__*`), contains all own write tools, and contains no `mcp__ei-<other>__` tool.
- [ ] **Step 2–4:** Run (FAIL) → write script, run it, add Dann definition and prose → run (PASS).
- [ ] **Step 5: Commit** `feat(agents): memory tools per agent, Dann agent definition, prior-work procedure`

### Task 8: UI — tabs, routing, Archive page

**Files:**
- Create: `ui/src/hooks/useHashRoute.ts`, `ui/src/components/ui/Tabs.tsx`, `ui/src/pages/ConsolePage.tsx`, `ui/src/pages/ArchivePage.tsx`, `ui/src/components/archive/{RunList,RunReplay,FindingsTable,CveNotesTable,SubmissionsList}.tsx`
- Modify: `ui/src/App.tsx`, `ui/src/api.ts`, `ui/src/types.ts`, `ui/src/styles.css`, `ui/src/components/ui/index.ts`

**Interfaces:**
- Produces: `useHashRoute() → [route: "console"|"bounties"|"archive", setRoute]`; `Tabs({ tabs: {id,label}[], active, onChange })`; API client fns `listRuns`, `getRunEvents`, `listFindings`, `listCveNotes`, `listSubmissions`, `exportSubmissionUrl(id)`.
- RunReplay reuses `buildChat` + `ChatRoom` + `RunMonitor` read-only (no Stop).

- [ ] **Step 1:** Implement; `npx tsc --noEmit` clean; `vite build` clean.
- [ ] **Step 2: Verify** in headless Chromium against the real server with a seeded DB: tabs switch and survive reload via hash; a stored run replays with bubbles; findings sorted by severity; no console errors; no horizontal scroll at 390px.
- [ ] **Step 3: Commit** `feat(ui): tabbed navigation and Archive page`

### Task 9: UI — Bounties page + Program picker

**Files:**
- Create: `ui/src/pages/BountiesPage.tsx`, `ui/src/components/bounties/{BountyColumn,LeadCard,ProgramCard,ProposalReview,AddProgramForm}.tsx`, `ui/src/components/run/ProgramPicker.tsx`, `ui/src/hooks/useBounties.ts`
- Modify: `ui/src/components/run/RunForm.tsx`, `ui/src/hooks/useRun.ts` (`programId`), `ui/src/api.ts`, `ui/src/types.ts`, `ui/src/styles.css`

**Interfaces:**
- Produces: `useBounties(pollWhile: boolean) → { data, refresh, track, dismiss, confirm, reject, addProgram }` (polls every 5 s while `pollWhile`, and on window focus); `ProgramPicker({ programs: ConfirmedProgram[], value, onChange })`; "Ask Sen for scope" calls `run.start("sen-of-saturday", { task, scope: program.url, authorization: "", enableActive: false })`.

- [ ] **Step 1:** Implement; tsc + build clean.
- [ ] **Step 2: Verify** headless against seeded DB: lead card shows finder color + sightings; Track moves it; Review → Confirm creates snapshot card with date; picker lists only confirmed programs and fills Scope/Authorization; stale flag after 30 days (seed an old snapshot).
- [ ] **Step 3: Commit** `feat(ui): Bounties pipeline page and program picker`

### Task 10: End-to-end check

- [ ] Run `npm test` (all green), `npx tsc --noEmit`, `vite build`.
- [ ] Real smoke run (cheap, passive): Dahlia direct run "Save a CVE note for CVE-2021-44228 from public sources" → `cve_notes` row with `agent = dahlia-of-wednesday`; ask it to also call a Diablo write tool → unavailable.
- [ ] Commit any fixes; update `ui/README.md` (DB location, tabs, memory tools, gating note).
