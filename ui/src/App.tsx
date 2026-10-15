import type { CSSProperties } from "react";
import { Banner, Tabs } from "./components/ui";
import { useAgents } from "./hooks/useAgents";
import { useHashRoute, type Route } from "./hooks/useHashRoute";
import { useRun } from "./hooks/useRun";
import ArchivePage from "./pages/ArchivePage";
import ConsolePage from "./pages/ConsolePage";
import { speakerFor } from "./speakers";

const TABS: { id: Route; label: string }[] = [
  { id: "console", label: "Console" },
  { id: "bounties", label: "Bounties" },
  { id: "archive", label: "Archive" },
];

export default function App() {
  const agents = useAgents();
  const run = useRun();
  const [route, setRoute] = useHashRoute();
  // The selected agent's color becomes the page accent.
  const agentColor = agents.selected ? speakerFor(agents.selected).color : undefined;

  return (
    <div className="app" style={agentColor ? ({ "--agent": agentColor } as CSSProperties) : undefined}>
      <header className="app__header">
        <h1>Endless Illusion</h1>
        <span className="subtitle">agent control plane · the Original Seven</span>
        <Tabs label="Sections" tabs={TABS} active={route} onChange={setRoute} />
      </header>

      {agents.error && <Banner>Could not load agents: {agents.error}. Is the server running on :8787?</Banner>}

      {route === "console" && <ConsolePage agents={agents} run={run} />}
      {route === "archive" && <ArchivePage agents={agents.agents} />}
      {route === "bounties" && <p className="empty">Bounties arrive in the next step.</p>}
    </div>
  );
}
