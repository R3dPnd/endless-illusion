import { exportSubmissionUrl } from "../../api";
import type { Submission } from "../../types";
import { EmptyState } from "../ui";
import SeverityChip from "./SeverityChip";

export default function SubmissionsList({ submissions }: { submissions: Submission[] }) {
  if (submissions.length === 0) return <EmptyState>No submission drafts yet.</EmptyState>;
  return (
    <ul className="card-list">
      {submissions.map((s) => (
        <li key={s.id} className="card">
          <div className="card__top">
            <SeverityChip severity={s.severity} />
            <span className="cell-title">{s.title}</span>
          </div>
          <div className="cell-sub">
            {s.program_name} · drafted {s.created_at.slice(0, 10)}
          </div>
          <a className="btn btn--ghost card__action" href={exportSubmissionUrl(s.id)} download>
            Export markdown
          </a>
        </li>
      ))}
    </ul>
  );
}
