import { useState } from "react";
import type { AgentPolicy } from "../types";
import { canGoActive, prettyName } from "../util";

interface Props {
  agent: AgentPolicy | undefined;
  busy: boolean;
  onRun: (body: {
    task: string;
    scope: string;
    authorization: string;
    enableActive: boolean;
  }) => void;
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
    return <div className="form-empty">Select an agent to begin.</div>;
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
        {agent.role === "orchestrator" && (
          <span className="hint"> — will route to the specialists</span>
        )}
      </div>

      <label>
        Task
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. Summarize known CVEs for nginx 1.24.0"
          rows={3}
          required
        />
      </label>

      <label>
        Scope / target(s)
        <textarea
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          placeholder="In-scope assets, domains, IP ranges, exclusions…"
          rows={2}
        />
      </label>

      <label>
        Authorization
        <textarea
          value={authorization}
          onChange={(e) => setAuthorization(e.target.value)}
          placeholder="Bounty program + link, signed SOW reference, or owner's written permission. Leave blank for passive-only."
          rows={2}
        />
      </label>

      {activeCapable ? (
        <div className={`active-gate ${activeArmed ? "is-armed" : ""}`}>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={enableActive}
              onChange={(e) => setEnableActive(e.target.checked)}
            />
            Enable active testing tools (adds <code>Bash</code> — live traffic)
          </label>
          {enableActive && (
            <>
              {!hasAuth && (
                <p className="gate-warn">
                  Authorization is required before active tools can be armed.
                </p>
              )}
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(e) => setConfirm(e.target.checked)}
                  disabled={!hasAuth}
                />
                I confirm I have documented authorization for this exact scope.
              </label>
            </>
          )}
          <p className="gate-status">
            {activeArmed ? (
              <span className="armed">● Active tools ARMED</span>
            ) : (
              <span className="safe">● Passive tools only (safe default)</span>
            )}
          </p>
        </div>
      ) : (
        <p className="gate-status">
          <span className="safe">● Passive agent — no active tooling</span>
        </p>
      )}

      <button type="submit" className="btn-run" disabled={!canSubmit}>
        {busy ? "Running…" : "Trigger agent"}
      </button>
    </form>
  );
}
