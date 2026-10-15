import { useEffect, useMemo, useState } from "react";
import { openRunStream } from "../../api";
import { buildChat } from "../../chat";
import type { RunEvent, RunSummary } from "../../types";
import ChatRoom from "../chat/ChatRoom";
import RunMonitor from "../monitor/RunMonitor";

/** Read-only replay of a stored run through the same Channel and Monitor views. */
export default function RunReplay({ run }: { run: RunSummary }) {
  const [events, setEvents] = useState<RunEvent[]>([]);

  useEffect(() => {
    setEvents([]);
    return openRunStream(run.id, (evt) => setEvents((prev) => [...prev, evt]), () => {});
  }, [run.id]);

  const chat = useMemo(() => buildChat(events, run.task), [events, run.task]);
  const status = run.status === "running" ? "running" : run.status;

  return (
    <div className="replay">
      <ChatRoom chat={chat} status={status} />
      <details className="replay__monitor">
        <summary>Raw event log ({events.length})</summary>
        <RunMonitor events={events} status={status} onStop={() => {}} />
      </details>
    </div>
  );
}
