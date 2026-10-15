import AgentPicker from "../components/agents/AgentPicker";
import ChatRoom from "../components/chat/ChatRoom";
import RunMonitor from "../components/monitor/RunMonitor";
import RunForm from "../components/run/RunForm";
import { Panel } from "../components/ui";
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

export default function ConsolePage({ agents, run, programs, programId, onProgramChange }: Props) {
  const { selected, setSelected, selectedAgent } = agents;
  return (
    <>
      <Panel title="Channel" className="panel--chat">
        <ChatRoom chat={run.chat} status={run.status} />
      </Panel>

      <div className="layout">
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

        <Panel title="Monitor" className="panel--monitor">
          <RunMonitor events={run.events} status={run.status} onStop={run.stop} />
        </Panel>
      </div>
    </>
  );
}
