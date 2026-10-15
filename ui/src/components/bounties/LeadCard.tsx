import type { Lead } from "../../types";
import SpeakerChip from "../chat/SpeakerChip";
import { Button } from "../ui";
import ExternalLink from "./ExternalLink";

interface Props {
  lead: Lead;
  onTrack: () => void;
  onDismiss: () => void;
}

export default function LeadCard({ lead, onTrack, onDismiss }: Props) {
  return (
    <li className="card bounty-card">
      <div className="card__top">
        <span className="cell-title">{lead.name}</span>
        {lead.platform && <span className="chip">{lead.platform}</span>}
        <span className="chip chip--muted">
          {lead.sightings} sighting{lead.sightings === 1 ? "" : "s"}
        </span>
      </div>
      <ExternalLink href={lead.url} />
      <div className="bounty-card__found">
        found by {lead.agents.map((a) => <SpeakerChip key={a} id={a} />)}
      </div>
      <div className="cell-sub">via {lead.foundVia}</div>
      {lead.scopeSummary && (
        <p className="bounty-card__unverified">
          <span className="chip chip--active">unverified</span> {lead.scopeSummary}
        </p>
      )}
      <div className="card__actions">
        <Button variant="ghost" onClick={onTrack}>
          Track
        </Button>
        <Button variant="danger" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </li>
  );
}
