import { useState } from "react";
import { listCveNotes, listFindings, listRuns, listSubmissions } from "../api";
import CveNotesTable from "../components/archive/CveNotesTable";
import FindingsTable from "../components/archive/FindingsTable";
import RunList from "../components/archive/RunList";
import RunReplay from "../components/archive/RunReplay";
import SubmissionsList from "../components/archive/SubmissionsList";
import { Banner, EmptyState, Panel, Select, Tabs, TextInput } from "../components/ui";
import { useLoad } from "../hooks/useLoad";
import type { AgentPolicy } from "../types";
import { prettyName } from "../util";

type Section = "runs" | "findings" | "cves" | "submissions";

const STATUSES = ["", "done", "running", "error", "stopped", "interrupted"];

function RunsSection({ agents }: { agents: AgentPolicy[] }) {
  const [agent, setAgent] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const runs = useLoad(() => listRuns({ agent, status, q }), [agent, status, q]);
  const current = runs.data?.find((r) => r.id === selected);

  return (
    <div className="archive-runs">
      <div className="filters">
        <Select
          label="Agent"
          value={agent}
          onChange={setAgent}
          options={[{ value: "", label: "All agents" }, ...agents.map((a) => ({ value: a.agent, label: prettyName(a.agent) }))]}
        />
        <Select label="Status" value={status} onChange={setStatus} options={STATUSES.map((s) => ({ value: s, label: s || "Any status" }))} />
        <TextInput label="Search tasks" type="search" value={q} onChange={setQ} placeholder="e.g. nginx" />
      </div>
      {runs.error && <Banner>{runs.error}</Banner>}
      <div className="archive-runs__body">
        <RunList runs={runs.data ?? []} selected={selected} onSelect={setSelected} />
        <div className="archive-runs__detail">
          {current ? <RunReplay run={current} /> : <EmptyState center>Select a run to replay it.</EmptyState>}
        </div>
      </div>
    </div>
  );
}

function RecordSection<T>({ load, render }: { load: () => Promise<T>; render: (data: T) => JSX.Element }) {
  const { data, error } = useLoad(load, []);
  if (error) return <Banner>{error}</Banner>;
  if (!data) return <EmptyState>Loading…</EmptyState>;
  return render(data);
}

export default function ArchivePage({ agents }: { agents: AgentPolicy[] }) {
  const [section, setSection] = useState<Section>("runs");
  return (
    <Panel title="Archive" className="panel--archive">
      <Tabs
        label="Archive sections"
        size="sm"
        active={section}
        onChange={setSection}
        tabs={[
          { id: "runs", label: "Runs" },
          { id: "findings", label: "Findings" },
          { id: "cves", label: "CVE notes" },
          { id: "submissions", label: "Submissions" },
        ]}
      />
      {section === "runs" && <RunsSection agents={agents} />}
      {section === "findings" && <RecordSection load={listFindings} render={(f) => <FindingsTable findings={f} />} />}
      {section === "cves" && <RecordSection load={listCveNotes} render={(n) => <CveNotesTable notes={n} />} />}
      {section === "submissions" && <RecordSection load={listSubmissions} render={(s) => <SubmissionsList submissions={s} />} />}
    </Panel>
  );
}
