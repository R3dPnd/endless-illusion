import type { ClaudeEvent } from "../../types";
import { Chip } from "../ui";
import FeedRow from "./FeedRow";

/** Run summary; the response text itself lives in the Channel. */
export default function FinalRow({ ts, data }: { ts: number; data: ClaudeEvent }) {
  const spawned = data.subagent_stats?.spawned ?? 0;
  const byType = data.subagent_stats?.by_type ?? {};
  return (
    <FeedRow ts={ts} variant={`final ${data.is_error ? "is-error" : ""}`}>
      <div className="final-card">
        <strong>{data.is_error ? "Finished with error" : "Final result"}</strong>
        <div className="final-pointer">Full response is in the Channel above.</div>
        <div className="final-stats">
          {typeof data.total_cost_usd === "number" && <span>cost ${data.total_cost_usd.toFixed(4)}</span>}
          {typeof data.duration_ms === "number" && <span>{(data.duration_ms / 1000).toFixed(1)}s</span>}
          {typeof data.num_turns === "number" && <span>{data.num_turns} turns</span>}
          <span>subagents: {spawned}</span>
          {Object.entries(byType).map(([k, v]) => (
            <Chip key={k} tone="orch">
              {k}×{v}
            </Chip>
          ))}
        </div>
      </div>
    </FeedRow>
  );
}
