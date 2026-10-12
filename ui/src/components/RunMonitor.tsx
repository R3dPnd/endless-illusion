import type { RunEvent, ClaudeEvent } from "../types";
import { fmtTime } from "../util";

interface Props {
  events: RunEvent[];
  status: string;
  onStop: () => void;
}

export default function RunMonitor({ events, status, onStop }: Props) {
  if (events.length === 0) {
    return <div className="monitor-empty">No run yet. Trigger an agent to watch it work.</div>;
  }
  return (
    <div className="monitor">
      <div className="monitor__bar">
        <span className={`status status--${status}`}>{status}</span>
        {status === "running" && (
          <button className="btn-stop" onClick={onStop}>
            Stop
          </button>
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

function EventRow({ evt }: { evt: RunEvent }) {
  const time = fmtTime(evt.ts);

  if (evt.kind === "meta") {
    return (
      <div className="row row--meta">
        <span className="t">{time}</span>
        <div>
          <strong>Dispatched: {evt.agent}</strong>
          {evt.orchestrated && <span className="chip chip--orch">orchestrated</span>}
          {evt.activeEngaged ? (
            <span className="chip chip--active">active tools</span>
          ) : (
            <span className="chip chip--safe">passive tools</span>
          )}
          <div className="tools">tools: {evt.tools.join(", ")}</div>
        </div>
      </div>
    );
  }

  if (evt.kind === "stderr") {
    return (
      <div className="row row--stderr">
        <span className="t">{time}</span>
        <pre>{evt.text}</pre>
      </div>
    );
  }

  if (evt.kind === "error") {
    return (
      <div className="row row--error">
        <span className="t">{time}</span>
        <span>⚠ {evt.text}</span>
      </div>
    );
  }

  if (evt.kind === "stdout") {
    return (
      <div className="row row--stdout">
        <span className="t">{time}</span>
        <pre>{evt.text}</pre>
      </div>
    );
  }

  if (evt.kind === "closed") {
    return (
      <div className="row row--closed">
        <span className="t">{time}</span>
        <span>Process closed ({evt.status}, exit {String(evt.code)})</span>
      </div>
    );
  }

  // kind === "claude"
  return <ClaudeRow data={evt.data} time={time} />;
}

function ClaudeRow({ data, time }: { data: ClaudeEvent; time: string }) {
  if (data.type === "system" && data.subtype === "init") {
    return (
      <div className="row row--init">
        <span className="t">{time}</span>
        <div>
          <strong>Session initialized</strong>
          {data.model && <span className="chip">{String(data.model)}</span>}
          {Array.isArray(data.tools) && (
            <div className="tools">allowed: {data.tools.join(", ")}</div>
          )}
        </div>
      </div>
    );
  }

  if (data.type === "assistant" && data.message?.content) {
    return (
      <>
        {data.message.content.map((block, i) => {
          if (block.type === "text") {
            return (
              <div className="row row--text" key={i}>
                <span className="t">{time}</span>
                <div className="md">{(block as { text: string }).text}</div>
              </div>
            );
          }
          if (block.type === "tool_use") {
            const b = block as { name: string; input?: unknown };
            const isTask = b.name === "Task";
            return (
              <div className={`row row--tool ${isTask ? "row--task" : ""}`} key={i}>
                <span className="t">{time}</span>
                <div>
                  <span className={`chip ${isTask ? "chip--task" : "chip--tool"}`}>
                    {isTask ? "→ delegate" : b.name}
                  </span>
                  <ToolInput name={b.name} input={b.input} />
                </div>
              </div>
            );
          }
          return null;
        })}
      </>
    );
  }

  if (data.type === "user" && data.message?.content) {
    const hasResult = data.message.content.some((b) => b.type === "tool_result");
    if (hasResult) {
      return (
        <div className="row row--result-in">
          <span className="t">{time}</span>
          <span className="chip chip--muted">tool result</span>
        </div>
      );
    }
  }

  if (data.type === "result") {
    const spawned = data.subagent_stats?.spawned ?? 0;
    const byType = data.subagent_stats?.by_type ?? {};
    return (
      <div className={`row row--final ${data.is_error ? "is-error" : ""}`}>
        <span className="t">{time}</span>
        <div className="final-card">
          <strong>{data.is_error ? "Finished with error" : "Final result"}</strong>
          <div className="md">{data.result}</div>
          <div className="final-stats">
            {typeof data.total_cost_usd === "number" && (
              <span>cost ${data.total_cost_usd.toFixed(4)}</span>
            )}
            {typeof data.duration_ms === "number" && (
              <span>{(data.duration_ms / 1000).toFixed(1)}s</span>
            )}
            {typeof data.num_turns === "number" && <span>{data.num_turns} turns</span>}
            <span>subagents: {spawned}</span>
            {Object.entries(byType).map(([k, v]) => (
              <span key={k} className="chip chip--orch">{k}×{v}</span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function ToolInput({ name, input }: { name: string; input?: unknown }) {
  if (input == null) return null;
  const obj = input as Record<string, unknown>;
  // Surface the most useful field per tool without dumping huge payloads.
  const preview =
    (obj.subagent_type as string) ||
    (obj.description as string) ||
    (obj.query as string) ||
    (obj.command as string) ||
    (obj.url as string) ||
    (obj.pattern as string) ||
    (obj.file_path as string) ||
    "";
  if (!preview) return null;
  return (
    <span className="tool-input" title={name}>
      {String(preview).slice(0, 160)}
    </span>
  );
}
