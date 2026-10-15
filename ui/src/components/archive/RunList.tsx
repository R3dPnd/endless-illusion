import type { RunSummary } from "../../types";
import { fmtTime } from "../../util";
import SpeakerChip from "../chat/SpeakerChip";
import { EmptyState, StatusBadge } from "../ui";

interface Props {
  runs: RunSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
}

const fmtDate = (iso: string) => `${new Date(iso).toLocaleDateString()} ${fmtTime(Date.parse(iso))}`;

export default function RunList({ runs, selected, onSelect }: Props) {
  if (runs.length === 0) return <EmptyState>No runs match.</EmptyState>;
  return (
    <ul className="run-list">
      {runs.map((r) => (
        <li key={r.id}>
          <button type="button" className={`run-row ${selected === r.id ? "is-selected" : ""}`} onClick={() => onSelect(r.id)}>
            <span className="run-row__top">
              <SpeakerChip id={r.agent} />
              <StatusBadge status={r.status} />
              {r.active_engaged && <span className="chip chip--active">active</span>}
              {r.program_id != null && <span className="chip chip--orch">program #{r.program_id}</span>}
            </span>
            <span className="run-row__task">{r.task}</span>
            <span className="run-row__meta">
              {fmtDate(r.started_at)}
              {r.cost_usd != null && ` · $${r.cost_usd.toFixed(4)}`}
              {r.duration_ms != null && ` · ${(r.duration_ms / 1000).toFixed(0)}s`}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
