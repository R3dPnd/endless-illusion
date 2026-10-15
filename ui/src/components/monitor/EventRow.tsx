import type { RunEvent } from "../../types";
import { Chip } from "../ui";
import ClaudeRow from "./ClaudeRow";
import FeedRow from "./FeedRow";

export default function EventRow({ evt }: { evt: RunEvent }) {
  switch (evt.kind) {
    case "meta":
      return (
        <FeedRow ts={evt.ts} variant="meta">
          <div>
            <strong>Dispatched: {evt.agent}</strong>
            {evt.orchestrated && <Chip tone="orch">orchestrated</Chip>}
            {evt.activeEngaged ? <Chip tone="active">active tools</Chip> : <Chip tone="safe">passive tools</Chip>}
            <div className="tools">tools: {evt.tools.join(", ")}</div>
          </div>
        </FeedRow>
      );
    case "stderr":
    case "stdout":
      return (
        <FeedRow ts={evt.ts} variant={evt.kind}>
          <pre>{evt.text}</pre>
        </FeedRow>
      );
    case "error":
      return (
        <FeedRow ts={evt.ts} variant="error">
          <span>⚠ {evt.text}</span>
        </FeedRow>
      );
    case "closed":
      return (
        <FeedRow ts={evt.ts} variant="closed">
          <span>
            Process closed ({evt.status}, exit {String(evt.code)})
          </span>
        </FeedRow>
      );
    case "claude":
      return <ClaudeRow ts={evt.ts} data={evt.data} />;
  }
}
