# Engagement pipeline: button-driven stages with per-action approval

- **Date:** 2026-11-24
- **Status:** Draft for operator review
- **Scope:** `hub/` (Python control plane), `ui/` (React client), `agents/*.policy.json`,
  `.claude/agents/*.md`, a new local lab target (OWASP Juice Shop)

## 1. Intent

The operator wants to **run a whole pen test through Endless Illusion with buttons rather than
prompts, and to understand every move the agents make while it happens.** Today the hub runs one
agent at a time from a free-text form. Taking an engagement from recon to report means routing it
by hand. The DigitalOcean pass on 2026-11-23 needed the orchestrator to sequence three agents and
copy their output into files.

The engagement becomes the main object. It moves through stages, one per agent, and nothing acts
without the operator's explicit go-ahead. The approval moment is also the teaching moment: each
risky action arrives with the agent's reason, the technique it uses, a scope check and a risk
note, so the operator learns the operation by approving it.

The first live run is against **OWASP Juice Shop on the operator's own machine**. It rehearses the
pipeline and the gate with no authorization risk. **DigitalOcean is the second engagement**,
once its authorization pieces exist (an `@intigriti.me` account, a re-fetched policy and a
confirmed scope snapshot).

## 2. Goals, non-goals, anti-goals

**Goals**
1. An engagement runs through these stages:
   - Discovery (Saudade, Sunday)
   - Planning (Dann, Thursday)
   - Web (Diablo, Monday) and API (Metsä, Tuesday), in parallel
   - Analysis (Sin, Friday)
   - Reporting (Sen, Saturday)

   Research (Dahlia, Wednesday) can be started at any time alongside them.
2. **No stage starts until the operator clicks Start.** Finishing a stage never starts the next one.
3. **Within a running stage, any action that sends traffic to the target pauses** until the
   operator approves or denies it, using the approval card (§5.3).
4. **Every stage can be monitored live**, including parallel ones, and stopped on its own.
5. Common actions are buttons: start or stop a stage, approve the plan, approve or deny an
   action, ask the agent a question, open a stage's output.
6. A Juice Shop engagement can be run end to end and produces a report.

**Non-goals**
- Automating DigitalOcean testing in this project. That is a later engagement on the same machinery.
- Approval of passive actions (option C, rejected). Reading, web searches and CVE lookups run
  freely inside an approved stage.
- Multi-user use, remote approval (phone or Slack) and scheduling.
- Replacing the Console's free-form single runs, which stay for ad-hoc work.

**Anti-goals** (failure even if everything technically works)
- **Permission enforced only by the AI.** If any path lets an agent send target traffic, or start
  a stage, because a prompt told it to wait and it didn't, the design has failed. Enforcement is
  in the hub.
- **Unexplained actions.** A gated action with no stated reason is never shown for approval. It
  is denied back to the agent with a request to explain.
- **Approval fatigue.** If the operator is clicking through routine non-traffic actions, the
  gate is too broad.
- **Silent scope drift.** An action against a host outside the engagement's scope must never look
  the same as an in-scope one.

## 3. Constraints

- **Rules of Engagement** (`RULES-OF-ENGAGEMENT.md`) still hold in full. Active tooling only
  arms with documented authorization. For Juice Shop, the operator owns the target, and the
  engagement records that as its authorization basis.
- **The existing run engine stays.** `hub/runner.py` spawns `claude -p --output-format stream-json`
  per run, with `--tools` to withhold tools and a per-run MCP config (`hub/session.py`). Stages
  are runs on this engine; it is not rewritten.
- **The existing persistence model stays.** SQLite in `data/endless-illusion.db`, with migrations
  in `hub/migrations/NNN-*.sql`. Agent-written tables are append-only with `supersedes`, and each
  agent writes only its own domain's tables. Pipeline state is **operator-owned**, so it goes in
  new tables that agents cannot write.
- **Scope authority.** For a bounty engagement, scope comes from the operator-confirmed snapshot
  (`scope_snapshots`), never from the request. For a lab engagement, the operator enters scope
  hosts when creating it.
- **Litestream** replicates the DB to R2. Nothing here needs special handling for it.
- **Platform:** macOS. Docker is not installed and Node is, so Juice Shop runs from npm or its
  release package.

## 4. Approaches considered

| # | Approach | Trade-off | Verdict |
|---|---|---|---|
| 1 | **The hub runs the pipeline.** Each stage is its own run on today's engine, started by the operator. Actions are gated by `claude -p --permission-prompt-tool` pointing at a hub MCP tool that blocks until the operator decides. | Most new code: engagement state, stage handoff, gate service. Permission is enforced by the hub; each stage is watchable and stoppable on its own. | **Chosen** |
| 2 | Dann runs the pipeline in one session, delegating to subagents; a hook calls the hub for approvals. | Less code, but parallel stages interleave in one stream, a single stage can't be stopped, and stage permission depends on Dann choosing to ask. That breaks the first anti-goal. | Rejected |
| 3 | Like 1, but with the runner rewritten on the Claude Agent SDK (`can_use_tool` callback). | Approvals in process, but rewrites a working engine and adds a dependency for no change in behavior. | Rejected |

**Risk carried by approach 1:** it hasn't yet been verified that `--permission-prompt-tool`
behaves as needed with the installed Claude Code version: it must be called for un-allowed
tools in `-p` mode, receive the tool input, and block while the operator decides. **Verifying
this is the first task of the plan.** The fallback is a `PreToolUse` hook command that
long-polls the hub for a decision. The rest of the design is unchanged by that switch.

The same first task also verifies `claude -p --resume <session> --fork-session` against a
session that is still running (§5.5). The fallback is to allow "Ask" only while a stage is
idle or paused at a gate, answering from a fork taken at the pause.

**Verification results (Task 1)** — Claude Code 2.1.331, real `claude -p --model haiku` runs
against a stdio MCP spike server exposing one tool, `permission`:

- **Mechanism: `--permission-prompt-tool mcp__<server>__<tool>` works; no hook fallback needed.**
  `--permission-prompts host` is the default and is not required (the flag can be omitted; with
  `host` but no tool, un-allowed tools are just refused and the agent is told to ask the user).
- **Which calls reach the tool:** only calls that would otherwise prompt. Read-only Bash such as
  `echo hi` is auto-allowed by Claude Code and never reaches the tool; `echo hi > hi.txt` does.
  Tasks 4/5 test with a write-style command.
- **Request** (`tools/call` params; `arguments` is exactly this, `_meta` is extra):
  ```json
  {"name":"permission","arguments":{"tool_name":"Bash",
    "input":{"command":"echo hi > hi.txt","description":"Run echo hi redirected to hi.txt"},
    "tool_use_id":"toolu_013xiA1ANVx14Fi7pRSySaVg"},
   "_meta":{"claudecode/toolUseId":"toolu_013xiA1ANVx14Fi7pRSySaVg","progressToken":2}}
  ```
  `tool_name` string, `input` object (the tool's own input), `tool_use_id` string.
- **Reply** is one MCP text content whose text is a JSON string:
  - allow: `{"behavior":"allow","updatedInput":{…}}` runs the (possibly edited) input.
    `{"behavior":"allow"}` alone also works and runs the original input, so `updatedInput`
    is optional (echo `input` back anyway to be safe).
  - deny: `{"behavior":"deny","message":"Operator denied: …"}`. The command does not run, and the
    message reaches the agent verbatim as the tool_result (`is_error:true`); the agent
    stops and reports it. The stream's final `result` event also lists it under `permission_denials`.
- **Blocking:** the session waits for the tool's reply for as long as it takes (tested 25s) and
  then continues normally with the same session id; nothing times out at that length.
- **Fork while running: works.** While the original was blocked in the permission tool,
  `claude -p --model haiku --tools Read --resume <id> --fork-session -- "what were you about to run and why?"`
  answered correctly ("`echo hi > hi.txt` because you asked me to…, the call was interrupted"),
  under a new session id, and the original then continued and completed unaffected. Gotchas:
  `--tools` is variadic, so put the prompt after `--` (or before the flag); and the fork sees the
  pending tool call as interrupted. No need to restrict Ask to paused stages.

**Follow-up: guaranteeing every gated call reaches the hub (verified)**

- **The permission tool alone is NOT enough.** Claude Code's config auto-allow (read-only
  Bash such as `echo hi`; decision `source:"config", reason_type:"subcommandResults"`) is
  decided before the permission tool is consulted. `--permission-mode manual` and `default`
  do not change this: `echo hi` still bypassed the tool in both.
- **A `PreToolUse` hook fires for auto-allowed calls** (via `--settings <json>`, matcher
  `"Bash|WebFetch|Write|Edit"`, `"timeout": 3600`). Hook stdin JSON:
  ```json
  {"session_id":"…","transcript_path":"…","cwd":"…","prompt_id":"…","permission_mode":"default",
   "effort":{"level":"medium"},"hook_event_name":"PreToolUse","tool_name":"Bash",
   "tool_input":{"command":"echo hi","description":"Run echo hi"},"tool_use_id":"toolu_…"}
  ```
- **Hook reply `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask"}}`
  overrides the auto-allow:** `echo hi` then reached `--permission-prompt-tool` with the normal
  request (`tool_name`, `input`, `tool_use_id`), and the tool's deny message reached the agent.
- **The hook can block as long as needed:** with `"timeout": 3600`, a hook that slept 25s then
  returned `permissionDecision:"allow"` held the run for ~27s, then `echo hi` ran
  (`permission_decision` `{"decision":"accept","source":"hook"}`).
- **Hook deny:** `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
  "permissionDecisionReason":"…"}}` blocks the call; the agent receives
  `PreToolUse:Bash hook error: <reason>` (`is_error:true`) and stops.
- **Env:** the hook process inherits the claude process's environment (`EI_RUN_ID=test` set on
  spawn was visible to the hook).
- **Recommendation:** use the hook as the single gate. It sees every Bash/WebFetch/Write/Edit
  call (including auto-allowed ones) with the full input and run env, can block while the
  operator decides, and returns allow/deny with a reason that reaches the agent. Having the hook
  return `"ask"` and keep `--permission-prompt-tool` too is workable but redundant; if both are
  used, the hook must return `ask` for every call, otherwise auto-allowed ones skip the tool.
  Do not rely on `--permission-prompt-tool` alone.
- Test caveat: `--mcp-config` pointing at a missing server script makes the permission tool
  error with "not found. Available MCP tools: none"; check `mcp_servers[].status` in the init event.

## 5. Design (decided with the operator)

### 5.1 Engagement and stages

- **Engagement.** It has a name, a kind (`lab` or `bounty`), a scope (hosts plus a notes text),
  an authorization basis, and a link to a program and snapshot for bounties. Created from the
  UI with a "New engagement" button. Bounty engagements require a confirmed snapshot. Lab
  engagements take operator-entered hosts, and the authorization line says the operator owns
  the target.
- **Stages** are fixed, in this order: Discovery, Planning, Web, API, Analysis, Reporting, plus a
  Research lane. Each stage has a status: `locked` (prerequisites not met), `ready` (waiting for
  the operator), `running`, `awaiting-approval` (a gated action is pending), `done`, `failed`,
  `stopped` or `skipped`.
- **Prerequisites:**
  - Discovery: none.
  - Planning: Discovery done.
  - Web and API: the plan approved, and the stage included in the plan.
  - Analysis: Web or API done, or both skipped.
  - Reporting: Analysis done or skipped.
  - Research: always available. It can be started any number of times, each with its own question.
- **A stage starts only when the operator clicks Start on it.** A stage may be re-run, which
  creates a new run while keeping the old one, or skipped.
- **Each stage is one hub run**, linked to the engagement and stage. Follow-ups use the existing
  "continue run" mechanism, so the operator can reply to a stage's agent.
- **Arming is separate from starting** (operator decision). Arming turns on the agent's
  `authorized_active` toolset, which is what gives it Bash.
  - **Web and API:** each stage's Start control carries an **Arm** checkbox. It can only be
    ticked when the engagement has an authorization basis, plus a confirmed scope snapshot for
    a bounty engagement.
  - **Discovery:** starts passive. It can be armed separately, which is active scanning, under
    the same conditions.
  - **Planning, Analysis and Reporting:** never arm.
  - **Research:** passive only.
  - An unarmed stage has passive tools only, and the gate still covers its WebFetch calls to
    scope hosts.
  - Arming is recorded on the stage's run, as `activeEngaged` already is today.

### 5.2 Planning and the plan

- **Planning is a plain run of Dann** *(builder-check call)*: Read, Grep and Glob, the
  read-only memory tools, and the new plan tool. There is **no Agent tool**, so Planning cannot
  spawn subagents. That keeps every stage separately visible and gated, and the gate never has
  to reach inside subagents.
- The Planning stage runs Dann with the Discovery output. Dann's job is to produce a **structured
  plan**:
  - which of Web, API, Analysis and Reporting to run;
  - for each, the in-scope targets and the focus (e.g. "search and login endpoints, SQLi and auth
    bypass");
  - what Research questions are worth asking.
- **The plan is recorded through a new tool on Dann's memory server, as a draft.** Each call
  stores a new draft; the latest draft is the one shown. **Only the operator's Approve copies a
  draft into the operator-owned approved plan.** Agents can never write the approved plan.
- The operator sees the draft rendered and can **Approve** it, or **Revise** it with a comment,
  which continues the Planning run with that comment.
- **Approving the plan is what unlocks the testing stages.** Each testing stage's prompt is built
  from its slice of the approved plan, plus the engagement scope and the RoE.

### 5.3 The action gate (option B)

**What is gated** — any action that sends traffic to the target:
- every `Bash` call, **except local-only commands** (operator decision). A command is
  auto-allowed only when **all** of these hold:
  - every command in it, including each segment of a pipe or `&&`/`;` chain, is on a short
    allowlist of local tools: `grep`, `rg`, `jq`, `cat`, `ls`, `head`, `tail`, `wc`, `sed`,
    `awk`, `sort`, `uniq`, `cut`, `tr`, `diff`, `file`, `echo`, `pwd`, `mkdir`, `tee`;
  - it contains no URL, hostname or IP;
  - it uses no command substitution (`$(…)`, backticks), no `eval`, no `xargs` and no process
    substitution;
  - every path it writes to is inside the engagement's working folder.

  Anything the classifier doesn't recognize **is gated**. Auto-allowed commands are still
  logged in the stage history. The classifier needs thorough tests, since a mistake here lets
  traffic through.
- `WebFetch` when the URL's host matches a host in the engagement scope, including subdomains of
  wildcard entries;
- any future target-touching tool listed in a policy as gated.

Everything else in the stage's toolset runs without asking: Read, Grep, WebSearch, WebFetch to
other hosts, and the memory and notes tools.

**Mechanism:**
- Gated tools are left out of `--allowedTools`, so Claude Code consults the permission prompt
  tool for them.
- A new **gate MCP server** is added to each stage run's config. When called, it records a
  pending action and blocks until the hub records a decision, then returns allow or deny.
- A deny carries the operator's optional message back to the agent.
- Non-gated, un-allowed tools are auto-allowed by the gate without asking the operator. That
  covers WebFetch to non-scope hosts.

**Why, Technique and Risk are declared explicitly** *(builder-check call)*:
- The gate server also exposes a `declare_action` tool. Before a gated action, the agent calls
  it with the exact command or URL plus **why**, **technique** (with a WSTG or OWASP API Top 10
  ID where one applies) and **risk**.
- When the permission check arrives, the hub pairs it with the latest matching declaration from
  that run, matching on the exact command text or URL.
- **No matching declaration, or any of the three fields empty, means auto-deny.** The message
  back to the agent says "call declare_action with why, technique and risk first". The action
  is never shown to the operator.
- The stage prompts and agent definitions teach this protocol.

**Approval card** (all of these, as agreed):

```
┌ Diablo (Web) wants to run ─────────────────────── waiting ┐
│ $ curl -s -i https://juice-shop.local/rest/products/search?q='  │
│                                                            │
│ Why (agent):  probing the search param for SQL injection   │
│ Technique:    error-based SQLi check (WSTG-INPV-05) [explain]│
│ Target:       juice-shop.local ✓ in scope                  │
│ Risk:         read-only request, single hit                │
│                                                            │
│  [Approve]  [Deny]  [Deny + tell agent why]  [Ask a question]│
└────────────────────────────────────────────────────────────┘
```

- **Command or URL:** shown exactly as it will run.
- **Why:** the agent's own reason.
- **Technique and Risk:** short labels the agent supplies with each gated action. The prompt
  requires them, alongside Why, and points to a WSTG or OWASP API Top 10 ID where one applies.
  **[explain]** opens a short explainer for that technique (§5.5).
- **Target:** worked out by the hub, not the agent. It extracts the hosts from the command or URL
  and checks them against the engagement scope. Out-of-scope or unrecognized hosts are shown
  plainly as **✗ out of scope** or **? can't tell**, never as a check mark. This is also what
  makes RoE violations visible.
- **Enforcement by scope verdict** (operator decision), in all engagement kinds:
  - **✗ out of scope:** the hub **refuses approval**. The card offers only Deny and Deny + tell
    agent why, and the approve endpoint rejects it server-side too.
  - **? can't tell:** approvable only after the operator ticks "I've checked this host is in
    scope". The tick is recorded with the decision.
- **Ask a question:** sends the operator's question to the agent while the action stays pending.
  The answer shows under the card, and the operator then approves or denies.
- **Every decision is recorded:** the action, the reason, the scope verdict, the decision, the
  operator's message and timestamps. It is shown in the stage's history and archived.

### 5.4 Monitoring

- An **Engagement page** (new tab) shows the stages as cards, each with its status, agent, the
  last activity line and its buttons. The Research lane sits beside them.
- **Pending approvals** surface at the top of the page, whatever stage they come from, with a
  count in the tab title. Multiple pending actions from parallel stages queue there.
- Opening a stage shows its live event feed, reusing the existing monitor components
  (`components/monitor/*`), plus its approval history.
- **Stop** on a stage stops only that stage's run.

### 5.5 Learning aids

- **Technique explainers.** Each gated action names a technique. [explain] shows a short note
  (what it is, what a positive result looks like, what's risky about it), taken from pnd-notes
  when a matching note exists. Otherwise the agent is asked for a two-line explanation, which is
  shown and cached for the engagement.
- **Ask a question** (above) on approval cards, and as a general "Ask" button on any running
  stage. *(Builder-check call:)* it is answered from a **fork of the stage's agent session**
  (`--resume <session> --fork-session`). The fork runs with no gated or write tools, so it can
  only answer. The original run and its pending action are untouched, and the answer comes from
  an agent with the full context of the work. The [explain] fallback uses the same fork.
  Verified in the plan's first task, with the fallback described in §4.

### 5.6 Juice Shop lab target

- The plan includes setting up OWASP Juice Shop locally without Docker, from npm or its release
  package, and an `okay-dann lab start|stop|status` helper to run it on a fixed local port.
- The first engagement is `juice-shop-lab`, of kind `lab`. Its scope is the local host and port.
  Its authorization is "operator-owned local lab". Juice Shop's own scoreboard is the check on
  what was really found.

### 5.7 Analysis and Reporting *(builder-check call)*

- **Analysis (Sin).** Triages and validates the Web and API findings. For each finding:
  - is it real, given the recorded evidence;
  - how it works and what its preconditions are;
  - what severity, with the reason;
  - how to detect and fix it.

  Sin still only reads; it sends no traffic and never arms. Where a finding maps to a public CVE
  or PoC, it explains that too, which is its existing role. Its output goes through its existing
  `save_exploit_analysis` tool. Analysis may need a finding-level analysis record; that is a
  builder call.
- **Reporting (Sen).** Writes the engagement report from `templates/engagement-report.md` to
  `research/<engagement>/engagement-report.md`, and stores the same text as a report in the DB.
  For a bounty engagement it also drafts submissions with `draft_submission`, as today. For a
  lab, there are no submissions. Sen needs file-write access for this stage (`Write` limited to
  `research/<engagement>/`), because today's session showed Sen-class agents without a write
  tool.
- **Acceptance test (goal 6).** A Juice Shop engagement ends with that report file and DB
  report. The findings in it are checked against Juice Shop's scoreboard.

## 6. Left to the builder

- **Table design** for engagements, stages, plans and gated actions. Operator-owned and not
  writable by agents, with the plan written only through Dann's new tool. Reusing or replacing
  the existing agent-written `engagements` and `run_engagements` tables is the builder's call.
- **API route shapes**, and how the UI learns about new pending actions. Today it streams run
  events over SSE; extending that is fine.
- **How the gate MCP server talks to the hub** while it blocks (local HTTP to the hub, or the DB
  plus polling).
- **Host extraction from shell commands.** Best-effort parsing of URLs, hostnames and IPs. When
  unsure, report "? can't tell", which still requires approval.
- **Exact stage prompts**, and how each stage's output (files, DB records, final report) is
  gathered and handed to the next.
- **UI layout details** within the card and page structure above. Use `pnd-lib-react`
  components.
- **Test strategy.** Follow the repo's pytest and vitest setup. The gate's enforcement path
  (deny by default, auto-deny without a reason, scope matching) needs tests.
