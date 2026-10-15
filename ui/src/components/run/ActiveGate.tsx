import { Checkbox } from "../ui";
import GateStatus from "./GateStatus";

interface Props {
  enabled: boolean;
  onEnabledChange: (v: boolean) => void;
  confirmed: boolean;
  onConfirmedChange: (v: boolean) => void;
  hasAuth: boolean;
  armed: boolean;
}

/** Opt-in for the authorized-active toolset; arming needs authorization + confirm. */
export default function ActiveGate({ enabled, onEnabledChange, confirmed, onConfirmedChange, hasAuth, armed }: Props) {
  return (
    <div className={`active-gate ${armed ? "is-armed" : ""}`}>
      <Checkbox checked={enabled} onChange={onEnabledChange}>
        Enable active testing tools (adds <code>Bash</code> — live traffic)
      </Checkbox>
      {enabled && (
        <>
          {!hasAuth && <p className="gate-warn">Authorization is required before active tools can be armed.</p>}
          <Checkbox checked={confirmed} onChange={onConfirmedChange} disabled={!hasAuth}>
            I confirm I have documented authorization for this exact scope.
          </Checkbox>
        </>
      )}
      <GateStatus armed={armed} label={armed ? "Active tools ARMED" : "Passive tools only (safe default)"} />
    </div>
  );
}
