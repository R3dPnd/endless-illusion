# Endless Illusion

A central hub for cybersecurity research agents.

Each agent is a **Markdown dossier** — a self-contained persona + operating
procedure you can paste into any capable LLM (Claude, etc.). They investigate
known issues (CVEs), research bug-bounty targets, and probe websites/APIs
**only within explicit, written authorization**. The repo also collects the
code and research material the agents produce.

The seven agents are skinned after the **Original Seven** armors of
*Gun × Sword* — the humanoid "Originals," each named for a day of the week.

> ⚠️ **Authorization first.** Every agent inherits
> [`RULES-OF-ENGAGEMENT.md`](RULES-OF-ENGAGEMENT.md). No active testing against
> any target without documented scope and permission. When in doubt, the agent
> refuses and asks.

## The Original Seven

| Codename | Day | Specialty | Dossier |
|---|---|---|---|
| **Saudade of Sunday** | Sun | Recon & attack-surface mapping | [dossier](agents/saudade-of-sunday.md) |
| **Diablo of Monday** | Mon | Web application testing (in-scope) | [dossier](agents/diablo-of-monday.md) |
| **Metsä of Tuesday** | Tue | API testing (in-scope) | [dossier](agents/metsa-of-tuesday.md) |
| **Dahlia of Wednesday** | Wed | CVE & known-issue research | [dossier](agents/dahlia-of-wednesday.md) |
| **Dann of Thursday** | Thu | Orchestrator / lead coordinator | [dossier](agents/dann-of-thursday.md) |
| **Sin of Friday** | Fri | Exploit & PoC analysis (read/explain) | [dossier](agents/sin-of-friday.md) |
| **Sen of Saturday** | Sat | Bug-bounty scope validation & reporting | [dossier](agents/sen-of-saturday.md) |

## Layout

```
endless-illusion/
├── README.md                 # this file
├── CLAUDE.md                 # orchestrator (Dann) context for the main session
├── RULES-OF-ENGAGEMENT.md    # shared authorization policy (all agents inherit)
├── agents/
│   ├── <name>.md             # full human-readable dossier (canonical persona)
│   └── <name>.policy.json    # machine-readable tool policy per agent
├── .claude/agents/           # Claude Code subagent definitions (derived)
├── research/                 # findings & notes, one folder per engagement
├── code/                     # tooling and PoCs the agents produce
└── templates/                # dossier + report templates for new work
```

## Two ways to run the agents

### A. Native Claude Code subagents (wired up)

Run `claude` from the repo root. The main session reads
[`CLAUDE.md`](CLAUDE.md) and acts as **Dann of Thursday**, the orchestrator; it
delegates to the six specialists defined in
[`.claude/agents/`](.claude/agents/) via its Agent tool. Just describe the task
and target + authorization, and Dann routes it.

> Subagents can't spawn subagents, so Dann is the *main* session, not a
> subagent file.

**Tool policy = safety enforcement.** Each subagent's `tools:` frontmatter is
derived from its [`agents/<name>.policy.json`](agents/). Active-testing agents
(Diablo, Metsä) and active recon (Saudade) ship with **passive tools only** —
the `authorized_active` toolset in the policy file (which adds `Bash`) is
enabled *only* when you have confirmed authorization and validated scope.

### B. Portable dossiers (any LLM)

Each [`agents/<name>.md`](agents/) is a self-contained persona. Paste the
dossier plus `RULES-OF-ENGAGEMENT.md` as opening context into any capable LLM,
then give it the task + scope. Useful outside Claude Code.

In both cases, write findings into `research/<engagement-name>/` using
[`templates/engagement-report.md`](templates/engagement-report.md).

## Adding an agent

Copy [`templates/agent-dossier.md`](templates/agent-dossier.md), fill it in, and
add a row to the roster table above.
