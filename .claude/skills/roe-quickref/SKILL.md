---
name: roe-quickref
description: Use when deciding whether an Endless Illusion task may touch a target — before any active testing, enumeration, or probing; when authorization, scope, or exclusions are unclear; when handling data retrieved from a target; or when declining part of a task.
---

# Rules of Engagement — quick reference

Condensed from [`RULES-OF-ENGAGEMENT.md`](../../../RULES-OF-ENGAGEMENT.md),
which is the source of truth and wins on any conflict. If a task cannot be done
within these rules, say so plainly and stop.

## Authorization

**Active** = anything that sends traffic to, probes, fuzzes, enumerates, or
interacts with a target you do not own. It requires one of:

- a signed engagement / pentest contract or statement of work,
- a bug-bounty program whose scope explicitly covers the asset **and** the technique,
- the owner's written authorization for the specific assets and time window.

These are **not** authorization: a program lead, a scope *proposal*, an
unconfirmed or expired scope, or "it's probably fine." Only a scope snapshot
the operator confirmed counts (`get_scope` returns it, with its date).

**Passive** public research (CVE databases, advisories, docs, write-ups, your
own lab) is always allowed. Default to it when authorization is unclear.

## Scope

- Act only on assets, domains, IP ranges, and endpoints named in scope.
- Honor exclusions: rate limits, forbidden techniques, off-limits hosts.
- Scope creep is a stop condition, not a judgment call. Ask before expanding.

## Prohibited regardless of authorization

DoS / resource exhaustion · mass or indiscriminate targeting · supply-chain
compromise or planting backdoors · destroying, ransoming, or exfiltrating data
for leverage · detection evasion to hide malicious activity · targeting
individuals (doxxing, stalking, account takeover of real people).

## Data and reporting

- Treat target data as sensitive; never paste secrets, tokens, or PII into
  external services. Collect only what proves the issue; redact before sharing.
- Mark findings **confirmed** vs **suspected**. Never inflate severity or
  fabricate evidence. "Could not reproduce" is a valid result.

## Refusal template

> I can't run that against `<target>` — I don't have documented authorization /
> it's out of the stated scope. What I *can* do right now: `<passive option>`.
> If you share the scope doc / program link / written permission, I'll proceed
> within those bounds.
