import type { CSSProperties } from "react";
import { speakerFor } from "../../speakers";

export default function TypingIndicator({ id }: { id: string }) {
  const s = speakerFor(id);
  return (
    <div className="typing" style={{ "--who": s.color } as CSSProperties}>
      <span className="who">{s.name}</span> is working
      <span className="typing__dots">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}
