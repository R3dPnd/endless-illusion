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
