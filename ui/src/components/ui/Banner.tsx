import type { ReactNode } from "react";

export default function Banner({ tone = "error", children }: { tone?: "error"; children: ReactNode }) {
  return <div className={`banner banner--${tone}`}>{children}</div>;
}
