import type { ScopeItem } from "../../types";

/**
 * The hub normalizes scope to ScopeItem[] / string[], but this renders agent
 * data, so it stays defensive: any other shape shows as text instead of throwing.
 */
export default function ScopeList({ title, items }: { title: string; items: unknown }) {
  const list: unknown[] = Array.isArray(items) ? items : items == null ? [] : [items];
  return (
    <div className="scope-list">
      <div className="scope-list__title">{title}</div>
      {list.length === 0 ? (
        <div className="cell-sub">none</div>
      ) : (
        <ul>
          {list.map((it, i) => (
            <li key={i}>{isScopeItem(it) ? <Entry it={it} /> : asText(it)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Entry({ it }: { it: ScopeItem }) {
  return (
    <>
      <code>{it.asset}</code>
      {it.type && <span className="cell-sub"> {it.type}</span>}
      {it.notes && <span className="cell-sub"> — {it.notes}</span>}
    </>
  );
}

function isScopeItem(v: unknown): v is ScopeItem {
  return !!v && typeof v === "object" && typeof (v as ScopeItem).asset === "string";
}

function asText(v: unknown): string {
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}
