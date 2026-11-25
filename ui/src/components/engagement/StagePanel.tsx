import { useState } from "react";
import { Banner, Button, Panel } from "pnd-lib-react";
import { stopStage } from "../../api";
import { useGuarded, useRunFeed } from "../../hooks/useEngagement";
import RunMonitor from "../monitor/RunMonitor";
import type { EngagementQuestion, StageView } from "../../types";
import { AskBox, QuestionList } from "./QuestionThread";

interface Props {
  engagementId: number;
  stage: StageView;
  questions: EngagementQuestion[];
  onClose: () => void;
  onChanged: () => void;
}

/** One stage's live feed (any run in its history), its questions, and a general Ask. */
export default function StagePanel({ engagementId, stage, questions, onClose, onChanged }: Props) {
  const [picked, setPicked] = useState<string | null>(null);
  const runId = picked && stage.history.includes(picked) ? picked : stage.runId;
  const { events, closed } = useRunFeed(runId);
  const { error, run } = useGuarded();
  const live = stage.status === "running" || stage.status === "awaiting-approval";
  const status = closed ?? (runId === stage.runId && live ? "running" : "done");

  return (
    <Panel title={`${stage.stage} · ${stage.agent}`}>
      <div className="toolbar">
        {stage.history.length > 1 && (
          <select aria-label="Run" value={runId ?? ""} onChange={(e) => setPicked(e.target.value)}>
            {stage.history.map((id, i) => (
              <option key={id} value={id}>
                run {i + 1}
              </option>
            ))}
          </select>
        )}
        <Button variant="ghost" className="push-right" onClick={onClose}>
          Close
        </Button>
      </div>
      <RunMonitor
        events={events}
        status={status}
        onStop={() => {
          void run(() => stopStage(engagementId, stage.stage)).then(onChanged);
        }}
      />
      {error && <Banner tone="error">{error}</Banner>}
      <QuestionList questions={questions.filter((q) => q.stage === stage.stage && q.action_id == null)} />
      {live && <AskBox engagementId={engagementId} stage={stage.stage} onAsked={onChanged} />}
    </Panel>
  );
}
