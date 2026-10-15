import type { Finding } from "../../types";
import SpeakerChip from "../chat/SpeakerChip";
import { EmptyState } from "../ui";
import SeverityChip from "./SeverityChip";

export default function FindingsTable({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) return <EmptyState>No findings recorded yet.</EmptyState>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Finding</th>
            <th>Status</th>
            <th>Agent</th>
            <th>Recorded</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => (
            <tr key={`${f.kind}-${f.id}`}>
              <td>
                <SeverityChip severity={f.severity} />
              </td>
              <td>
                <div className="cell-title">{f.title}</div>
                <div className="cell-sub">
                  {f.kind.toUpperCase()} · {f.target}
                </div>
              </td>
              <td className="cell-sub">{f.status.replace("_", " ")}</td>
              <td>
                <SpeakerChip id={f.agent} />
              </td>
              <td className="cell-sub">{f.created_at.slice(0, 10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
