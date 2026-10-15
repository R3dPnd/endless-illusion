import { useState } from "react";
import type { Program } from "../../types";
import { Button } from "../ui";
import ExternalLink from "./ExternalLink";
import ProposalReview from "./ProposalReview";

interface Props {
  program: Program;
  onAskSen: () => void;
  onConfirm: (proposalId: number) => void;
  onReject: (proposalId: number) => void;
}

export default function ProgramCard({ program, onAskSen, onConfirm, onReject }: Props) {
  const [reviewing, setReviewing] = useState(false);
  const proposal = program.proposals[0];
  return (
    <li className="card bounty-card">
      <div className="card__top">
        <span className="cell-title">{program.name}</span>
        {program.platform && <span className="chip">{program.platform}</span>}
        <span className="chip chip--muted">{program.source}</span>
      </div>
      <ExternalLink href={program.url} />
      <div className="card__actions">
        <Button variant="ghost" onClick={onAskSen}>
          Ask Sen for scope
        </Button>
        {proposal && (
          <Button variant="ghost" onClick={() => setReviewing((r) => !r)}>
            {reviewing ? "Hide proposal" : `Review proposal${program.proposals.length > 1 ? `s (${program.proposals.length})` : ""}`}
          </Button>
        )}
      </div>
      {reviewing && proposal && (
        <ProposalReview program={program} proposal={proposal} onConfirm={() => onConfirm(proposal.id)} onReject={() => onReject(proposal.id)} />
      )}
    </li>
  );
}
