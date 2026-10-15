import type { RunEvent } from "../../types";
import { Button, EmptyState, StatusBadge } from "../ui";
import EventRow from "./EventRow";

interface Props {
  events: RunEvent[];
  status: string;
  onStop: () => void;
}

export default function RunMonitor({ events, status, onStop }: Props) {
  if (events.length === 0) {
    return <EmptyState>No run yet. Trigger an agent to watch it work.</EmptyState>;
  }
  return (
    <div className="monitor">
      <div className="toolbar">
        <StatusBadge status={status} />
        {status === "running" && (
          <Button variant="danger" className="push-right" onClick={onStop}>
            Stop
          </Button>
        )}
      </div>
      <div className="feed">
        {events.map((evt, i) => (
          <EventRow key={i} evt={evt} />
        ))}
      </div>
    </div>
  );
}
