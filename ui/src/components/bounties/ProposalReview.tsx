import type { Program, Proposal } from "../../types";
import SpeakerChip from "../chat/SpeakerChip";
import { Button } from "../ui";
import ScopeList from "./ScopeList";

interface Props {
  program: Program;
  proposal: Proposal;
  onConfirm: () => void;
  onReject: () => void;
}

/** Sen's proposal beside the source policy. Confirming creates the authorization snapshot. */
export default function ProposalReview({ program, proposal, onConfirm, onReject }: Props) {
  const source = proposal.sourceExcerpt || program.policyText || "";
  return (
    <div className="proposal">
      <div className="proposal__head">
        Proposal #{proposal.id} by <SpeakerChip id={proposal.agent} />
        <span className="cell-sub">{proposal.createdAt.slice(0, 10)}</span>
      </div>
      <div className="proposal__grid">
        <div>
          <ScopeList title="In scope" items={proposal.inScope} />
          <ScopeList title="Out of scope" items={proposal.outOfScope} />
          <ScopeList title="Exclusions" items={proposal.exclusions} />
        </div>
        <div>
          <div className="scope-list__title">Source policy</div>
          <pre className="proposal__source">{source || "No policy text stored — check the program page before confirming."}</pre>
        </div>
      </div>
      <p className="gate-warn">Confirming makes this the authorization basis for runs linked to {program.name}.</p>
      <div className="card__actions">
        <Button variant="ghost" onClick={onConfirm}>
          Confirm scope
        </Button>
        <Button variant="danger" onClick={onReject}>
          Reject
        </Button>
      </div>
    </div>
  );
}
