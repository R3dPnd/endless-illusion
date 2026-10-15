import type { ConfirmedProgram } from "../../types";
import { Button } from "../ui";
import ExternalLink from "./ExternalLink";
import ScopeList from "./ScopeList";

export default function ConfirmedCard({ program, onUse }: { program: ConfirmedProgram; onUse: () => void }) {
  const { snapshot } = program;
  return (
    <li className={`card bounty-card ${snapshot.stale ? "is-stale" : ""}`}>
      <div className="card__top">
        <span className="cell-title">{program.name}</span>
        {program.platform && <span className="chip">{program.platform}</span>}
        {snapshot.stale && <span className="chip chip--active">re-verify scope</span>}
      </div>
      <ExternalLink href={program.url} />
      <div className="cell-sub">
        snapshot #{snapshot.id} · confirmed {snapshot.confirmedAt.slice(0, 10)}
      </div>
      <ScopeList title="In scope" items={snapshot.inScope} />
      {snapshot.exclusions.length > 0 && <ScopeList title="Exclusions" items={snapshot.exclusions} />}
      <div className="card__actions">
        <Button variant="ghost" onClick={onUse}>
          Use in Trigger
        </Button>
      </div>
    </li>
  );
}
