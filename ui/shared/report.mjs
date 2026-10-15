// Shared by the hub (server) and the browser client.

/** Tool names the CLI uses for delegating to a subagent. */
export const DELEGATE_TOOLS = new Set(["Task", "Agent"]);

/** Text of a tool_result's content (string or array of text blocks). */
export function resultText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((c) => (c && typeof c === "object" && c.type === "text" ? String(c.text ?? "") : ""))
      .filter(Boolean)
      .join("\n\n");
  }
  return "";
}

/**
 * Strip the harness framing from a subagent's hand-back: the "[Subagent
 * hand-back] … The report follows:" preamble, the two-space indent on every
 * report line, and the trailing agentId / <usage> lines (kept as stats).
 */
export function cleanReport(raw) {
  let text = String(raw ?? "");
  const marker = "The report follows:";
  if (text.startsWith("[Subagent hand-back]") && text.includes(marker)) {
    text = text.slice(text.indexOf(marker) + marker.length).replace(/^\r?\n/, "");
    text = text.replace(/^ {2}/gm, "");
  }
  let meta;
  const usage = text.match(/<usage>([\s\S]*?)<\/usage>\s*$/);
  if (usage) {
    const field = (k) => usage[1].match(new RegExp(`${k}:\\s*(\\d+)`))?.[1];
    const tools = field("tool_uses");
    const ms = field("duration_ms");
    const parts = [];
    if (tools) parts.push(`${tools} tool uses`);
    if (ms) {
      const sec = Math.round(Number(ms) / 1000);
      parts.push(sec >= 60 ? `${Math.floor(sec / 60)}m ${sec % 60}s` : `${sec}s`);
    }
    meta = parts.join(" · ") || undefined;
    text = text.slice(0, usage.index);
  }
  text = text.replace(/\n?agentId: \S+ \(use SendMessage[^\n]*\)\s*$/, "");
  return meta ? { text: text.trim(), meta } : { text: text.trim() };
}
