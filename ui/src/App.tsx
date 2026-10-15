import type { CSSProperties } from "react";
import AgentPicker from "./components/agents/AgentPicker";
import ChatRoom from "./components/chat/ChatRoom";
import RunMonitor from "./components/monitor/RunMonitor";
import RunForm from "./components/run/RunForm";
import { Banner, Panel } from "./components/ui";
import { useAgents } from "./hooks/useAgents";
import { useRun } from "./hooks/useRun";
import { speakerFor } from "./speakers";

export default function App() {
  const { agents, selected, setSelected, selectedAgent, error } = useAgents();
  const run = useRun();
  // The selected agent's color becomes the page accent.
  const agentColor = selected ? speakerFor(selected).color : undefined;

  return (
    <div className="app" style={agentColor ? ({ "--agent": agentColor } as CSSProperties) : undefined}>
      <header className="app__header">
        <h1>Endless Illusion</h1>
        <span className="subtitle">agent control plane · the Original Seven</span>
      </header>

      {error && <Banner>Could not load agents: {error}. Is the server running on :8787?</Banner>}

      <Panel title="Channel" className="panel--chat">
        <ChatRoom chat={run.chat} status={run.status} />
      </Panel>

      <div className="layout">
        <Panel title="Agents" as="aside" className="panel--agents">
          <AgentPicker agents={agents} selected={selected} onSelect={setSelected} />
        </Panel>

        <Panel title="Trigger" className="panel--form">
          <RunForm agent={selectedAgent} busy={run.busy} onRun={(body) => selected && run.start(selected, body)} />
          {selectedAgent?.notes && <p className="notes">{selectedAgent.notes}</p>}
        </Panel>

        <Panel title="Monitor" className="panel--monitor">
          <RunMonitor events={run.events} status={run.status} onStop={run.stop} />
        </Panel>
      </div>
    </div>
  );
}
