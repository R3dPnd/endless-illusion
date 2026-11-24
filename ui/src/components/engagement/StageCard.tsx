import { useState } from "react";
import { Banner, Button, Checkbox, StatusBadge, TextInput } from "pnd-lib-react";
import { skipStage, startStage, stopStage } from "../../api";
import { stageButtons } from "../../engagement";
import { useGuarded } from "../../hooks/useEngagement";
import type { StageView } from "../../types";

interface Props {
  engagementId: number;
  stage: StageView;
  /** Whether this stage's panel is the one open below. */
  selected: boolean;
  onOpen: () => void;
  onChanged: () => void;
}

export default function StageCard({ engagementId, stage, selected, onOpen, onChanged }: Props) {
  const buttons = stageButtons(stage);
  const [armed, setArmed] = useState(false);
  const [question, setQuestion] = useState("");
  const { error, busy, run } = useGuarded();
  const research = stage.stage === "research";

  async function act(fn: () => Promise<unknown>) {
    await run(fn);
    onChanged();
  }
  // Armed is only sent when the box is ticked and the stage can be armed.
  const start = () =>
    act(() => startStage(engagementId, stage.stage, { ...(armed ? { armed: true } : {}), ...(research ? { question: question.trim() } : {}) }));

  const canStart = buttons.includes("start") || buttons.includes("rerun");
  return (
    <div className={`stage-card stage-card--${stage.status} ${selected ? "stage-card--selected" : ""}`}>
      <div className="stage-card__head">
        <strong>{stage.stage}</strong>
        <span className="stage-card__agent">{stage.agent}</span>
        <StatusBadge status={stage.status} />
        {stage.armed && <span className="gate-warn">armed</span>}
        {stage.pending > 0 && <span className="gate-warn">{stage.pending} awaiting approval</span>}
      </div>
      {research && canStart && <TextInput label="Research question" value={question} onChange={setQuestion} placeholder="What is known about this stack?" />}
      {buttons.includes("arm") && (
        <Checkbox checked={armed} onChange={setArmed} disabled={busy}>
          Arm active tools
        </Checkbox>
      )}
      <div className="toolbar">
        {canStart && (
          <Button variant="primary" disabled={busy || (research && !question.trim())} onClick={() => void start()}>
            {buttons.includes("rerun") ? "Re-run" : "Start"}
          </Button>
        )}
        {buttons.includes("stop") && (
          <Button variant="danger" disabled={busy} onClick={() => void act(() => stopStage(engagementId, stage.stage))}>
            Stop
          </Button>
        )}
        {buttons.includes("skip") && (
          <Button variant="ghost" disabled={busy} onClick={() => void act(() => skipStage(engagementId, stage.stage))}>
            Skip
          </Button>
        )}
        {buttons.includes("open") && (
          <Button variant="ghost" onClick={onOpen}>
            Open
          </Button>
        )}
      </div>
      {error && <Banner tone="error">{error}</Banner>}
    </div>
  );
}
