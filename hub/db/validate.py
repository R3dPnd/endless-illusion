import json

from .redact import MAX_TEXT, clip, redact, redact_deep


class ValidationError(ValueError):
    pass


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _to_stored(label, spec, value):
    """Convert one incoming value to its stored form, or raise a descriptive error."""

    def fail(why):
        raise ValidationError(f"{label}: {why}")

    kind = spec["type"]
    if kind == "text":
        if not isinstance(value, str):
            fail("must be a string")
        return redact(clip(value))
    if kind == "int":
        if not is_int(value):
            fail("must be an integer")
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            fail("must be true or false")
        return 1 if value else 0
    if kind == "enum":
        if value not in spec["values"]:
            fail(f"must be one of {', '.join(spec['values'])}")
        return value
    if kind == "json":
        try:
            stored = json.dumps(redact_deep(value), ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            fail("must be JSON-serializable")
        if len(stored) > MAX_TEXT:
            fail("is too large")
        return stored
    fail(f"has unsupported type {kind}")


def validate_fields(table, columns, fields):
    """
    Validate `fields` against a table's column specs and return a
    column -> stored-value map. Unknown fields and missing required fields are errors.
    """
    out = {}
    for key in fields:
        if key == "supersedes":
            continue
        if key not in columns:
            raise ValidationError(f'{table}: unknown field "{key}"')
    for col, spec in columns.items():
        value = fields.get(col)
        if value is None:
            if not spec.get("optional"):
                raise ValidationError(f"{table}.{col}: required")
            continue
        out[col] = _to_stored(f"{table}.{col}", spec, value)
    supersedes = fields.get("supersedes")
    if supersedes is not None:
        if not is_int(supersedes):
            raise ValidationError(f"{table}.supersedes: must be an integer")
        out["supersedes"] = supersedes
    return out
