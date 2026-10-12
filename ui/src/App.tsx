import { useEffect, useRef, useState } from "react";
import type { AgentPolicy, RunEvent } from "./types";
import { getAgents, startRun, stopRun, openRunStream } from "./api";
import AgentPicker from "./components/AgentPicker";
import RunForm from "./components/RunForm";
import RunMonitor from "./components/RunMonitor";

export default function App() {
  const [agents, setAgents] = useState<AgentPolicy[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const [runId, setRunId] = useState<string | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getAgents()
      .then((list) => {
        setAgents(list);
        setSelected((cur) => cur ?? list[0]?.agent ?? null);
      })
      .catch((e) => setLoadError(e.message));
  }, []);

  useEffect(() => () => cleanupRef.current?.(), []);

  const selectedAgent = agents.find((a) => a.agent === selected);
  const busy = status === "running";

  async function handleRun(body: {
    task: string;
    scope: string;
    authorization: string;
    enableActive: boolean;
  }) {
    if (!selected) return;
    cleanupRef.current?.();
    setEvents([]);
    setStatus("running");
    try {
      const res = await startRun({ agent: selected, ...body });
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

  async function handleStop() {
    if (runId) await stopRun(runId);
    setStatus("stopped");
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>Endless Illusion</h1>
        <span className="subtitle">agent control plane · the Original Seven</span>
      </header>

      {loadError && (
        <div className="banner banner--error">
          Could not load agents: {loadError}. Is the server running on :8787?
        </div>
      )}

      <div className="layout">
        <aside className="panel panel--agents">
          <h2>Agents</h2>
          <AgentPicker agents={agents} selected={selected} onSelect={setSelected} />
        </aside>

        <section className="panel panel--form">
          <h2>Trigger</h2>
          <RunForm agent={selectedAgent} busy={busy} onRun={handleRun} />
          {selectedAgent?.notes && (
            <p className="notes">{selectedAgent.notes}</p>
          )}
        </section>

        <section className="panel panel--monitor">
          <h2>Monitor</h2>
          <RunMonitor events={events} status={status} onStop={handleStop} />
        </section>
      </div>
    </div>
  );
}
