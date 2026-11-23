import { useState } from "react";
import AgentPicker from "../components/agents/AgentPicker";
import ChatRoom from "../components/chat/ChatRoom";
import RunMonitor from "../components/monitor/RunMonitor";
import RunForm from "../components/run/RunForm";
import { Button, Panel, StatusBadge } from "pnd-lib-react";
import type { useAgents } from "../hooks/useAgents";
import type { useRun } from "../hooks/useRun";
import type { ConfirmedProgram } from "../types";

interface Props {
  agents: ReturnType<typeof useAgents>;
  run: ReturnType<typeof useRun>;
  programs: ConfirmedProgram[];
  programId: number | null;
  onProgramChange: (id: number | null) => void;
}

// Per-viewer layout preference; the console works the same without storage.
const MONITOR_KEY = "ei.console.showMonitor";
function loadShowMonitor(): boolean {
  try {
    return localStorage.getItem(MONITOR_KEY) === "1";
  } catch {
    return false;
  }
}
function saveShowMonitor(on: boolean) {
  try {
    localStorage.setItem(MONITOR_KEY, on ? "1" : "0");
  } catch {
    /* storage unavailable: keep the in-memory choice */
  }
}

export default function ConsolePage({ agents, run, programs, programId, onProgramChange }: Props) {
  const { selected, setSelected, selectedAgent } = agents;
  // The Monitor (raw event feed) is hidden by default so the chat gets the room.
  const [showMonitor, setShowMonitor] = useState(loadShowMonitor);
  const toggleMonitor = () =>
    setShowMonitor((on) => {
      saveShowMonitor(!on);
      return !on;
    });

  return (
    <div className={`console ${showMonitor ? "" : "console--no-monitor"}`}>
      <Panel title="Channel" className="panel--chat">
        <ChatRoom
          chat={run.chat}
          status={run.status}
          canReply={run.canReply}
          replyAgent={run.replyAgent}
          onReply={(text) => void run.reply(text)}
          onClear={run.clear}
          actions={
            <>
              {/* Stop normally lives in the Monitor; keep it reachable while that's hidden. */}
              {!showMonitor && run.busy && (
                <Button variant="danger" onClick={() => void run.stop()}>
                  Stop
                </Button>
              )}
              <Button variant="link" onClick={toggleMonitor} aria-pressed={showMonitor} className="monitor-toggle">
                {showMonitor ? "Hide monitor" : "Show monitor"}
                {!showMonitor && run.status !== "idle" && <StatusBadge status={run.status} />}
              </Button>
            </>
          }
        />
      </Panel>

      <Panel title="Agents" as="aside" className="panel--agents">
        <AgentPicker agents={agents.agents} selected={selected} onSelect={setSelected} />
      </Panel>

      <Panel title="Trigger" className="panel--form">
        <RunForm
          agent={selectedAgent}
          busy={run.busy}
          onRun={(body) => selected && run.start(selected, body)}
          programs={programs}
          programId={programId}
          onProgramChange={onProgramChange}
        />
        {selectedAgent?.notes && <p className="notes">{selectedAgent.notes}</p>}
      </Panel>

      {showMonitor && (
        <Panel title="Monitor" className="panel--monitor">
          <RunMonitor events={run.events} status={run.status} onStop={run.stop} />
        </Panel>
      )}
    </div>
  );
}
