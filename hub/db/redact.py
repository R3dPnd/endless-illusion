import re

MAX_TEXT = 65536

MASK = "[REDACTED]"

# Patterns for secrets that must never be persisted (RoE §4).
PATTERNS = [
    (re.compile(r"(authorization:\s*bearer\s+)[^\s\"']+", re.I), rf"\g<1>{MASK}"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+"), MASK),
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), MASK),
    (
        re.compile(r"\b(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key)(\s*[=:]\s*)[^\s&\"',;]+", re.I),
        rf"\g<1>\g<2>{MASK}",
    ),
]


def redact(text):
    """Mask obvious secrets in free text."""
    if not isinstance(text, str):
        return text
    for pattern, rep in PATTERNS:
        text = pattern.sub(rep, text)
    return text


def clip(text, limit=MAX_TEXT):
    """Cap text at MAX_TEXT characters."""
    return text[:limit] if isinstance(text, str) and len(text) > limit else text


def redact_deep(value):
    """Clip + redact every string inside a JSON-able value, leaving its structure intact."""
    if isinstance(value, str):
        return redact(clip(value))
    if isinstance(value, list):
        return [redact_deep(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_deep(v) for k, v in value.items()}
    return value
