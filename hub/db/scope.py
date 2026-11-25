"""
Canonical shapes for scope proposals and snapshots.

propose_scope takes free JSON, and real policies don't fit one mold: agents
send exclusions grouped by heading ({"conduct": [...]}), scope items with
extra fields (pays, conditions, tier, a list of subdomains), or bare strings.
Readers (the Bounties page, get_scope, the Trigger form) get one shape:

    in_scope / out_of_scope: [{"asset": str, "type"?: str, "notes"?: str}]
    exclusions:              [str]

Nothing is dropped. Extra fields fold into `notes` and grouped exclusions keep
their heading, so the operator still sees everything they are confirming. The
stored JSON is left as the agent wrote it.
"""

import json
import re
import time
from datetime import datetime

_KNOWN = ("asset", "type", "notes")
_ASSET_KEYS = ("asset", "host", "target", "name", "url", "domain", "pattern")


def _text(value):
    """One readable line for any JSON value."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(t for t in (_text(v) for v in value) if t)
    if isinstance(value, dict):
        return "; ".join(f"{_label(k)}: {t}" for k, v in value.items() if (t := _text(v)))
    return json.dumps(value, ensure_ascii=False)


def _label(key):
    return str(key).replace("_", " ").strip()


def _item(raw):
    """One scope entry as {asset, type?, notes?}, or None if it has nothing to show."""
    if isinstance(raw, dict):
        asset_key = next((k for k in _ASSET_KEYS if _text(raw.get(k))), None)
        asset = _text(raw.get(asset_key)) if asset_key else ""
        extras = {k: v for k, v in raw.items() if k not in _KNOWN and k != asset_key}
        notes = "; ".join(t for t in [_text(raw.get("notes")), *(f"{_label(k)}: {_text(v)}" for k, v in extras.items() if _text(v))] if t)
        if not asset:
            asset, notes = (notes, "") if notes else ("", "")
        if not asset:
            return None
        item = {"asset": asset}
        if _text(raw.get("type")):
            item["type"] = _text(raw.get("type"))
        if notes:
            item["notes"] = notes
        return item
    text = _text(raw)
    return {"asset": text} if text else None


def scope_items(value):
    """in_scope / out_of_scope in canonical form, from whatever the agent stored."""
    if isinstance(value, dict):
        # {"heading": [...]} or {"asset": {...}}: one group per key.
        out = []
        for key, group in value.items():
            entries = group if isinstance(group, list) else [group]
            for entry in entries:
                item = _item(entry)
                if item and not isinstance(entry, dict):
                    item["notes"] = "; ".join(t for t in (item.get("notes", ""), _label(key)) if t)
                if item:
                    out.append(item)
        return out
    entries = value if isinstance(value, list) else [value]
    return [item for item in (_item(e) for e in entries) if item]


def exclusion_lines(value):
    """Exclusions as plain strings; grouped exclusions keep their heading."""
    if isinstance(value, dict):
        lines = []
        for key, group in value.items():
            for entry in group if isinstance(group, list) else [group]:
                if t := _text(entry):
                    lines.append(f"{_label(key)}: {t}")
        return lines
    entries = value if isinstance(value, list) else [value]
    return [t for t in (_text(e) for e in entries) if t]


# ---- engagement scope from a confirmed snapshot (I1) ----

STALE_MS = 30 * 24 * 60 * 60 * 1000  # a snapshot older than this must be re-confirmed before arming

# Scope items whose type says they are not network hosts (app-store ids look like DNS names).
_NON_HOST_TYPES = ("android", "ios", "mobile", "app store", "apk", "ipa", "executable", "binary", "hardware",
                   "source", "desktop", "firmware")
_HOST_RE = re.compile(
    r"^(?:\*\.)?(?:[a-z0-9_](?:[a-z0-9_\-]{0,61}[a-z0-9_])?\.)+[a-z]{2,63}(?::\d{1,5})?$"
    r"|^(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?$"
    r"|^\[[0-9a-f:.]+\](?::\d{1,5})?$"
)


def asset_hosts(text):
    """Every host-shaped token of a scope asset or exclusion line, as `host`, `host:port` or
    `*.domain` (lowercase; scheme, userinfo and path dropped). `*` and `*.<tld>` are too broad
    and are dropped; anything else that is not plainly a host (prose, app ids) is ignored."""
    out = []
    for tok in re.split(r"[\s,;()<>\"'`]+", (text or "").lower()):
        tok = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", tok)
        tok = re.split(r"[/?#\\]", tok, maxsplit=1)[0].rsplit("@", 1)[-1].strip(".:")
        if not tok or not _HOST_RE.match(tok):
            continue
        if tok.startswith("*.") and "." not in tok[2:].split(":")[0]:
            continue
        if tok not in out:
            out.append(tok)
    return out


def _item_hosts(items):
    out = []
    for item in items:
        if any(t in (item.get("type") or "").lower() for t in _NON_HOST_TYPES):
            continue
        for h in asset_hosts(item.get("asset")):
            if h not in out:
                out.append(h)
    return out


def _json(value, default):
    try:
        return json.loads(value) if value else default
    except ValueError:
        return default


def snapshot_scope(db, snapshot_id, now_ms=None):
    """{in, out, stale, snapshot_id} for one confirmed snapshot. `in`: hosts of its in_scope
    assets; `out`: hosts of its out_of_scope assets and every host named in its exclusions
    (always out, even if in_scope also matches them); `stale`: confirmed over 30 days ago."""
    snap = db.get("SELECT * FROM scope_snapshots WHERE id = ?", snapshot_id) if snapshot_id is not None else None
    if snap is None:
        return {"in": [], "out": [], "stale": False, "snapshot_id": None}
    out = _item_hosts(scope_items(_json(snap["out_of_scope"], [])))
    for line in exclusion_lines(_json(snap["exclusions"], [])):
        for h in asset_hosts(line):
            if h not in out:
                out.append(h)
    now_ms = now_ms if now_ms is not None else time.time() * 1000
    confirmed = datetime.fromisoformat(snap["confirmed_at"].replace("Z", "+00:00")).timestamp() * 1000
    return {
        "in": _item_hosts(scope_items(_json(snap["in_scope"], []))),
        "out": out,
        "stale": now_ms - confirmed > STALE_MS,
        "snapshot_id": snap["id"],
    }
