import type { ReactNode } from "react";

export default function EmptyState({ center = false, children }: { center?: boolean; children: ReactNode }) {
  return <div className={`empty ${center ? "empty--center" : ""}`}>{children}</div>;
}
