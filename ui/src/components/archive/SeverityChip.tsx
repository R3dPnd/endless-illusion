import type { Severity } from "../../types";

export default function SeverityChip({ severity }: { severity: Severity }) {
  return <span className={`sev sev--${severity}`}>{severity}</span>;
}
