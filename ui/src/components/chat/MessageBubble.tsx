import { useState, type CSSProperties } from "react";
import type { ChatMessage } from "../../chat";
import { speakerFor } from "../../speakers";
import { Avatar, Button } from "../ui";
import MessageHeader from "./MessageHeader";

const COLLAPSE_AT = 360;

export default function MessageBubble({ m }: { m: ChatMessage }) {
  const [open, setOpen] = useState(false);
  const from = speakerFor(m.from);
  const to = m.to ? speakerFor(m.to) : undefined;
  const mine = m.from === "operator";
  // Hand-off briefs can be long; collapse them so the conversation stays readable.
  const long = m.kind === "handoff" && m.text.length > COLLAPSE_AT;
  const text = long && !open ? m.text.slice(0, COLLAPSE_AT).trimEnd() + "…" : m.text;

  return (
    <div
      className={`msg msg--${m.kind} ${mine ? "msg--mine" : ""} ${m.isError ? "is-error" : ""}`}
      style={{ "--who": from.color, "--to": to?.color ?? from.color } as CSSProperties}
    >
      <Avatar speaker={from} />
      <div className="msg__body">
        <MessageHeader m={m} from={from} to={to} />
        <div className="bubble md">{text}</div>
        {long && (
          <Button variant="link" onClick={() => setOpen((o) => !o)}>
            {open ? "Show less" : "Show full brief"}
          </Button>
        )}
      </div>
    </div>
  );
}
