import type { ReactNode } from "react";
import { Timestamp } from "../ui";

/** One timestamped line in the monitor feed. */
export default function FeedRow({ ts, variant, children }: { ts: number; variant?: string; children: ReactNode }) {
  return (
    <div className={`row ${variant ? `row--${variant}` : ""}`}>
      <Timestamp ts={ts} />
      {children}
    </div>
  );
}
