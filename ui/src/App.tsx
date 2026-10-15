import { useState, type CSSProperties } from "react";
import { Banner, Tabs } from "./components/ui";
import { useAgents } from "./hooks/useAgents";
import { useBounties } from "./hooks/useBounties";
import { useHashRoute, type Route } from "./hooks/useHashRoute";
import { useRun } from "./hooks/useRun";
import ArchivePage from "./pages/ArchivePage";
import BountiesPage from "./pages/BountiesPage";
import ConsolePage from "./pages/ConsolePage";
import { speakerFor } from "./speakers";
import type { Program } from "./types";

const TABS: { id: Route; label: string }[] = [
  { id: "console", label: "Console" },
  { id: "bounties", label: "Bounties" },
  { id: "archive", label: "Archive" },
];

export default function App() {
  const agents = useAgents();
  const run = useRun();
  const [route, setRoute] = useHashRoute();
  const bounties = useBounties(run.busy);
  const [programId, setProgramId] = useState<number | null>(null);

  // Scope proposals are Sen's job: start a passive Sen run for the program.
  function askSen(p: Program) {
    agents.setSelected("sen-of-saturday");
    void run.start("sen-of-saturday", {
      task:
        `Propose structured scope for tracked program #${p.id} "${p.name}" (${p.url}). ` +
        `Read the program policy below (or its public page), then record it with propose_scope using program_id ${p.id}. ` +
        `This is scope validation only: do not contact or test any asset.` +
        (p.policyText ? `\n\nPolicy text provided by the operator:\n${p.policyText}` : ""),
      scope: p.url,
      authorization: "",
      enableActive: false,
    });
    setRoute("console");
  }

  function pickProgram(id: number) {
    setProgramId(id);
    setRoute("console");
  }
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

      {route === "console" && (
        <ConsolePage agents={agents} run={run} programs={bounties.data?.confirmed ?? []} programId={programId} onProgramChange={setProgramId} />
      )}
      {route === "archive" && <ArchivePage agents={agents.agents} />}
      {route === "bounties" && <BountiesPage bounties={bounties} onAskSen={askSen} onUseProgram={pickProgram} />}
    </div>
  );
}
