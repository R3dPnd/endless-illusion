import type { RunEvent } from "./types";
import { DELEGATE_TOOLS, HANDBACK_TOOLS, cleanReport, resultText } from "../shared/report.mjs";

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

export { DELEGATE_TOOLS, cleanReport };

type Block = { type: string; [k: string]: unknown };

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
  // delegation id -> report the subagent delivered via SubagentHandback
  const handbacks = new Map<string, string>();
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
        } else if (b.type === "tool_use" && HANDBACK_TOOLS.has(String(b.name)) && parentId && delegations.has(parentId)) {
          handbacks.set(parentId, String((b.input as { message?: unknown } | undefined)?.message ?? ""));
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
        const cleaned = cleanReport(resultText(b.content));
        const text = handbacks.get(String(b.tool_use_id)) ?? cleaned.text;
        const meta = cleaned.meta;
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
