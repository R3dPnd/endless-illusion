import type { CSSProperties } from "react";
import type { Speaker } from "../../speakers";

/** Colored initial for an agent (or the operator). */
export default function Avatar({ speaker }: { speaker: Speaker }) {
  return (
    <div className="avatar" title={speaker.source} style={{ "--who": speaker.color } as CSSProperties}>
      {speaker.name.charAt(0)}
    </div>
  );
}
