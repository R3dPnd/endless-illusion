import type { ReactNode } from "react";
import { EmptyState } from "../ui";

interface Props {
  title: string;
  hint: string;
  count: number;
  tone: "lead" | "tracked" | "confirmed";
  empty: string;
  children: ReactNode;
}

export default function BountyColumn({ title, hint, count, tone, empty, children }: Props) {
  return (
    <section className={`bounty-col bounty-col--${tone}`}>
      <header className="bounty-col__head">
        <h3>
          {title} <span className="tab__count">{count}</span>
        </h3>
        <p className="cell-sub">{hint}</p>
      </header>
      {count === 0 ? <EmptyState>{empty}</EmptyState> : <ul className="bounty-col__list">{children}</ul>}
    </section>
  );
}
