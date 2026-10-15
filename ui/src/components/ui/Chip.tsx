import type { ReactNode } from "react";

export type Tone = "tool" | "task" | "active" | "safe" | "orch" | "muted" | "plain";

/** Small inline label used in feeds and stats. */
export function Chip({ tone = "plain", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <span className={`chip chip--${tone}`} title={title}>
      {children}
    </span>
  );
}

/** Outlined pill used for classifications on cards. */
export function Tag({ tone = "muted", children }: { tone?: string; children: ReactNode }) {
  return <span className={`tag tag--${tone}`}>{children}</span>;
}
