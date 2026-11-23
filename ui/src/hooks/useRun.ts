import { useEffect, useMemo, useRef, useState } from "react";
import type { RunEvent } from "../types";
import { openRunStream, startRun, stopRun, type StartRunBody } from "../api";
import { buildThread, type ThreadSegment } from "../chat";

export interface RunRequest {
  task: string;
  scope: string;
  authorization: string;
  enableActive: boolean;
  programId?: number;
}

let segSeq = 0;

/**
 * The console conversation: a thread of runs. Triggering an agent appends a
 * new run to the thread instead of clearing it; replying resumes the latest
 * run's claude session (the hub inherits its agent, scope, authorization, and
 * tools). `clear` starts a new conversation.
 */
export function useRun() {
  const [segments, setSegments] = useState<ThreadSegment[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const chat = useMemo(() => buildThread(segments), [segments]);
  const current = segments[segments.length - 1];
  const events = current?.events ?? [];
  const busy = status === "running";

  const patch = (id: string, fn: (s: ThreadSegment) => ThreadSegment) =>
    setSegments((prev) => prev.map((s) => (s.id === id ? fn(s) : s)));

  async function launch(body: StartRunBody & { continueRun?: string }) {
    cleanupRef.current?.();
    cleanupRef.current = null;
    const id = `s${++segSeq}`;
    setSegments((prev) => [...prev, { id, runId: null, task: body.task, events: [] }]);
    setStatus("running");
    try {
      const res = await startRun(body);
      patch(id, (s) => ({ ...s, runId: res.id }));
      cleanupRef.current = openRunStream(
        res.id,
        (evt) => {
          patch(id, (s) => ({ ...s, events: [...s.events, evt] }));
          if (evt.kind === "closed") setStatus(evt.status);
        },
        () => setStatus((s) => (s === "running" ? "done" : s))
      );
    } catch (e) {
      setStatus("error");
      // Keep the operator's message visible, with the error under it.
      const err: RunEvent = { kind: "error", text: (e as Error).message, ts: Date.now() };
      patch(id, (s) => ({ ...s, events: [...s.events, err] }));
    }
  }

  function start(agent: string, body: RunRequest) {
    return launch({ agent, ...body });
  }

  /** The most recent run that actually started; replies continue its session. */
  const replyTarget = [...segments].reverse().find((s) => s.runId);
  const replyAgent = replyTarget?.events.find((e) => e.kind === "meta")?.agent;

  function reply(text: string) {
    if (!replyTarget?.runId || busy || !text.trim()) return;
    return launch({ agent: replyAgent ?? "", task: text, continueRun: replyTarget.runId });
  }

  function clear() {
    if (busy) return;
    cleanupRef.current?.();
    cleanupRef.current = null;
    setSegments([]);
    setStatus("idle");
  }

  async function stop() {
    if (current?.runId) await stopRun(current.runId);
    setStatus("stopped");
  }

  return {
    events,
    status,
    chat,
    busy,
    start,
    stop,
    reply,
    clear,
    canReply: !busy && !!replyTarget?.runId,
    replyAgent,
  };
}
