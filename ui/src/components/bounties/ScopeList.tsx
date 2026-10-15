import type { ScopeItem } from "../../types";

export default function ScopeList({ title, items }: { title: string; items: (ScopeItem | string)[] }) {
  return (
    <div className="scope-list">
      <div className="scope-list__title">{title}</div>
      {items.length === 0 ? (
        <div className="cell-sub">none</div>
      ) : (
        <ul>
          {items.map((it, i) =>
            typeof it === "string" ? (
              <li key={i}>{it}</li>
            ) : (
              <li key={i}>
                <code>{it.asset}</code>
                {it.type && <span className="cell-sub"> {it.type}</span>}
                {it.notes && <span className="cell-sub"> — {it.notes}</span>}
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}
