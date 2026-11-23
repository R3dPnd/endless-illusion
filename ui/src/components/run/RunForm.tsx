import { useEffect, useState } from "react";
import { authorizationText, scopeText } from "../../bounties";
import type { AgentPolicy, ConfirmedProgram } from "../../types";
import type { RunRequest } from "../../hooks/useRun";
import { composeRun, isComplete, specFor } from "../../triggerSpecs";
import { canGoActive, prettyName } from "../../util";
import { Button, EmptyState, TextField } from "pnd-lib-react";
import ActiveGate from "./ActiveGate";
import GateStatus from "./GateStatus";
import ProgramPicker from "./ProgramPicker";

interface Props {
  agent: AgentPolicy | undefined;
  busy: boolean;
  onRun: (body: RunRequest) => void;
  programs: ConfirmedProgram[];
  programId: number | null;
  onProgramChange: (id: number | null) => void;
}

/** The Trigger form, shaped to the selected agent (see triggerSpecs.ts). */
export default function RunForm({ agent, busy, onRun, programs, programId, onProgramChange }: Props) {
  const [task, setTask] = useState("");
  // Field values by key. Scope and authorization are shared keys, so they carry
  // across agents that use them; hidden fields are never sent.
  const [values, setValues] = useState<Record<string, string>>({});
  const [enableActive, setEnableActive] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const set = (key: string) => (v: string) => setValues((prev) => ({ ...prev, [key]: v }));

  const spec = specFor(agent);

  // Choosing a program fills Scope and Authorization from its confirmed snapshot.
  const program = spec.program ? programs.find((p) => p.id === programId) : undefined;
  useEffect(() => {
    if (!program) return;
    setValues((prev) => ({ ...prev, scope: scopeText(program), authorization: authorizationText(program) }));
  }, [program]);

  // Never carry an armed gate over to a different agent.
  useEffect(() => {
    setEnableActive(false);
    setConfirm(false);
  }, [agent?.agent]);

  if (!agent) {
    return <EmptyState>Select an agent to begin.</EmptyState>;
  }

  const composed = composeRun(spec, task, values);
  const activeCapable = canGoActive(agent);
  const hasAuth = composed.authorization.length > 0;
  // Active tooling only unlocks with: capable agent + authorization + confirm.
  const activeArmed = activeCapable && enableActive && confirm && hasAuth;
  const canSubmit = isComplete(spec, task, values) && !busy;

  return (
    <form
      className="run-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onRun({ ...composed, enableActive: activeArmed, ...(program ? { programId: program.id } : {}) });
      }}
    >
      <div className="run-form__agent">
        Dispatching to <strong>{prettyName(agent.agent)}</strong>
        <span className="hint"> — {agent.role}</span>
      </div>

      {spec.program && programs.length > 0 && <ProgramPicker programs={programs} value={programId} onChange={onProgramChange} />}

      <TextField
        label={spec.taskLabel}
        value={task}
        onChange={setTask}
        placeholder={spec.taskPlaceholder}
        rows={spec.taskRows ?? 3}
        required
      />
      {spec.fields.map((f) => (
        <TextField
          key={f.key}
          label={f.required ? f.label : `${f.label} (optional)`}
          value={values[f.key] ?? ""}
          onChange={set(f.key)}
          placeholder={f.placeholder}
          rows={f.rows}
          required={f.required}
        />
      ))}

      {activeCapable ? (
        <ActiveGate
          enabled={enableActive}
          onEnabledChange={setEnableActive}
          confirmed={confirm}
          onConfirmedChange={setConfirm}
          hasAuth={hasAuth}
          armed={activeArmed}
        />
      ) : (
        <GateStatus armed={false} label={agent.role === "orchestrator" ? "Routes to specialists — no active tooling of its own" : "Passive agent — no active tooling"} />
      )}

      <Button type="submit" variant="primary" disabled={!canSubmit}>
        {busy ? "Running…" : spec.submitLabel}
      </Button>
    </form>
  );
}
