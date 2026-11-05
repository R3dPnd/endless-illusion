"""Subagent report helpers (mirrors ui/shared/report.mjs, which the browser uses)."""

import re

# Tool names the CLI uses for delegating to a subagent.
DELEGATE_TOOLS = {"Task", "Agent"}

# Tool a subagent calls to deliver its report (Claude Code 2.1+). Its input
# carries the report; the delegation's own tool_result then only points to it.
HANDBACK_TOOLS = {"SubagentHandback"}


def result_text(content):
    """Text of a tool_result's content (string or array of text blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [str(c.get("text") or "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return "\n\n".join(p for p in parts if p)
    return ""


def clean_report(raw):
    """
    Strip the harness framing from a subagent's hand-back: the "[Subagent
    hand-back] … The report follows:" preamble, the two-space indent on every
    report line, and the trailing agentId / <usage> lines (kept as stats).
    Returns (text, meta) where meta is a short stats string or None.
    """
    text = str(raw if raw is not None else "")
    marker = "The report follows:"
    if text.startswith("[Subagent hand-back]") and marker in text:
        text = re.sub(r"^\r?\n", "", text[text.index(marker) + len(marker) :])
        text = re.sub(r"^ {2}", "", text, flags=re.M)
    meta = None
    usage = re.search(r"<usage>([\s\S]*?)</usage>\s*\Z", text)
    if usage:

        def field(k):
            m = re.search(rf"{k}:\s*(\d+)", usage.group(1))
            return m.group(1) if m else None

        tools, ms = field("tool_uses"), field("duration_ms")
        parts = []
        if tools:
            parts.append(f"{tools} tool uses")
        if ms:
            sec = round(int(ms) / 1000)
            parts.append(f"{sec // 60}m {sec % 60}s" if sec >= 60 else f"{sec}s")
        meta = " · ".join(parts) or None
        text = text[: usage.start()]
    text = re.sub(r"\n?agentId: \S+ \(use SendMessage[^\n]*\)\s*\Z", "", text)
    return text.strip(), meta
