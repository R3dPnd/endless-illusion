import { useState } from "react";
import AddProgramForm from "../components/bounties/AddProgramForm";
import BountyColumn from "../components/bounties/BountyColumn";
import BountyDetail from "../components/bounties/BountyDetail";
import ConfirmedCard from "../components/bounties/ConfirmedCard";
import LeadCard from "../components/bounties/LeadCard";
import ProgramCard from "../components/bounties/ProgramCard";
import { Banner, Button, EmptyState, Panel, Select } from "pnd-lib-react";
import type { BoardItem, DannSession } from "../bounties";
import type { useBounties } from "../hooks/useBounties";
import type { Lead, Program } from "../types";

interface Props {
  bounties: ReturnType<typeof useBounties>;
  /** A run is in progress (scouting, or anything else). */
  busy: boolean;
  onAskSen: (program: Program) => void;
  onUseProgram: (programId: number) => void;
  onStartDann: (session: DannSession) => void;
  onScout: (focus: string) => void;
}

type Sort = "newest" | "reward";

const byReward = (a: Lead, b: Lead) => (b.maxRewardUsd ?? -1) - (a.maxRewardUsd ?? -1);

export default function BountiesPage({ bounties, busy, onAskSen, onUseProgram, onStartDann, onScout }: Props) {
  const { data, error } = bounties;
  const [open, setOpen] = useState<BoardItem | null>(null);
  const [focus, setFocus] = useState("");
  const [sort, setSort] = useState<Sort>("newest");

  // Re-resolve the open item from fresh data so polling updates the dialog (and closes it if the item moved on).
  const current = open && data ? resolve(open, data) : null;
  const leads = data ? (sort === "reward" ? [...data.leads].sort(byReward) : data.leads) : [];

  return (
    <Panel title="Bounties" className="panel--bounties">
      <form
        className="scout-bar"
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy) onScout(focus);
        }}
      >
        <input
          className="scout-bar__input"
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
          placeholder="Optional focus — e.g. fintech APIs, Web3 over $50k, programs updated this month"
          aria-label="Scouting focus"
        />
        <Button type="submit" variant="primary" disabled={busy}>
          {busy ? "Agents working…" : "Scout bounties"}
        </Button>
        <span className="cell-sub">Saudade searches public program directories with the bounty-scout skill and fills the board.</span>
      </form>

      <div className="toolbar">
        <span className="cell-sub">Leads never authorize testing. Only scope you confirm here does.</span>
        <span className="push-right" />
        <Select
          label="Sort leads"
          value={sort}
          onChange={(v) => setSort(v as Sort)}
          options={[
            { value: "newest", label: "Newest" },
            { value: "reward", label: "Top reward" },
          ]}
        />
        <AddProgramForm onAdd={bounties.addProgram} />
      </div>
      {error && <Banner>{error}</Banner>}
      {!data ? (
        <EmptyState>Loading…</EmptyState>
      ) : (
        <div className="bounty-board">
          <BountyColumn title="Discovered" hint="Found by Saudade and Dahlia — click one for details" count={leads.length} tone="lead" empty="No new leads. Scout bounties to fill the board.">
            {leads.map((l) => (
              <LeadCard
                key={l.normalizedUrl}
                lead={l}
                onOpen={() => setOpen({ stage: "lead", key: `lead:${l.normalizedUrl}`, bounty: l })}
                onTrack={() => bounties.track(l.normalizedUrl)}
                onDismiss={() => bounties.dismiss(l.normalizedUrl)}
              />
            ))}
          </BountyColumn>
          <BountyColumn title="Tracked" hint="Sen proposes scope; you confirm it" count={data.tracked.length} tone="tracked" empty="Track a lead or add a program.">
            {data.tracked.map((p) => (
              <ProgramCard
                key={p.id}
                program={p}
                onOpen={() => setOpen({ stage: "tracked", key: `program:${p.id}`, bounty: p })}
                onAskSen={() => onAskSen(p)}
                onConfirm={bounties.confirm}
                onReject={bounties.reject}
              />
            ))}
          </BountyColumn>
          <BountyColumn title="Scope confirmed" hint="Usable as a run's authorization basis" count={data.confirmed.length} tone="confirmed" empty="No confirmed scope yet.">
            {data.confirmed.map((p) => (
              <ConfirmedCard
                key={p.id}
                program={p}
                onOpen={() => setOpen({ stage: "confirmed", key: `program:${p.id}`, bounty: p })}
                onUse={() => onUseProgram(p.id)}
              />
            ))}
          </BountyColumn>
        </div>
      )}

      {current && (
        <BountyDetail
          key={current.key}
          item={current}
          busy={busy}
          onClose={() => setOpen(null)}
          onStartDann={(s) => {
            setOpen(null);
            onStartDann(s);
          }}
          onTrack={current.stage === "lead" ? () => void bounties.track(current.bounty.normalizedUrl).then(() => setOpen(null)) : undefined}
          onDismiss={current.stage === "lead" ? () => void bounties.dismiss(current.bounty.normalizedUrl).then(() => setOpen(null)) : undefined}
        />
      )}
    </Panel>
  );
}

/** The same bounty in the latest data, following it from lead to tracked to confirmed. */
function resolve(item: BoardItem, data: NonNullable<ReturnType<typeof useBounties>["data"]>): BoardItem | null {
  const url = item.bounty.normalizedUrl;
  const lead = data.leads.find((l) => l.normalizedUrl === url);
  if (lead) return { stage: "lead", key: `lead:${url}`, bounty: lead };
  const confirmed = data.confirmed.find((p) => p.normalizedUrl === url);
  if (confirmed) return { stage: "confirmed", key: `program:${confirmed.id}`, bounty: confirmed };
  const tracked = data.tracked.find((p) => p.normalizedUrl === url);
  if (tracked) return { stage: "tracked", key: `program:${tracked.id}`, bounty: tracked };
  return null;
}
