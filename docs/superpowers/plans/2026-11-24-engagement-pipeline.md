# Engagement Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a whole engagement as operator-started stages (Discovery → Planning → Web ∥ API → Analysis → Reporting, plus Research), where every target-touching action pauses on an approval card the hub enforces.

**Architecture:**
- **Stages:** each stage is an ordinary hub run (`hub/runner.py`, `claude -p` stream-json) tagged with an engagement and stage.
- **Gate:** a new stdio MCP server (`hub/gate.py`), wired in as the run's `--permission-prompt-tool`. It records gated actions in SQLite and blocks by polling the DB until the operator decides through the hub API.
- **State:** pipeline state lives in new operator-owned tables. Agents can only write a plan draft.

**Tech Stack:** Python 3.12 stdlib hub, SQLite (WAL), pytest; React + TypeScript + `pnd-lib-react`, vitest; Claude Code CLI 2.1.331.

**Spec:** `docs/superpowers/specs/2026-11-24-engagement-pipeline-design.md`

## Global Constraints

- **Enforcement is in the hub, never in a prompt.** Every allow/deny path for a gated tool goes through `hub/gate_service.py`, and the default is deny.
- **Ask, fork and explain runs** (Task 7) never get `Bash`, `Write` or `WebFetch`.
- **Stages never auto-start.** Only `POST /api/engagements/:id/stages/:stage/start` starts one.
- **Arming:**
  - Possible only for `web`, `api` and `discovery`.
  - Requires the engagement's `authorization` to be non-empty, and for `kind = 'bounty'` a confirmed `snapshot_id`.
  - Never possible for planning, analysis, reporting or research.
- **Gated:**
  - every `Bash` call except local-only commands (Task 3 rules);
  - `WebFetch` whose URL host is in the engagement scope;
  - `Write` / `Edit` outside `research/<engagement-slug>/`, which is always **auto-denied**.
- **Scope verdicts:**
  - `out`: cannot be approved; the API refuses with 409.
  - `unknown`: approvable only with `scopeAck: true`.
- **Declarations:** a gated action needs a prior `declare_action` from the same run with the exact same command or URL, plus non-empty `why`, `technique` and `risk`. Otherwise it is auto-denied with the message `call declare_action with why, technique and risk first`.
- **Engagement working folder:** `research/<slug>/`. The slug is `[a-z0-9-]+`, made from the name.
- **Juice Shop lab:** `127.0.0.1`, port `3000`. Scope host entry `localhost:3000`, plus `127.0.0.1:3000`.
- **Schema changes** go in new migration files only (`hub/migrations/004-*.sql`); existing migrations are never edited.

## Review Focus

1. **Hub restart while an action is pending.** On startup, every `pending` gate action whose run isn't live becomes `expired`, and the gate server returns deny for it. *(Task 4 test `test_expire_orphaned_pending`.)*
2. **Two stages pending at once.** Approving one never releases the other; decisions are keyed by action id, not by run or stage. *(Task 4 test `test_parallel_pending_are_independent`.)*
3. **Declared command differs from the executed one.** Any byte difference (extra space, changed flag) auto-denies. *(Task 4 test `test_declaration_must_match_exactly`.)*
4. **Stop a stage while its action is pending.** The action becomes `cancelled`, and the blocked gate call returns deny within one poll interval. *(Task 6 test `test_stop_cancels_pending_action`.)*
5. **Host hidden from parsing.** For example `H=localhost; curl "$H:3000"` or `curl $(cat host.txt)`: the command is gated with verdict `unknown`, never `in`. *(Task 3 test `test_indirect_hosts_are_unknown`.)*

---

## File map

| File | Responsibility |
|---|---|
| `hub/migrations/004-engagement-pipeline.sql` | operator tables + `plan_drafts` |
| `hub/db/pipeline.py` | engagement/stage/plan CRUD (operator writes) |
| `hub/gate_rules.py` | pure: host extraction, scope verdict, bash/write classification |
| `hub/gate_service.py` | declarations, permission decision, pending/decide/expire |
| `hub/mcp_stdio.py` | shared stdio JSON-RPC loop, extracted from `hub/memory.py` |
| `hub/gate.py` | gate MCP server: `declare_action`, `permission` |
| `hub/pipeline.py` | stage definitions, state machine, prompts, start/skip/plan/ask |
| `hub/session.py`, `hub/runner.py`, `hub/app.py` | wiring |
| `ui/src/engagement.ts` (+ `.test.ts`) | pure UI rules for stages and cards |
| `ui/src/components/engagement/*`, `ui/src/pages/EngagementsPage.tsx` | the Engagements tab |
| `okay_dann.py` | `okay-dann lab start\|stop\|status` |

---

### Task 1: Verify the CLI mechanisms (spike, no product code)

**Files:**
- Create: `scripts/spikes/gate_spike_server.py` (throwaway; deleted at the end of this task)
- Modify: `docs/superpowers/specs/2026-11-24-engagement-pipeline-design.md` (§4: record the results)

**Interfaces:**
- Produces: the exact JSON shapes that Tasks 4 and 5 code against:
  - the permission-tool request arguments (expected: `tool_name`, `input`, possibly `tool_use_id`);
  - the reply body (expected: a text content of `{"behavior":"allow","updatedInput":{…}}` or `{"behavior":"deny","message":"…"}`);
  - whether the fork answers while the original session is still running.

- [ ] **Step 1:** Write a 60-line stdio MCP server exposing one tool, `permission`. It appends its arguments to a log file, sleeps 20s, then returns allow.
- [ ] **Step 2:** Run a `claude -p` session against it:

  ```
  claude -p --output-format stream-json --verbose --tools Bash --allowedTools "" \
    --strict-mcp-config --mcp-config <cfg> --permission-prompt-tool mcp__spike__permission \
    --permission-prompts host
  ```

  Use the prompt `run: echo hi`. Expected:
  - the log shows one call with the Bash input;
  - the session pauses about 20s, then prints `hi`;
  - with a deny reply, the agent receives the deny message.
- [ ] **Step 3:** While Step 2's session is paused, run `claude -p --resume <session_id> --fork-session --tools Read "what were you about to run and why?"`. Expected: it answers with context and gets a new session id, and the original continues unaffected.
- [ ] **Step 4:** Record the results in spec §4.
  - If the permission tool doesn't work, switch Task 5 to a `PreToolUse` hook command, `python hub/gate.py --hook`, that applies the same `check_permission`.
  - If the fork fails while the session is running, restrict Ask to paused stages, as spec §4 allows.

  Delete the spike, then commit.

```bash
git add docs/superpowers/specs/2026-11-24-engagement-pipeline-design.md
git commit -m "docs(spec): record permission-prompt-tool and fork-session verification"
```

---

### Task 2: Schema and pipeline DB layer

**Files:**
- Create: `hub/migrations/004-engagement-pipeline.sql`, `hub/db/pipeline.py`, `tests/test_pipeline_db.py`
- Modify: `hub/db/tables.py` (`plan_drafts`), `hub/db/ownership.py` (Dann owns `plan_drafts`)

**Interfaces:**
- Produces, as tables:
  - `ops_engagements(id, slug UNIQUE, name, kind CHECK lab|bounty, scope_hosts JSON, scope_notes, authorization, program_id, snapshot_id, created_at)`
  - `ops_stages(id, engagement_id, stage CHECK discovery|planning|web|api|analysis|reporting|research, status CHECK ready|running|done|failed|stopped|skipped, run_id, armed INT, question TEXT, created_at, finished_at)`. Rows are created on start or skip. `locked` and `awaiting-approval` are derived, never stored.
  - `ops_plans(id, engagement_id, draft_id, plan JSON, approved_at)`
  - `gate_declarations(id, run_id, target, why, technique, risk, created_at)`
  - `gate_actions(id, run_id, engagement_id, stage, tool_name, input JSON, target, why, technique, risk, hosts JSON, verdict CHECK in|out|unknown|none, status CHECK pending|approved|denied|auto_allowed|auto_denied|expired|cancelled, message, scope_ack INT, created_at, decided_at)`
  - `gate_questions(id, engagement_id, stage, action_id, kind CHECK ask|explain, question, technique, fork_run_id, answer, created_at)`
- Produces the agent table `plan_drafts`. Tool `save_plan_draft`, columns:
  - `engagement_id` (int, required)
  - `summary` (text)
  - `plan` (json): `{"stages": {"web"|"api"|"analysis"|"reporting": {"include": bool, "targets": [str], "focus": str}}, "research": [str]}`
- Produces these functions in `hub/db/pipeline.py`:
  - `create_engagement(db, name, kind, scope_hosts: list[str], scope_notes, authorization, program_id=None, snapshot_id=None) -> dict`. Raises `ValueError` on: an empty name; a bounty without a confirmed snapshot (reuse `require_confirmed_snapshot` from `hub/db/scope.py`); a lab with no hosts.
  - `get_engagement(db, id) -> dict | None` and `list_engagements(db) -> list[dict]`
  - `add_stage(db, engagement_id, stage, run_id, armed, question=None) -> int`
  - `set_stage_status(db, stage_id, status) -> None`
  - `stage_rows(db, engagement_id) -> list[dict]`
  - `latest_plan_draft(db, engagement_id) -> dict | None`
  - `approve_plan(db, engagement_id) -> int`: copies the latest draft into `ops_plans`. Raises `ValueError` if there's no draft.
  - `approved_plan(db, engagement_id) -> dict | None`

- [ ] **Step 1: Write the failing tests** in `tests/test_pipeline_db.py`:
  - `test_create_lab_engagement_slugs_name`: `"Juice Shop Lab"` gives slug `juice-shop-lab`.
  - `test_bounty_requires_confirmed_snapshot`: raises `ValueError`.
  - `test_lab_requires_hosts`
  - `test_agent_cannot_write_operator_tables`: `assert_owns("dann-of-thursday", "ops_plans")` raises `OwnershipError`.
  - `test_dann_saves_plan_draft_and_operator_approves`: insert via `insert_agent_row(db, "dann-of-thursday", "plan_drafts", {...})`, then `approve_plan`, and `approved_plan(...)["plan"]` equals the draft's plan.
  - `test_approve_plan_without_draft_raises`
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_pipeline_db.py -q`. Expected: FAIL (no module `hub.db.pipeline`).
- [ ] **Step 3:** Write the migration and functions above. Register `plan_drafts` in `WRITE_TABLES` and in `OWNERSHIP["dann-of-thursday"]`. Then run `python -m hub.sync_agent_tools` so Dann's tool list includes `save_plan_draft`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q`. Expected: all pass, including the existing `test_agent_config.py` after the sync.
- [ ] **Step 5: Commit** with `feat(db): engagement pipeline tables and plan drafts`.

---

### Task 3: Gate rules (pure functions)

**Files:**
- Create: `hub/gate_rules.py`, `tests/test_gate_rules.py`

**Interfaces:**
- Produces:
  - `LOCAL_COMMANDS: frozenset[str]`: exactly `grep rg jq cat ls head tail wc sed awk sort uniq cut tr diff file echo pwd mkdir tee`
  - `extract_hosts(text: str) -> tuple[list[str], bool]`. Returns `(hosts, indirect)`.
    - Hosts are taken from URLs, `host:port` tokens, bare domains with a dot plus a known TLD or `localhost`, and IPv4.
    - Each is returned lowercased, as `host` or `host:port`.
    - `indirect` is True when the text has `$VAR`, `${…}`, `$(…)`, backticks or `eval`.
  - `scope_verdict(hosts: list[str], indirect: bool, scope_hosts: list[str]) -> str`:

    | Condition | Verdict |
    |---|---|
    | `indirect` | `"unknown"` |
    | no hosts | `"none"` |
    | any host outside scope | `"out"` |
    | otherwise | `"in"` |

    A scope entry `*.example.com` matches subdomains. An entry with a port matches only that port; one without matches any port.
  - `classify_bash(command: str, workdir: Path) -> str`:
    - returns `"local"` only when every segment split on `|`, `&&`, `||` and `;` starts with a `LOCAL_COMMANDS` name, there are no hosts, `indirect` is False, there is no `xargs` or `<(`, and every `>`, `>>`, `tee` or `sed -i` / `--in-place` target resolves inside `workdir`;
    - otherwise `"gated"`.
  - `classify_write(path: str, workdir: Path) -> str`: `"local"` when the resolved path is inside `workdir`, else `"denied"`.

- [ ] **Step 1: Write the failing tests:**
  - `test_extract_hosts_from_curl`: `curl -s http://localhost:3000/rest/products` gives `(["localhost:3000"], False)`.
  - `test_indirect_hosts_are_unknown`:
    - `H=localhost; curl "$H:3000"` gives verdict `unknown`;
    - `curl $(cat host.txt)` gives `unknown`;
    - both classify as `gated`.
  - `test_scope_wildcard_and_port`:
    - `api.example.com` is `in` for `["*.example.com"]`;
    - `localhost:8080` is `out` for `["localhost:3000"]`.
  - `test_out_if_any_host_out`: `curl a.example.com b.evil.com` gives `out`.
  - `test_local_pipeline_allowed`: `grep -i sql out.txt | sort | uniq` is `local`.
  - `test_local_with_redirect_outside_workdir_gated`: `cat x > /etc/hosts` and `sed -i s/a/b/ ~/.zshrc` are `gated`.
  - `test_unlisted_binary_gated`: `nmap -sV localhost` and `python3 -c 1` are `gated`.
  - `test_xargs_and_procsub_gated`
  - `test_write_inside_workdir_only`: `../../etc/x` is `denied`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_gate_rules.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement with `shlex` for tokenizing and `urllib.parse` for URLs. Unparseable input (a `shlex` ValueError) is `gated`, with verdict `unknown`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5: Commit** with `feat(gate): host extraction, scope verdicts, local-command rules`.

---

### Task 4: Gate service (decisions, pending, operator decide)

**Files:**
- Create: `hub/gate_service.py`, `tests/test_gate_service.py`

**Interfaces:**
- Consumes: Task 2 tables, Task 3 functions.
- Produces:
  - `RunContext` dataclass: `run_id, engagement_id, stage, slug, scope_hosts: list[str], workdir: Path`
  - `context_for_run(db, run_id) -> RunContext | None`
  - `record_declaration(db, run_id, target, why, technique, risk) -> int`. Raises `ValueError` on any empty field.
  - `check_permission(db, ctx, tool_name, tool_input: dict, wait: Callable[[int], dict]) -> dict`. Returns the reply shape recorded in Task 1. Rules:
    - Non-gated tools, and `Bash` classified `local`: `auto_allowed`, recorded with `input`.
    - `Write`/`Edit` outside the workdir: `auto_denied`.
    - `WebFetch` to a host not in scope: `auto_allowed`.
    - Gated with no exact declaration (Bash `command`, or the WebFetch `url`, equal to `target`), or with an empty field: `auto_denied` with the Global Constraints message.
    - Otherwise: insert `pending` with `verdict` and `hosts`, and return `wait(action_id)`.
  - `wait_for_decision(db, action_id, poll=0.5, timeout=None) -> dict`. Polls until the status isn't `pending`:
    - `approved`: allow, with the original input;
    - `denied`: deny, with `message` or "operator denied";
    - `expired` or `cancelled`: deny, with "action was cancelled".
  - `decide(db, action_id, approve: bool, message: str = "", scope_ack: bool = False) -> dict`:
    - raises `GateRefused` (409) when approving verdict `out`, or verdict `unknown` without `scope_ack`;
    - raises `ValueError` if the action isn't pending (so a double click is a no-op error, not a second decision);
    - stamps `decided_at`.
  - `pending_actions(db, engagement_id=None) -> list[dict]`
  - `cancel_for_run(db, run_id) -> int`
  - `expire_orphaned(db, live_run_ids: set[str]) -> int`

- [ ] **Step 1: Write the failing tests**, using `db` and an inline `ctx`, with `wait` driven by a thread that calls `decide`:
  - `test_local_bash_auto_allowed`
  - `test_gated_without_declaration_auto_denied`
  - `test_declaration_must_match_exactly`: declared `curl -s http://localhost:3000/a` and executed `curl -s  http://localhost:3000/a` gives `auto_denied`.
  - `test_missing_technique_auto_denied`
  - `test_approve_returns_allow_with_input`
  - `test_deny_message_reaches_agent`
  - `test_out_of_scope_cannot_be_approved`: `decide(approve=True)` raises `GateRefused`.
  - `test_unknown_needs_scope_ack`
  - `test_double_decide_rejected`
  - `test_parallel_pending_are_independent`: two runs; approving A leaves B `pending`.
  - `test_expire_orphaned_pending`: `expire_orphaned(db, set())` gives status `expired`, and the waiter gets deny.
  - `test_webfetch_offscope_host_auto_allowed`
  - `test_write_outside_workdir_auto_denied`
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_gate_service.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Every status change goes through `db.transaction()`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5: Commit** with `feat(gate): permission decisions with operator approval`.

---

### Task 5: Gate MCP server

**Files:**
- Create: `hub/mcp_stdio.py`, `hub/gate.py`, `tests/test_gate_mcp.py`
- Modify: `hub/memory.py` (use `hub/mcp_stdio.py`, with no behavior change)

**Interfaces:**
- Consumes: Task 4.
- Produces:
  - `hub/mcp_stdio.py`: `serve(tools: dict[str, dict], call: Callable[[str, dict], dict], name: str) -> None`. This is the `initialize`, `ping`, `tools/list` and `tools/call` loop moved out of `memory.py`.
  - `hub/gate.py`:
    - invoked as `python hub/gate.py --db <file>`, with env `EI_RUN_ID`, as server name `ei-gate`;
    - tool `declare_action{target, why, technique, risk}` replies `declared #<id>`;
    - tool `permission`, with the argument names from Task 1, replies with `check_permission(..., wait=wait_for_decision)` serialized as Task 1 found;
    - with no `RunContext` (not a stage run), `permission` denies everything gated.
  - Constants `GATE_SERVER = "ei-gate"` and `PERMISSION_TOOL = "mcp__ei-gate__permission"`, both in `hub/tool_names.py`.

- [ ] **Step 1: Write the failing tests**, spawning `hub/gate.py` over stdio with a temp DB:
  - `test_lists_two_tools`
  - `test_declare_then_permission_pending_then_approve`: a background thread calls `decide`, and the reply's `behavior` is `allow`.
  - `test_permission_without_context_denies`
  - `test_memory_server_unchanged`: the existing memory tests still pass.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_gate_mcp.py tests/test_mcp.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5: Commit** with `feat(gate): ei-gate MCP server`.

---

### Task 6: Runner wiring for stage runs

**Files:**
- Modify: `hub/session.py`, `hub/runner.py`, `hub/app.py` (startup expiry), `tests/test_api.py`
- Modify: `tests/fixtures/fake_claude.py`, adding `FAKE_HOLD_FILE`: wait while the file exists, so a run can be held "running".

**Interfaces:**
- Consumes: Tasks 2, 4 and 5.
- Produces:
  - `build_session_args(..., permission_tool: str | None = None, fork: bool = False)`. It adds `--permission-prompt-tool <tool>`, then `--permission-prompts host`, then `--fork-session` (with `resume`).
  - `write_mcp_config(..., gate=False, db_file=...)` adds the `ei-gate` server, with `EI_RUN_ID`.
  - `Runner.start(body, link=None, stage=None)`:
    - `stage` is `{"engagementId": int, "stage": str, "armed": bool, "tools": list[str] | None, "mcpAgents": list[str] | None}`;
    - with a stage, it adds the gate server, removes `Bash`, `WebFetch`, `Write` and `Edit` from `--allowedTools` (still in `--tools`), and passes `PERMISSION_TOOL`;
    - `tools`/`mcpAgents` override the policy toolset (Planning, Ask);
    - it records the run id on the `ops_stages` row.
  - `Runner.stop(run_id)` also calls `cancel_for_run`.
  - At startup, `Hub.__init__` calls `expire_orphaned(db, set())`.
  - On run finish, the stage status mirrors the run: `done`→`done`, `error`→`failed`, `stopped`→`stopped`.

- [ ] **Step 1: Write the failing tests:**
  - `test_stage_run_args_include_gate`: the argv recorded by `fake_claude` contains `--permission-prompt-tool mcp__ei-gate__permission`, `Bash` is absent from the `--allowedTools` value, and the MCP config has `ei-gate`.
  - `test_stop_cancels_pending_action`: hold the run, insert a pending action for its run id, stop it, and the action is `cancelled`.
  - `test_plain_console_run_unchanged`: no gate flags.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_api.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(runner): gated stage runs`.

---

### Task 7: Pipeline state machine, stage prompts, Ask/explain

**Files:**
- Create: `hub/pipeline.py`, `tests/test_pipeline.py`
- Modify: `hub/prompt.py` (stage prompt builder), `.claude/agents/{saudade,diablo,metsa,sin,sen,dann}-*.md` and `agents/*.md` (a short "Gated actions" section). Sen's policy file is **not** changed. The Reporting stage alone passes `tools = Sen's default_safe + ["Write"]`, so plain Console runs of Sen never gain unconfined Write.

**Interfaces:**
- Consumes: Tasks 2, 4 and 6.
- Produces:
  - `STAGES: dict[str, dict]`, each with `agent`, `prereq` and `can_arm`:

    | Stage | Agent | Prerequisite |
    |---|---|---|
    | `discovery` | saudade | none |
    | `planning` | dann | discovery `done` |
    | `web` | diablo | plan approved and `include` true |
    | `api` | metsa | plan approved and `include` true |
    | `analysis` | sin | web and api each `done` or skipped |
    | `reporting` | sen | analysis `done` or skipped |
    | `research` | dahlia | none (repeatable; requires `question`) |

    `can_arm` is true only for discovery, web and api. A stage absent from the approved plan counts as skipped.
  - `stage_view(db, engagement_id, live: Callable[[str], bool]) -> list[dict]`. Each item is `{stage, agent, status, runId, armed, canArm, pending: int, history: [run ids]}`, where `status` is one of `locked|ready|running|awaiting-approval|done|failed|stopped|skipped`, and `awaiting-approval` means running with at least one pending action.
  - `start_stage(hub, engagement_id, stage, armed=False, question=None) -> dict`. It raises `ValueError` when:
    - the stage is locked;
    - it's already running;
    - `armed` is requested where `can_arm` is false;
    - `armed` is requested without authorization (or, for bounties, without a snapshot);
    - it's research without a question.

    It builds the prompt from: the RoE, the engagement scope and authorization, the stage's plan slice, the earlier stages' final reports (from the `reports` table, `kind = 'final'`), the workdir, and the gated-action protocol text ("before any target-touching command, call `mcp__ei-gate__declare_action` with the exact command, why, technique (WSTG / OWASP API Top 10 ID where one applies), risk").

    Planning uses `tools=["Read","Grep","Glob"]` and `mcpAgents=["dann-of-thursday"]`, with no `Agent` tool.
  - `skip_stage(db, engagement_id, stage) -> None`
  - `revise_plan(hub, engagement_id, comment) -> dict`: continues the planning run with the comment.
  - `ask(hub, engagement_id, stage, question, action_id=None, kind="ask", technique=None) -> dict`. It forks the stage run's session with `tools=["Read","Grep","Glob"]` and no gate, then stores the result in `gate_questions` as `fork_run_id`. Its answer is that run's final report.

    `kind="explain"` uses the fixed question: "In 2-3 lines: what is <technique>, what does a positive result look like, what is risky about it? Check pnd-notes first." It is cached per `(engagement_id, technique)`.

- [ ] **Step 1: Write the failing tests:**
  - `test_fresh_engagement_only_discovery_and_research_ready`
  - `test_planning_unlocks_after_discovery_done`
  - `test_web_locked_until_plan_approved`
  - `test_plan_excluding_api_marks_it_skipped`
  - `test_cannot_arm_planning`
  - `test_arm_requires_authorization`
  - `test_research_requires_question`
  - `test_stage_never_starts_itself`: finishing discovery leaves planning `ready`, with no run.
  - `test_planning_has_no_agent_tool`: the recorded argv `--tools` lacks `Agent`.
  - `test_explain_cached_per_technique`
  - `test_ask_fork_has_no_gated_tools`
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_pipeline.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Add the agent-definition sections and the Sen policy change, then run `python -m hub.sync_agent_tools`.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(pipeline): stage state machine, prompts, ask and explain`.

---

### Task 8: HTTP API

**Files:**
- Modify: `hub/app.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: Tasks 2, 4 and 7.
- Produces these routes (JSON; POSTs keep the existing content-type and origin guard):

  | Method | Route | Body or notes |
  |---|---|---|
  | GET | `/api/engagements` | list |
  | POST | `/api/engagements` | `{name, kind, scopeHosts, scopeNotes, authorization, programId?}`; the snapshot comes from `require_confirmed_snapshot`, never from the body |
  | GET | `/api/engagements/:id` | `{engagement, stages: stage_view, plan: {draft, approved}, pending: [...], questions: [...]}` |
  | POST | `/api/engagements/:id/stages/:stage/start` | `{armed?, question?}` |
  | POST | `/api/engagements/:id/stages/:stage/skip` | |
  | POST | `/api/engagements/:id/stages/:stage/stop` | |
  | POST | `/api/engagements/:id/plan/approve` | |
  | POST | `/api/engagements/:id/plan/revise` | `{comment}` |
  | POST | `/api/gate/actions/:id/decide` | `{approve, message?, scopeAck?}`; `GateRefused` returns 409 |
  | POST | `/api/engagements/:id/ask` | `{stage, question, actionId?, kind?, technique?}` |
  | GET | `/api/gate/pending` | all engagements, for the tab badge |

- [ ] **Step 1: Write the failing tests:**
  - `test_create_engagement_and_view`
  - `test_start_locked_stage_400`
  - `test_decide_out_of_scope_409`
  - `test_decide_cross_origin_403`
  - `test_bounty_snapshot_not_taken_from_body`
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_api.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/python -m pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** with `feat(api): engagement pipeline and gate routes`.

---

### Task 9: Engagements tab (UI)

**Files:**
- Create:
  - `ui/src/engagement.ts`, `ui/src/engagement.test.ts`
  - `ui/src/hooks/useEngagement.ts`
  - `ui/src/pages/EngagementsPage.tsx`
  - `ui/src/components/engagement/{EngagementList,NewEngagementForm,StageCard,ApprovalCard,PlanReview,QuestionThread,StagePanel}.tsx`
- Modify: `ui/src/App.tsx` (an `engagements` route, first tab, label "Engagements", with a pending-count badge), `ui/src/api.ts`, `ui/src/types.ts`

**Interfaces:**
- Consumes: the Task 8 routes.
- Produces these pure helpers in `ui/src/engagement.ts`:
  - `stageButtons(s: StageView): ("start"|"arm"|"stop"|"skip"|"rerun"|"open")[]`
  - `cardButtons(a: GateAction): ("approve"|"deny"|"denyWithReason"|"ask")[]`. `approve` is never included when `verdict === "out"`.
  - `approveNeedsAck(a: GateAction): boolean`: true for `verdict === "unknown"`.
  - `verdictLabel(v): string`, giving `"✓ in scope" | "✗ out of scope" | "? can't tell" | "no target host"`.
- UI behavior:
  - `useEngagement(id)` polls `GET /api/engagements/:id` every 1000 ms while the tab is visible. The badge polls `/api/gate/pending` every 2000 ms.
  - `StagePanel` reuses `components/monitor/RunMonitor` for the live feed.
  - `ApprovalCard` shows command/URL, Why, Technique with [explain], Target (the verdict label plus hosts), and Risk.
    - Its buttons follow `cardButtons`.
    - "Deny + tell agent why" and "Ask a question" open an inline text field.
    - Approving an `unknown` action needs the "I've checked this host is in scope" checkbox ticked.
  - Pending cards from every stage stack at the top of the page, oldest first.

- [ ] **Step 1: Write the failing tests** in `ui/src/engagement.test.ts`:
  - `cardButtons({verdict:"out"})` excludes `approve` and includes `deny` and `denyWithReason`.
  - `approveNeedsAck({verdict:"unknown"})` is `true`.
  - `stageButtons({status:"locked"})` is `[]`.
  - `stageButtons({status:"ready", canArm:true})` includes `start` and `arm`.
  - `stageButtons({status:"ready", canArm:false})` excludes `arm`.
  - `stageButtons({status:"running"})` includes `stop`.
- [ ] **Step 2:** Run `cd ui && npx vitest run src/engagement.test.ts`. Expected: FAIL.
- [ ] **Step 3:** Implement the helpers, then the components with `pnd-lib-react` (`Button`, `Checkbox`, `TextField`, `EmptyState`, `Banner`).
- [ ] **Step 4:** Run `cd ui && npx vitest run && npx tsc --noEmit && npx vite build`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat(ui): engagements tab with stage cards and approval cards`.

---

### Task 10: Juice Shop lab helper

**Files:**
- Modify: `okay_dann.py`, `tests/test_okay_dann.py`, `.gitignore` (nothing needed if the install lives outside the repo)

**Interfaces:**
- Produces:
  - `okay-dann lab start` installs OWASP Juice Shop on first use, under `~/.local/share/endless-illusion/juice-shop`, from its official packaged release for the local Node major (`juice-shop-<ver>_node<major>_macos_<arch>.tgz`), with the SHA-256 checked if the release publishes it. It then starts it bound to `127.0.0.1:3000` (`NODE_ENV=` unset, `PORT=3000`).
  - `okay-dann lab stop` stops it; `okay-dann lab status` reports up/down and the URL.
  - `okay-dann status` and `stop` include the lab process.
  - `lab_release_asset(version: str, node_major: int, machine: str) -> str` (pure, tested).

- [ ] **Step 1: Write the failing tests:**
  - `test_lab_release_asset_name`: `("17.3.0", 22, "arm64")` gives `"juice-shop-17.3.0_node22_macos_arm64.tgz"`. Check the real naming against the latest release page before fixing this value.
  - `test_lab_process_classified_as_service`
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_okay_dann.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests, then `okay-dann lab start && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/`. Expected: `200`; then `okay-dann lab stop`.
- [ ] **Step 5: Commit** with `feat(okay-dann): Juice Shop lab helper`.

---

### Task 11: End-to-end rehearsal (acceptance)

**Files:**
- Create: `research/juice-shop-lab/` outputs (produced by the run), `docs/superpowers/plans/2026-11-24-engagement-pipeline-rehearsal.md` (checklist results)

- [ ] **Step 1:** Run `okay-dann lab start`, then `okay-dann web --open`.
- [ ] **Step 2:** Create the engagement: "Juice Shop Lab", lab, scope `localhost:3000`, `127.0.0.1:3000`, authorization "operator-owned local lab (OWASP Juice Shop)".
- [ ] **Step 3:** Walk the pipeline with the operator. Each line is a pass/fail item in the rehearsal doc:
  - Discovery unarmed.
  - Planning produces a draft. Revise once, then approve.
  - Web and API armed in parallel. Approve at least 3 actions, deny 1 with a reason, Ask on 1, [explain] on 1.
  - Confirm one out-of-scope action shows ✗ and can't be approved (e.g. ask Diablo to try `example.com`).
  - Analysis, then Reporting.
- [ ] **Step 4:** Verify `research/juice-shop-lab/engagement-report.md` exists and that a `reports` row exists. Then compare the findings with the Juice Shop scoreboard (`http://127.0.0.1:3000/#/score-board`) and record the matches.
- [ ] **Step 5: Commit** the rehearsal doc and report with `docs: Juice Shop pipeline rehearsal`.
