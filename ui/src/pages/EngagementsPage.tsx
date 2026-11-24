import { useState } from "react";
import { Banner, EmptyState, Panel } from "pnd-lib-react";
import ApprovalCard from "../components/engagement/ApprovalCard";
import EngagementList from "../components/engagement/EngagementList";
import NewEngagementForm from "../components/engagement/NewEngagementForm";
import PlanReview from "../components/engagement/PlanReview";
import StageCard from "../components/engagement/StageCard";
import StagePanel from "../components/engagement/StagePanel";
import { useEngagement, useEngagementList } from "../hooks/useEngagement";
import type { ConfirmedProgram, StageName } from "../types";

interface Props {
  programs: ConfirmedProgram[];
}

export default function EngagementsPage({ programs }: Props) {
  const { list, error: listError, refresh: refreshList } = useEngagementList();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<StageName | null>(null);
  const { detail, error, refresh } = useEngagement(selectedId);

  const agentOf = (stage: StageName) => detail?.stages.find((s) => s.stage === stage)?.agent ?? stage;
  const pending = [...(detail?.pending ?? [])].sort((a, b) => a.id - b.id); // oldest first
  const planError = detail?.stages.find((s) => s.planError)?.planError ?? null;
  const lane = detail?.stages.filter((s) => s.stage !== "research") ?? [];
  const research = detail?.stages.find((s) => s.stage === "research");
  const openStage = detail?.stages.find((s) => s.stage === open);

  return (
    <div className="engagements">
      <Panel title="Engagements" className="panel--eng-list">
        <EngagementList
          engagements={list}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            setCreating(false);
            setOpen(null);
          }}
          onNew={() => setCreating(true)}
        />
        {listError && <Banner tone="error">{listError}</Banner>}
      </Panel>

      <div className="engagements__main">
        {creating ? (
          <Panel title="New engagement">
            <NewEngagementForm
              programs={programs}
              onCancel={() => setCreating(false)}
              onCreated={(e) => {
                setCreating(false);
                setSelectedId(e.id);
                void refreshList();
              }}
            />
          </Panel>
        ) : !detail ? (
          error ? <Banner tone="error">{error}</Banner> : <EmptyState>{selectedId == null ? "Pick or create an engagement." : "Loading…"}</EmptyState>
        ) : (
          <>
            {error && <Banner tone="error">{error}</Banner>}
            {pending.length > 0 && (
              <Panel title={`Pending approvals (${pending.length})`}>
                {pending.map((a) => (
                  <ApprovalCard
                    key={a.id}
                    action={a}
                    agent={agentOf(a.stage)}
                    questions={detail.questions}
                    engagementId={detail.engagement.id}
                    onChanged={() => void refresh()}
                  />
                ))}
              </Panel>
            )}
            <Panel title={detail.engagement.name}>
              <div className="stage-grid">
                {lane.map((s) => (
                  <StageCard
                    key={s.stage}
                    engagementId={detail.engagement.id}
                    stage={s}
                    selected={open === s.stage}
                    onOpen={() => setOpen(s.stage)}
                    onChanged={() => void refresh()}
                  />
                ))}
              </div>
              {research && (
                <div className="research-lane">
                  <StageCard
                    engagementId={detail.engagement.id}
                    stage={research}
                    selected={open === "research"}
                    onOpen={() => setOpen("research")}
                    onChanged={() => void refresh()}
                  />
                </div>
              )}
            </Panel>
            <PlanReview engagementId={detail.engagement.id} plan={detail.plan} planError={planError} onChanged={() => void refresh()} />
            {openStage && (
              <StagePanel
                engagementId={detail.engagement.id}
                stage={openStage}
                questions={detail.questions}
                onClose={() => setOpen(null)}
                onChanged={() => void refresh()}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
