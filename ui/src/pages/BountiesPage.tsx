import AddProgramForm from "../components/bounties/AddProgramForm";
import BountyColumn from "../components/bounties/BountyColumn";
import ConfirmedCard from "../components/bounties/ConfirmedCard";
import LeadCard from "../components/bounties/LeadCard";
import ProgramCard from "../components/bounties/ProgramCard";
import { Banner, EmptyState, Panel } from "../components/ui";
import type { useBounties } from "../hooks/useBounties";
import type { Program } from "../types";

interface Props {
  bounties: ReturnType<typeof useBounties>;
  onAskSen: (program: Program) => void;
  onUseProgram: (programId: number) => void;
}

export default function BountiesPage({ bounties, onAskSen, onUseProgram }: Props) {
  const { data, error } = bounties;
  return (
    <Panel title="Bounties" className="panel--bounties">
      <div className="toolbar">
        <span className="cell-sub">Leads never authorize testing. Only scope you confirm here does.</span>
        <span className="push-right" />
        <AddProgramForm onAdd={bounties.addProgram} />
      </div>
      {error && <Banner>{error}</Banner>}
      {!data ? (
        <EmptyState>Loading…</EmptyState>
      ) : (
        <div className="bounty-board">
          <BountyColumn title="Discovered" hint="Leads recorded by Saudade and Dahlia" count={data.leads.length} tone="lead" empty="No new leads.">
            {data.leads.map((l) => (
              <LeadCard key={l.normalizedUrl} lead={l} onTrack={() => bounties.track(l.normalizedUrl)} onDismiss={() => bounties.dismiss(l.normalizedUrl)} />
            ))}
          </BountyColumn>
          <BountyColumn title="Tracked" hint="Sen proposes scope; you confirm it" count={data.tracked.length} tone="tracked" empty="Track a lead or add a program.">
            {data.tracked.map((p) => (
              <ProgramCard key={p.id} program={p} onAskSen={() => onAskSen(p)} onConfirm={bounties.confirm} onReject={bounties.reject} />
            ))}
          </BountyColumn>
          <BountyColumn title="Scope confirmed" hint="Usable as a run's authorization basis" count={data.confirmed.length} tone="confirmed" empty="No confirmed scope yet.">
            {data.confirmed.map((p) => (
              <ConfirmedCard key={p.id} program={p} onUse={() => onUseProgram(p.id)} />
            ))}
          </BountyColumn>
        </div>
      )}
    </Panel>
  );
}
