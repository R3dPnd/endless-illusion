import type { AgentPolicy, RunEvent, StartRunResponse } from "./types";

export async function getAgents(): Promise<AgentPolicy[]> {
  const res = await fetch("/api/agents");
  if (!res.ok) throw new Error(`GET /api/agents failed: ${res.status}`);
  return res.json();
}

export interface StartRunBody {
  agent: string;
  task: string;
  scope?: string;
  authorization?: string;
  enableActive?: boolean;
}

export async function startRun(body: StartRunBody): Promise<StartRunResponse> {
  const res = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `start failed: ${res.status}`);
  return data;
}

export async function stopRun(id: string): Promise<void> {
  await fetch(`/api/runs/${id}/stop`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
}

/** Opens an SSE stream for a run. Returns a cleanup function. */
export function openRunStream(
  id: string,
  onEvent: (evt: RunEvent) => void,
  onDone: () => void
): () => void {
  const es = new EventSource(`/api/runs/${id}/events`);
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data) as RunEvent);
    } catch {
      /* ignore keep-alive / malformed frames */
    }
  };
  es.addEventListener("done", () => {
    onDone();
    es.close();
  });
  es.onerror = () => {
    // The server ends the stream on completion; EventSource would otherwise
    // try to reconnect. Close on error to avoid a reconnect loop.
    es.close();
    onDone();
  };
  return () => es.close();
}
