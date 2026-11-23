import type { Lead } from "../../types";
import SpeakerChip from "../chat/SpeakerChip";
import { Button } from "pnd-lib-react";
import BoardFacts from "./BoardFacts";

interface Props {
  lead: Lead;
  onOpen: () => void;
  onTrack: () => void;
  onDismiss: () => void;
}

/** A discovered bounty. The whole card opens its details (and the Dann brief). */
export default function LeadCard({ lead, onOpen, onTrack, onDismiss }: Props) {
  return (
    <li className="card bounty-card is-clickable">
      <button type="button" className="bounty-card__open" onClick={onOpen} aria-label={`Open ${lead.name}`}>
        <div className="card__top">
          <span className="cell-title">{lead.name}</span>
          {lead.platform && <span className="chip">{lead.platform}</span>}
          {lead.sightings > 1 && <span className="chip tone--muted">{lead.sightings} sightings</span>}
        </div>
        <BoardFacts b={lead} />
        {lead.details && <p className="bounty-card__details">{lead.details}</p>}
        {lead.scopeSummary && (
          <p className="bounty-card__unverified">
            <span className="chip tone--orange">unverified</span> {lead.scopeSummary}
          </p>
        )}
      </button>
      <div className="bounty-card__found">
        found by {lead.agents.map((a) => <SpeakerChip key={a} id={a} />)}
      </div>
      <div className="card__actions">
        <Button variant="primary" onClick={onOpen}>
          Brief Dann
        </Button>
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
