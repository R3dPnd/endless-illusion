import { getJson, postJson } from "pnd-lib-react";
import type { AgentPolicy, Bounties, CveNote, Engagement, EngagementDetail, EngagementQuestion, Finding, PendingGate, RunEvent, RunSummary, StartRunResponse, Submission } from "./types";

export const getAgents = () => getJson<AgentPolicy[]>("/api/agents");

export interface StartRunBody {
  agent: string;
  task: string;
  scope?: string;
  authorization?: string;
  enableActive?: boolean;
  programId?: number;
  /** Reply into this finished run's claude session; the hub inherits its agent, scope, authorization, and tools. */
  continueRun?: string;
}

export const startRun = (body: StartRunBody) => postJson<StartRunResponse>("/api/runs", body);

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

// ---- engagements ------------------------------------------------------------

export interface NewEngagementBody {
  name: string;
  kind: "lab" | "bounty";
  scopeHosts: string[];
  scopeNotes: string;
  authorization: string;
  programId?: number;
}

const eng = (id: number) => `/api/engagements/${id}`;
export const listEngagements = () => getJson<Engagement[]>("/api/engagements");
export const createEngagement = (body: NewEngagementBody) => postJson<Engagement>("/api/engagements", body);
export const getEngagement = (id: number) => getJson<EngagementDetail>(eng(id));
export const startStage = (id: number, stage: string, body: { armed?: boolean; question?: string } = {}) =>
  postJson<{ runId: string }>(`${eng(id)}/stages/${stage}/start`, body);
export const skipStage = (id: number, stage: string) => postJson(`${eng(id)}/stages/${stage}/skip`, {});
export const stopStage = (id: number, stage: string) => postJson(`${eng(id)}/stages/${stage}/stop`, {});
export const approvePlan = (id: number) => postJson<{ planId: number }>(`${eng(id)}/plan/approve`, {});
export const revisePlan = (id: number, comment: string) => postJson(`${eng(id)}/plan/revise`, { comment });
export const askQuestion = (
  id: number,
  body: { stage: string; question: string; actionId?: number; kind?: "ask" | "explain"; technique?: string }
) => postJson<EngagementQuestion>(`${eng(id)}/ask`, body);
export const decideAction = (actionId: number, body: { approve: boolean; message?: string; scopeAck?: boolean }) =>
  postJson(`/api/gate/actions/${actionId}/decide`, body);
export const getPendingGate = () => getJson<PendingGate>("/api/gate/pending");
