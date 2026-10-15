import type { ChatMessage } from "../../chat";
import type { Speaker } from "../../speakers";
import { Timestamp } from "../ui";

const KIND_LABEL: Partial<Record<ChatMessage["kind"], string>> = {
  handoff: "hand-off",
  report: "report",
  final: "final response",
};

export default function MessageHeader({ m, from, to }: { m: ChatMessage; from: Speaker; to?: Speaker }) {
  const label = KIND_LABEL[m.kind];
  return (
    <div className="msg__head">
      <span className="who">{from.name}</span>
      {to && m.from !== "operator" && (
        <span className="to">
          → <b>{to.name}</b>
        </span>
      )}
      {label && <span className="kind">{label}</span>}
      {m.meta && <span className="t">{m.meta}</span>}
      <Timestamp ts={m.ts} />
    </div>
  );
}
