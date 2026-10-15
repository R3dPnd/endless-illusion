import type { CveNote } from "../../types";
import { EmptyState } from "../ui";

export default function CveNotesTable({ notes }: { notes: CveNote[] }) {
  if (notes.length === 0) return <EmptyState>No CVE notes recorded yet.</EmptyState>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>CVE</th>
            <th>Product</th>
            <th>Affected → fixed</th>
            <th>CVSS</th>
            <th>Flags</th>
            <th>Recorded</th>
          </tr>
        </thead>
        <tbody>
          {notes.map((n) => (
            <tr key={n.id}>
              <td className="cell-title">{n.cve_id}</td>
              <td>
                <div>{n.product}</div>
                <div className="cell-sub">{n.summary}</div>
              </td>
              <td className="cell-sub">
                {n.affected_versions}
                {n.fixed_version && ` → ${n.fixed_version}`}
              </td>
              <td className="cell-sub">{n.cvss ?? "—"}</td>
              <td>
                {n.kev && <span className="chip chip--active">KEV</span>}
                {n.public_exploit && <span className="chip chip--orch">public exploit</span>}
              </td>
              <td className="cell-sub">{n.created_at.slice(0, 10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
