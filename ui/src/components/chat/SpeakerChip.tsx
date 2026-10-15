import type { CSSProperties } from "react";
import { speakerFor } from "../../speakers";

/** An agent's name in its color, with an optional "working" pulse. */
export default function SpeakerChip({ id, active = false }: { id: string; active?: boolean }) {
  const s = speakerFor(id);
  return (
    <span
      className={`speaker-chip ${active ? "is-active" : ""}`}
      style={{ "--who": s.color } as CSSProperties}
      title={s.source}
    >
      <i className="dot" />
      {s.name}
    </span>
  );
}
