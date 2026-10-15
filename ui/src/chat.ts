import type { RunEvent } from "./types";

export type ChatKind = "prompt" | "message" | "handoff" | "report" | "final";

export interface ChatMessage {
  key: string;
  kind: ChatKind;
  from: string; // agent id, or "operator"
  to?: string; // addressee agent id (handoffs)
  text: string;
  ts: number;
  isError?: boolean;
  /** Subagent run stats from a report's trailer, e.g. "16 tool uses · 5m 21s". */
  meta?: string;
}

export interface Chat {
  messages: ChatMessage[];
  /** Who is currently working (for the typing indicator). */
  active?: string;
  /** Final response text, if the run finished. */
  finalText?: string;
}

export const DELEGATE_TOOLS = new Set(["Task", "Agent"]);

type Block = { type: string; [k: string]: unknown };

function resultText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((c) => (c && typeof c === "object" && (c as Block).type === "text" ? String((c as Block).text ?? "") : ""))
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
export function cleanReport(raw: string): { text: string; meta?: string } {
  let text = raw;
  const marker = "The report follows:";
  if (text.startsWith("[Subagent hand-back]") && text.includes(marker)) {
    text = text.slice(text.indexOf(marker) + marker.length).replace(/^\r?\n/, "");
    text = text.replace(/^ {2}/gm, "");
  }
  let meta: string | undefined;
  const usage = text.match(/<usage>([\s\S]*?)<\/usage>\s*$/);
  if (usage) {
    const field = (k: string) => usage[1].match(new RegExp(`${k}:\\s*(\\d+)`))?.[1];
    const tools = field("tool_uses");
    const ms = field("duration_ms");
    const parts: string[] = [];
    if (tools) parts.push(`${tools} tool uses`);
    if (ms) {
      const sec = Math.round(Number(ms) / 1000);
      parts.push(sec >= 60 ? `${Math.floor(sec / 60)}m ${sec % 60}s` : `${sec}s`);
    }
    meta = parts.join(" · ") || undefined;
    text = text.slice(0, usage.index);
  }
  text = text.replace(/\n?agentId: \S+ \(use SendMessage[^\n]*\)\s*$/, "");
  return { text: text.trim(), meta };
}

/**
 * Fold a run's stream-json events into a chat between the operator and the
 * agents. Top-level assistant text belongs to the dispatched agent; text whose
 * parent_tool_use_id points at a delegation belongs to that subagent; a
 * delegation's tool_result is the subagent's report back.
 */
export function buildChat(events: RunEvent[], task: string | undefined): Chat {
  const messages: ChatMessage[] = [];
  let root = "dann-of-thursday";
  let active: string | undefined;
  let finalText: string | undefined;
  // delegation tool_use id -> subagent id
  const delegations = new Map<string, string>();
  // speaker of each delegation's caller, so nested handoffs report to the right agent
  const callers = new Map<string, string>();

  const lastFrom = (from: string) => {
    for (let i = messages.length - 1; i >= 0; i--) if (messages[i].from === from) return messages[i];
    return undefined;
  };

  events.forEach((evt, i) => {
    if (evt.kind === "meta") {
      root = evt.agent;
      if (task) messages.push({ key: `p${i}`, kind: "prompt", from: "operator", to: root, text: task, ts: evt.ts });
      active = root;
      return;
    }
    if (evt.kind !== "claude") return;
    const data = evt.data;
    const parentId = (data.parent_tool_use_id as string | null | undefined) ?? null;
    const speaker = parentId ? delegations.get(parentId) ?? root : root;
    const raw = data.message?.content;
    const content = (Array.isArray(raw) ? raw : []) as Block[];

    if (data.type === "assistant") {
      content.forEach((b, j) => {
        if (b.type === "text" && String(b.text ?? "").trim()) {
          messages.push({ key: `a${i}.${j}`, kind: "message", from: speaker, text: String(b.text), ts: evt.ts });
          active = speaker;
        } else if (b.type === "tool_use" && DELEGATE_TOOLS.has(String(b.name))) {
          const input = (b.input ?? {}) as Record<string, unknown>;
          const target = String(input.subagent_type ?? "agent");
          if (typeof b.id === "string") {
            delegations.set(b.id, target);
            callers.set(b.id, speaker);
          }
          messages.push({
            key: `h${i}.${j}`,
            kind: "handoff",
            from: speaker,
            to: target,
            text: String(input.prompt ?? input.description ?? ""),
            ts: evt.ts,
          });
          active = target;
        } else if (b.type === "tool_use") {
          active = speaker;
        }
      });
      return;
    }

    if (data.type === "user") {
      content.forEach((b, j) => {
        if (b.type !== "tool_result") return;
        const target = delegations.get(String(b.tool_use_id));
        if (!target) return;
        const { text, meta } = cleanReport(resultText(b.content));
        // If the subagent's own messages were streamed, its last one is this report.
        const prev = lastFrom(target);
        if (prev && prev.kind === "message" && prev.text.trim() === text) {
          prev.kind = "report";
          prev.to = callers.get(String(b.tool_use_id));
          prev.meta = meta;
        } else if (text) {
          messages.push({
            key: `r${i}.${j}`,
            kind: "report",
            from: target,
            to: callers.get(String(b.tool_use_id)),
            text,
            ts: evt.ts,
            isError: b.is_error === true,
            meta,
          });
        }
        active = callers.get(String(b.tool_use_id)) ?? root;
      });
      return;
    }

    if (data.type === "result") {
      finalText = data.result ?? "";
      const prev = lastFrom(root);
      if (prev && prev.kind === "message" && prev.text.trim() === finalText.trim()) {
        prev.kind = "final";
        prev.isError = data.is_error === true;
      } else if (finalText.trim()) {
        messages.push({ key: `f${i}`, kind: "final", from: root, text: finalText, ts: evt.ts, isError: data.is_error === true });
      }
      active = undefined;
    }
  });

  return { messages, active, finalText };
}
