"""The engagement approval gate: permission decisions, pending actions, operator decisions.

Every tool call an engagement stage makes passes through `check_permission`
(from the PreToolUse hook, or the permission-prompt tool as a backstop). The
hub, not a prompt, decides; the default on any doubt is deny.

- Local-only Bash, in-workdir writes, off-scope WebFetch reading and non-gated
  tools are auto-allowed. "Off-scope" for WebFetch is strict (Ruling R14, see
  `gate_rules.fetch_verdict`): a plain public DNS name unrelated to every scope
  host. IPs, localhost, wildcard-DNS names and port-only mismatches are gated.
- Writes outside `research/<slug>/` are auto-denied.
- Anything that touches a target needs a matching, unused `declare_action`
  declaration from the same run, then waits (`pending`) for the operator.

Every call is recorded in `gate_actions`; that table is the stage history the
operator sees. Status changes all happen inside `db.transaction()` and re-check
the current status there, so racing decisions cannot both apply.

Replies are neutral `{"behavior": "allow"|"deny", "message": str}`; callers
serialize them for their channel. An approval allows the ORIGINAL input that
was recorded -- there is no way to substitute a modified input.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .db import now_iso
from .gate_rules import classify_bash, classify_write, extract_hosts, fetch_verdict, scope_verdict

DECLARE_FIRST = "call declare_action with why, technique and risk first"
OPERATOR_DENIED = "operator denied"
CANCELLED = "action was cancelled"

WRITE_PATH_KEYS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
GATED_TOOLS = frozenset({"Bash", "WebFetch", *WRITE_PATH_KEYS})

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


class GateRefused(PermissionError):
    """The operator asked for something the gate never permits (HTTP 409)."""

    status = 409


@dataclass(frozen=True)
class RunContext:
    run_id: str
    engagement_id: int
    stage: str
    slug: str
    scope_hosts: list[str]
    workdir: Path


def _allow(message: str = "") -> dict:
    return {"behavior": "allow", "message": message}


def _deny(message: str) -> dict:
    return {"behavior": "deny", "message": message}


def context_for_run(db, run_id, repo_root: Path) -> RunContext | None:
    """The engagement stage a run belongs to (via `ops_stages.run_id`), or None."""
    if not isinstance(run_id, str) or not run_id:
        return None
    row = db.get(
        "SELECT s.engagement_id, s.stage, e.slug, e.scope_hosts FROM ops_stages s"
        " JOIN ops_engagements e ON e.id = s.engagement_id WHERE s.run_id = ? ORDER BY s.id DESC LIMIT 1",
        run_id,
    )
    if row is None or not _SLUG_RE.match(row["slug"] or ""):
        return None
    try:
        hosts = json.loads(row["scope_hosts"] or "[]")
    except ValueError:
        return None
    if not isinstance(hosts, list):
        return None
    workdir = (Path(repo_root) / "research" / row["slug"]).resolve()
    return RunContext(run_id, row["engagement_id"], row["stage"], row["slug"], [h for h in hosts if isinstance(h, str)], workdir)


def _filled(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def record_declaration(db, run_id, target, why, technique, risk) -> int:
    """Store an agent's `declare_action`. `target` is kept byte-for-byte (it must
    equal the later command or URL exactly). Raises ValueError on any empty field."""
    for name, value in (("run_id", run_id), ("target", target), ("why", why), ("technique", technique), ("risk", risk)):
        if not _filled(value):
            raise ValueError(f"{name} is required")
    did, _ = db.run(
        "INSERT INTO gate_declarations (run_id, target, why, technique, risk, created_at) VALUES (?,?,?,?,?,?)",
        run_id, target, why, technique, risk, now_iso(),
    )
    return did


def _record(db, ctx, tool_name, tool_input, status, verdict, hosts=(), message=None, decl=None) -> int:
    now = now_iso()
    aid, _ = db.run(
        "INSERT INTO gate_actions (run_id, engagement_id, stage, tool_name, input, target, why, technique, risk,"
        " hosts, verdict, status, message, created_at, decided_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ctx.run_id if ctx else None, ctx.engagement_id if ctx else None, ctx.stage if ctx else None,
        str(tool_name), json.dumps(tool_input, default=str),
        *((decl["target"], decl["why"], decl["technique"], decl["risk"]) if decl else (None, None, None, None)),
        json.dumps(list(hosts)), verdict, status, message, now,
        None if status == "pending" else now,
    )
    return aid


def check_permission(db, ctx: RunContext | None, tool_name, tool_input, wait: Callable[[int], dict]) -> dict:
    """Decide one tool call; gated calls block in `wait(action_id)` for the operator.

    Fail-closed: any exception (database locked, a rules bug, a failing `wait`)
    returns deny `gate error: <ExceptionType>`, with a best-effort `auto_denied`
    record (and the pending action, if any, expired)."""
    pending = []
    try:
        reply = _decide_call(db, ctx, tool_name, tool_input, pending.append)
        if reply is not None:
            return reply
        reply = wait(pending[0])
        if not isinstance(reply, dict) or reply.get("behavior") not in ("allow", "deny"):
            raise TypeError("wait returned a malformed reply")
        return {"behavior": reply["behavior"], "message": str(reply.get("message") or "")}
    except Exception as err:
        msg = f"gate error: {type(err).__name__}"
        try:
            if pending:
                with db.transaction():
                    db.run(
                        "UPDATE gate_actions SET status = 'expired', message = ?, decided_at = ? WHERE id = ? AND status = 'pending'",
                        msg, now_iso(), pending[0],
                    )
            _record(db, ctx, tool_name, tool_input if isinstance(tool_input, dict) else {}, "auto_denied", "none", message=msg)
        except Exception:
            pass
        return _deny(msg)


def _decide_call(db, ctx, tool_name, tool_input, set_pending) -> dict | None:
    """The decision proper. Returns a reply, or None after creating a pending action (passed to `set_pending`)."""
    if not isinstance(tool_input, dict):
        tool_input = {}
    if ctx is None:
        _record(db, None, tool_name, tool_input, "auto_denied", "none", message="no engagement stage for this run")
        return _deny("no engagement stage for this run")

    if tool_name in WRITE_PATH_KEYS:
        path = tool_input.get(WRITE_PATH_KEYS[tool_name])
        if isinstance(path, str) and classify_write(path, ctx.workdir) == "local":
            _record(db, ctx, tool_name, tool_input, "auto_allowed", "none")
            return _allow()
        msg = f"writes are limited to research/{ctx.slug}/ (absolute paths)"
        _record(db, ctx, tool_name, tool_input, "auto_denied", "none", message=msg)
        return _deny(msg)

    if tool_name == "Bash":
        target = tool_input.get("command")
        target = target if isinstance(target, str) else ""
        if classify_bash(target, ctx.workdir) == "local":
            _record(db, ctx, tool_name, tool_input, "auto_allowed", "none")
            return _allow()
        hosts, indirect = extract_hosts(target, strict=True, workdir=ctx.workdir)
        verdict = scope_verdict(hosts, indirect, ctx.scope_hosts)
        if verdict == "none":  # R8: "no host found" is not "no target"
            verdict = "unknown"
    elif tool_name == "WebFetch":
        target = tool_input.get("url")
        if not isinstance(target, str) or not target.strip():
            _record(db, ctx, tool_name, tool_input, "auto_denied", "none", message="WebFetch needs a url")
            return _deny("WebFetch needs a url")
        hosts, indirect = extract_hosts(target, strict=False)
        # R14: only a plain public DNS name unrelated to every scope host is free research reading.
        # Aliases (IPs, localhost, wildcard DNS) and port-only mismatches come back "unknown": gated.
        verdict = fetch_verdict(hosts, indirect, ctx.scope_hosts)
        if verdict == "out":
            _record(db, ctx, tool_name, tool_input, "auto_allowed", verdict, hosts)
            return _allow()
    else:
        _record(db, ctx, tool_name, tool_input, "auto_allowed", "none")
        return _allow()

    # Gated: consume the most recent unused exact-match declaration and go pending.
    with db.transaction():
        decl = db.get(
            "SELECT * FROM gate_declarations WHERE run_id = ? AND target = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1",
            ctx.run_id, target,
        ) if target else None
        if decl is None or not all(_filled(decl[k]) for k in ("target", "why", "technique", "risk")) or decl["target"] != target:
            _record(db, ctx, tool_name, tool_input, "auto_denied", verdict, hosts, message=DECLARE_FIRST)
            return _deny(DECLARE_FIRST)
        aid = _record(db, ctx, tool_name, tool_input, "pending", verdict, hosts, decl=decl)
        db.run("UPDATE gate_declarations SET used_at = ?, action_id = ? WHERE id = ? AND used_at IS NULL", now_iso(), aid, decl["id"])
    set_pending(aid)
    return None


def _reply_for(row, run_id=None) -> dict | None:
    """The agent's reply for a waited-on action; None while still pending.
    Only an `approved` row (of the waiting run, when given) ever allows."""
    if row is None:
        return _deny("gate action not found")
    if run_id is not None and row["run_id"] != run_id:
        return _deny("gate action belongs to another run")
    status = row["status"]
    if status == "pending":
        return None
    if status == "approved":
        return _allow(row["message"] or "")
    if status == "denied":
        return _deny(row["message"] or OPERATOR_DENIED)
    if status in ("expired", "cancelled"):
        return _deny(CANCELLED)
    return _deny(f"action is {status}, not awaiting approval")


def wait_for_decision(db, action_id, poll=0.5, timeout=None, run_id=None) -> dict:
    """Block until the action is decided. On `timeout` (seconds) it is marked
    `expired` and denied. With `run_id`, an action of another run is denied."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        reply = _reply_for(db.get("SELECT run_id, status, message FROM gate_actions WHERE id = ?", action_id), run_id)
        if reply is not None:
            return reply
        if deadline is not None and time.monotonic() >= deadline:
            with db.transaction():
                db.run(
                    "UPDATE gate_actions SET status = 'expired', decided_at = ? WHERE id = ? AND status = 'pending'",
                    now_iso(), action_id,
                )
                row = db.get("SELECT run_id, status, message FROM gate_actions WHERE id = ?", action_id)
            return _reply_for(row, run_id) or _deny(CANCELLED)
        time.sleep(poll)


def _action(row):
    if row is not None:
        for key, default in (("input", {}), ("hosts", [])):
            try:
                row[key] = json.loads(row[key]) if row[key] else default
            except ValueError:
                row[key] = default
    return row


def decide(db, action_id, approve: bool, message: str = "", scope_ack: bool = False) -> dict:
    """The operator's decision on a pending action. Returns the updated action.

    Raises GateRefused (409) when approving an `out` verdict, or `unknown`/`none`
    without `scope_ack`; ValueError when the action isn't pending."""
    with db.transaction():
        row = db.get("SELECT id, status, verdict FROM gate_actions WHERE id = ?", action_id)
        if row is None:
            raise ValueError("no such gate action")
        if row["status"] != "pending":
            raise ValueError(f"action is already {row['status']}")
        if approve and row["verdict"] == "out":
            raise GateRefused("an out-of-scope action cannot be approved")
        if approve and row["verdict"] in ("unknown", "none") and not scope_ack:
            raise GateRefused("scope is unknown: approving needs scopeAck")
        db.run(
            "UPDATE gate_actions SET status = ?, message = ?, scope_ack = ?, decided_at = ? WHERE id = ? AND status = 'pending'",
            "approved" if approve else "denied", message or None, 1 if scope_ack else 0, now_iso(), action_id,
        )
        return _action(db.get("SELECT * FROM gate_actions WHERE id = ?", action_id))


def pending_actions(db, engagement_id=None) -> list[dict]:
    if engagement_id is None:
        rows = db.all("SELECT * FROM gate_actions WHERE status = 'pending' ORDER BY id")
    else:
        rows = db.all("SELECT * FROM gate_actions WHERE status = 'pending' AND engagement_id = ? ORDER BY id", engagement_id)
    return [_action(r) for r in rows]


def cancel_for_run(db, run_id) -> int:
    """Cancel a stopped run's pending actions; its waiter gets deny."""
    with db.transaction():
        _, n = db.run(
            "UPDATE gate_actions SET status = 'cancelled', decided_at = ? WHERE run_id = ? AND status = 'pending'",
            now_iso(), run_id,
        )
    return n


def expire_orphaned(db, live_run_ids: set[str]) -> int:
    """Expire pending actions whose run isn't live (e.g. after a hub restart)."""
    live = set(live_run_ids or ())
    with db.transaction():
        rows = db.all("SELECT id, run_id FROM gate_actions WHERE status = 'pending'")
        now, n = now_iso(), 0
        for r in rows:
            if r["run_id"] not in live:
                n += db.run("UPDATE gate_actions SET status = 'expired', decided_at = ? WHERE id = ? AND status = 'pending'", now, r["id"])[1]
    return n
