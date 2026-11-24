import { useState } from "react";
import { Banner, Button, TextInput } from "pnd-lib-react";
import { askQuestion } from "../../api";
import { useGuarded } from "../../hooks/useEngagement";
import type { EngagementQuestion } from "../../types";

/** Questions and answers; an answer is null until the agent fork finishes. */
export function QuestionList({ questions }: { questions: EngagementQuestion[] }) {
  if (questions.length === 0) return null;
  return (
    <ul className="qthread">
      {questions.map((q) => (
        <li key={q.id}>
          <p className="qthread__q">
            {q.kind === "explain" ? `Explain: ${q.technique ?? q.question}` : `Q: ${q.question}`}
          </p>
          <p className="qthread__a">{q.answer ?? "waiting for the agent…"}</p>
        </li>
      ))}
    </ul>
  );
}

interface AskProps {
  engagementId: number;
  stage: string;
  actionId?: number;
  onAsked: () => void;
}

/** A one-line question box that posts to the agent's fork (the stage and any pending action stay as they are). */
export function AskBox({ engagementId, stage, actionId, onAsked }: AskProps) {
  const [text, setText] = useState("");
  const { error, busy, run } = useGuarded();
  async function send() {
    const q = text.trim();
    if (!q) return;
    const res = await run(() => askQuestion(engagementId, { stage, question: q, ...(actionId != null ? { actionId } : {}) }));
    if (res) {
      setText("");
      onAsked();
    }
  }
  return (
    <div className="askbox">
      <TextInput label="Ask the agent" value={text} onChange={setText} />
      <Button variant="ghost" disabled={busy || !text.trim()} onClick={() => void send()}>
        Send
      </Button>
      {error && <Banner tone="error">{error}</Banner>}
    </div>
  );
}
