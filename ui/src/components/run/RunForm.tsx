import { useState } from "react";
import type { AgentPolicy } from "../../types";
import type { RunRequest } from "../../hooks/useRun";
import { canGoActive, prettyName } from "../../util";
import { Button, EmptyState, TextField } from "../ui";
import ActiveGate from "./ActiveGate";
import GateStatus from "./GateStatus";

interface Props {
  agent: AgentPolicy | undefined;
  busy: boolean;
  onRun: (body: RunRequest) => void;
}

export default function RunForm({ agent, busy, onRun }: Props) {
  const [task, setTask] = useState("");
  const [scope, setScope] = useState("");
  const [authorization, setAuthorization] = useState("");
  const [enableActive, setEnableActive] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const activeCapable = canGoActive(agent);
  const hasAuth = authorization.trim().length > 0;
  // Active tooling only unlocks with: capable agent + authorization + confirm.
  const activeArmed = activeCapable && enableActive && confirm && hasAuth;
  const canSubmit = !!agent && task.trim().length > 0 && !busy;

  if (!agent) {
    return <EmptyState>Select an agent to begin.</EmptyState>;
  }

  return (
    <form
      className="run-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onRun({ task, scope, authorization, enableActive: activeArmed });
      }}
    >
      <div className="run-form__agent">
        Dispatching to <strong>{prettyName(agent.agent)}</strong>
        {agent.role === "orchestrator" && <span className="hint"> — will route to the specialists</span>}
      </div>

      <TextField
        label="Task"
        value={task}
        onChange={setTask}
        placeholder="e.g. Summarize known CVEs for nginx 1.24.0"
        rows={3}
        required
      />
      <TextField
        label="Scope / target(s)"
        value={scope}
        onChange={setScope}
        placeholder="In-scope assets, domains, IP ranges, exclusions…"
      />
      <TextField
        label="Authorization"
        value={authorization}
        onChange={setAuthorization}
        placeholder="Bounty program + link, signed SOW reference, or owner's written permission. Leave blank for passive-only."
      />

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
        <GateStatus armed={false} label="Passive agent — no active tooling" />
      )}

      <Button type="submit" variant="primary" disabled={!canSubmit}>
        {busy ? "Running…" : "Trigger agent"}
      </Button>
    </form>
  );
}
