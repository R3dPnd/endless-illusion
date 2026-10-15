import type { ChatMessage } from "../../chat";
import SpeakerChip from "./SpeakerChip";

/** Everyone who has spoken in the channel so far. */
export default function Roster({ messages, active }: { messages: ChatMessage[]; active?: string }) {
  const ids = Array.from(new Set(messages.map((m) => m.from).filter((id) => id !== "operator")));
  if (ids.length === 0) return <span className="chat__title">Agent channel</span>;
  return (
    <div className="roster">
      {ids.map((id) => (
        <SpeakerChip key={id} id={id} active={active === id} />
      ))}
    </div>
  );
}
