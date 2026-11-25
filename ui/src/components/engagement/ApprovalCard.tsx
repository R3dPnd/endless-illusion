import { useState } from "react";
import { Banner, Button, Checkbox, TextInput } from "pnd-lib-react";
import { askQuestion, decideAction } from "../../api";
import { approveNeedsAck, cardButtons, verdictLabel } from "../../engagement";
import { useGuarded } from "../../hooks/useEngagement";
import { speakerFor } from "../../speakers";
import type { EngagementQuestion, GateAction } from "../../types";
import { AskBox, QuestionList } from "./QuestionThread";

interface Props {
  action: GateAction;
  agent: string;
  questions: EngagementQuestion[];
  engagementId: number;
  onChanged: () => void;
}

export default function ApprovalCard({ action, agent, questions, engagementId, onChanged }: Props) {
  const buttons = cardButtons(action);
  const needsAck = approveNeedsAck(action);
  const [ack, setAck] = useState(false);
  const [mode, setMode] = useState<"deny" | "ask" | null>(null);
  const [reason, setReason] = useState("");
  const { error, busy, run } = useGuarded();
  const mine = questions.filter((q) => q.action_id === action.id);

  async function decide(approve: boolean, message?: string) {
    // Booleans go as real JSON booleans; scopeAck is only sent when the tick is needed and given.
    const ok = await run(() =>
      decideAction(action.id, {
        approve,
        ...(message ? { message } : {}),
        ...(approve && needsAck && ack ? { scopeAck: true } : {}),
      })
    );
    if (ok !== undefined) onChanged();
  }

  const explain = () => {
    void run(() =>
      askQuestion(engagementId, { stage: action.stage, actionId: action.id, kind: "explain", technique: action.technique, question: `Explain ${action.technique}` })
    ).then(onChanged);
  };

  return (
    <div className={`approval-card approval-card--${action.verdict}`}>
      <div className="approval-card__head">
        <strong style={{ color: speakerFor(agent).color }}>{agent}</strong> wants to run <span className="stage-card__agent">({action.stage})</span>
        <span className="push-right gate-warn">waiting</span>
      </div>
      <pre className="approval-card__cmd">
        {action.tool_name === "Bash" ? "$ " : `${action.tool_name} `}
        {action.target}
      </pre>
      <dl className="approval-card__facts">
        <dt>Why (agent)</dt>
        <dd>{action.why}</dd>
        <dt>Technique</dt>
        <dd>
          {action.technique}{" "}
          <Button variant="link" disabled={busy} onClick={explain}>
            [explain]
          </Button>
        </dd>
        <dt>Target</dt>
        <dd className={action.verdict === "in" ? "" : "gate-warn"}>
          {action.hosts.join(", ")} {verdictLabel(action.verdict)}
        </dd>
        <dt>Risk</dt>
        <dd>{action.risk}</dd>
      </dl>

      {buttons.includes("approve") && needsAck && (
        <Checkbox checked={ack} onChange={setAck}>
          I've checked this host is in scope
        </Checkbox>
      )}
      <div className="toolbar">
        {buttons.includes("approve") && (
          <Button variant="primary" disabled={busy || (needsAck && !ack)} onClick={() => void decide(true)}>
            Approve
          </Button>
        )}
        {buttons.includes("deny") && (
          <Button variant="danger" disabled={busy} onClick={() => void decide(false)}>
            Deny
          </Button>
        )}
        {buttons.includes("denyWithReason") && (
          <Button variant="ghost" disabled={busy} onClick={() => setMode(mode === "deny" ? null : "deny")}>
            Deny + tell agent why
          </Button>
        )}
        {buttons.includes("ask") && (
          <Button variant="ghost" disabled={busy} onClick={() => setMode(mode === "ask" ? null : "ask")}>
            Ask a question
          </Button>
        )}
      </div>

      {mode === "deny" && (
        <div className="askbox">
          <TextInput label="Tell the agent why" value={reason} onChange={setReason} />
          <Button variant="danger" disabled={busy || !reason.trim()} onClick={() => void decide(false, reason.trim())}>
            Deny with reason
          </Button>
        </div>
      )}
      {mode === "ask" && <AskBox engagementId={engagementId} stage={action.stage} actionId={action.id} onAsked={onChanged} />}
      <QuestionList questions={mine} />
      {error && <Banner tone="error">{error}</Banner>}
    </div>
  );
}
