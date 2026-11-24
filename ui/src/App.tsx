import { useState, type CSSProperties } from "react";
import { Banner, DisplaySettings, Tabs, useDisplay, useHashRoute } from "pnd-lib-react";
import { displayHost } from "./displayHost";
import { useAgents } from "./hooks/useAgents";
import { useBounties } from "./hooks/useBounties";
import { useRun } from "./hooks/useRun";
import ErrorBoundary from "./components/ErrorBoundary";
import ArchivePage from "./pages/ArchivePage";
import BountiesPage from "./pages/BountiesPage";
import ConsolePage from "./pages/ConsolePage";
import EngagementsPage from "./pages/EngagementsPage";
import { usePendingCount } from "./hooks/useEngagement";
import { scoutTask, type DannSession } from "./bounties";
import { speakerFor } from "./speakers";
import type { Program } from "./types";

const ROUTES = ["engagements", "console", "bounties", "archive"] as const;
type Route = (typeof ROUTES)[number];

const BASE_TABS: { id: Route; label: string; count?: number }[] = [
  { id: "engagements", label: "Engagements" },
  { id: "console", label: "Console" },
  { id: "bounties", label: "Bounties" },
  { id: "archive", label: "Archive" },
];

export default function App() {
  const display = useDisplay(displayHost);
  const agents = useAgents();
  const run = useRun();
  const [route, setRoute] = useHashRoute(ROUTES);
  const bounties = useBounties(run.busy);
  const [programId, setProgramId] = useState<number | null>(null);
  const pendingApprovals = usePendingCount();
  // The badge is the number of gated actions waiting on the operator, across engagements.
  const TABS = BASE_TABS.map((t) => (t.id === "engagements" && pendingApprovals > 0 ? { ...t, count: pendingApprovals } : t));

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

  // Bounty board: open a session with Dann about a bounty. It joins the Console
  // conversation; active tooling is never armed from here.
  function startDann(s: DannSession) {
    agents.setSelected("dann-of-thursday");
    if (s.programId !== undefined) setProgramId(s.programId);
    void run.start("dann-of-thursday", {
      task: s.task,
      scope: s.scope,
      authorization: s.authorization,
      enableActive: false,
      ...(s.programId !== undefined ? { programId: s.programId } : {}),
    });
    setRoute("console");
  }

  // Bounty board: Saudade scouts public directories with the bounty-scout skill.
  // Stay on the board; it polls while the run is active, so cards appear as they're recorded.
  function scout(focus: string) {
    agents.setSelected("saudade-of-sunday");
    void run.start("saudade-of-sunday", {
      task: scoutTask(focus),
      scope: "Public bug bounty directories and program/policy pages only (passive). No program assets.",
      authorization: "",
      enableActive: false,
    });
  }

  function pickProgram(id: number) {
    setProgramId(id);
    setRoute("console");
  }
  // The selected agent's color becomes the page accent.
  const agentColor = agents.selected ? speakerFor(agents.selected).color : undefined;

  return (
    <div className={`app app--${route}`} style={agentColor ? ({ "--accent": agentColor } as CSSProperties) : undefined}>
      <header className="app__header">
        <h1>Endless Illusion</h1>
        <span className="subtitle">agent control plane · the Original Seven</span>
        <Tabs label="Sections" tabs={TABS} active={route} onChange={setRoute} />
        <DisplaySettings d={display} />
      </header>

      {agents.error && <Banner>Could not load agents: {agents.error}. Is the server running on :8787?</Banner>}

      <ErrorBoundary key={route} area={TABS.find((t) => t.id === route)?.label ?? "This tab"}>
        {route === "engagements" && <EngagementsPage programs={bounties.data?.confirmed ?? []} />}
        {route === "console" && (
          <ConsolePage agents={agents} run={run} programs={bounties.data?.confirmed ?? []} programId={programId} onProgramChange={setProgramId} />
        )}
        {route === "archive" && <ArchivePage agents={agents.agents} />}
        {route === "bounties" && (
          <BountiesPage bounties={bounties} busy={run.busy} onAskSen={askSen} onUseProgram={pickProgram} onStartDann={startDann} onScout={scout} />
        )}
      </ErrorBoundary>
    </div>
  );
}
