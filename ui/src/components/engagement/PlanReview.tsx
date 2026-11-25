import { useState } from "react";
import { Banner, Button, EmptyState, Panel, TextField } from "pnd-lib-react";
import { approvePlan, revisePlan } from "../../api";
import { planIsApproved } from "../../engagement";
import { useGuarded } from "../../hooks/useEngagement";
import type { EngagementDetail } from "../../types";

interface Props {
  engagementId: number;
  plan: EngagementDetail["plan"];
  planError: string | null;
  onChanged: () => void;
}

/** The latest plan draft: per-stage include/targets/focus and research questions, with Approve and Revise. */
export default function PlanReview({ engagementId, plan, planError, onChanged }: Props) {
  const [comment, setComment] = useState("");
  const { error, busy, run } = useGuarded();
  const draft = plan.draft;
  const approved = planIsApproved(plan);

  async function act(fn: () => Promise<unknown>) {
    const ok = await run(fn);
    if (ok !== undefined) {
      setComment("");
      onChanged();
    }
  }

  return (
    <Panel title="Plan">
      {planError && <Banner tone="error">{planError}</Banner>}
      {!draft ? (
        <EmptyState>No plan draft yet. Run Planning once Discovery is done.</EmptyState>
      ) : (
        <>
          {approved && <p className="gate-ok">Approved.</p>}
          <ul className="plan">
            {Object.entries(draft.plan.stages ?? {}).map(([name, s]) => (
              <li key={name}>
                <strong>{name}</strong> {s?.include ? "included" : "excluded"}
                {s?.include && (
                  <>
                    <div>Targets: {(s.targets ?? []).join(", ") || "none"}</div>
                    <div>Focus: {s.focus ?? ""}</div>
                  </>
                )}
              </li>
            ))}
          </ul>
          {(draft.plan.research?.length ?? 0) > 0 && (
            <>
              <h4>Research questions</h4>
              <ul>
                {draft.plan.research!.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </>
          )}
          {!approved && (
            <>
              <TextField label="Revision comment" value={comment} onChange={setComment} rows={2} placeholder="What should change?" />
              <div className="toolbar">
                <Button variant="primary" disabled={busy} onClick={() => void act(() => approvePlan(engagementId, draft.id))}>
                  Approve plan
                </Button>
                <Button variant="ghost" disabled={busy || !comment.trim()} onClick={() => void act(() => revisePlan(engagementId, comment.trim()))}>
                  Revise
                </Button>
              </div>
            </>
          )}
        </>
      )}
      {error && <Banner tone="error">{error}</Banner>}
    </Panel>
  );
}
