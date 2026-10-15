import type { AgentPolicy, Bounties, CveNote, Finding, RunEvent, RunSummary, StartRunResponse, Submission } from "./types";

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
  programId?: number;
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

// ---- archive + bounties -----------------------------------------------------

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `GET ${url} failed: ${res.status}`);
  return data as T;
}

async function postJson<T>(url: string, body: unknown = {}): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `POST ${url} failed: ${res.status}`);
  return data as T;
}

export const listRuns = (params: { agent?: string; status?: string; q?: string } = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return getJson<RunSummary[]>(`/api/runs${qs ? `?${qs}` : ""}`);
};
export const listFindings = () => getJson<Finding[]>("/api/findings");
export const listCveNotes = () => getJson<CveNote[]>("/api/cve-notes");
export const listSubmissions = () => getJson<Submission[]>("/api/submissions");
export const exportSubmissionUrl = (id: number) => `/api/submissions/${id}/export`;

export const getBounties = () => getJson<Bounties>("/api/bounties");
export const trackLead = (normalizedUrl: string) => postJson<{ programId: number }>("/api/leads/track", { normalizedUrl });
export const dismissLead = (normalizedUrl: string) => postJson("/api/leads/dismiss", { normalizedUrl });
export const confirmProposal = (id: number) => postJson<{ snapshotId: number }>(`/api/proposals/${id}/confirm`);
export const rejectProposal = (id: number) => postJson(`/api/proposals/${id}/reject`);
export const addProgram = (body: { name: string; url: string; platform?: string; policyText?: string }) =>
  postJson<{ programId: number }>("/api/programs", body);
