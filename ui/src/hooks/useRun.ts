import { useEffect, useMemo, useRef, useState } from "react";
import type { RunEvent } from "../types";
import { openRunStream, startRun, stopRun } from "../api";
import { buildChat } from "../chat";

export interface RunRequest {
  task: string;
  scope: string;
  authorization: string;
  enableActive: boolean;
}

/** Start, stream, and stop one agent run; exposes its events and the derived chat. */
export function useRun() {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const [runId, setRunId] = useState<string | null>(null);
  const [task, setTask] = useState<string>("");
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const chat = useMemo(() => buildChat(events, task), [events, task]);

  async function start(agent: string, body: RunRequest) {
    cleanupRef.current?.();
    setEvents([]);
    setTask(body.task);
    setStatus("running");
    try {
      const res = await startRun({ agent, ...body });
      setRunId(res.id);
      cleanupRef.current = openRunStream(
        res.id,
        (evt) => {
          setEvents((prev) => [...prev, evt]);
          if (evt.kind === "closed") setStatus(evt.status);
        },
        () => setStatus((s) => (s === "running" ? "done" : s))
      );
    } catch (e) {
      setStatus("error");
      setEvents([{ kind: "error", text: (e as Error).message, ts: Date.now() }]);
    }
  }

  async function stop() {
    if (runId) await stopRun(runId);
    setStatus("stopped");
  }

  return { events, status, chat, busy: status === "running", start, stop };
}
