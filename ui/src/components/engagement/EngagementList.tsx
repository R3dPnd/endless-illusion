import { Button, EmptyState } from "pnd-lib-react";
import type { Engagement } from "../../types";

interface Props {
  engagements: Engagement[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
}

export default function EngagementList({ engagements, selectedId, onSelect, onNew }: Props) {
  return (
    <div className="eng-list">
      <Button variant="primary" onClick={onNew}>
        New engagement
      </Button>
      {engagements.length === 0 && <EmptyState>No engagements yet.</EmptyState>}
      <ul>
        {engagements.map((e) => (
          <li key={e.id}>
            <Button variant={e.id === selectedId ? "primary" : "ghost"} onClick={() => onSelect(e.id)}>
              {e.name} <span className="eng-kind">({e.kind})</span>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
