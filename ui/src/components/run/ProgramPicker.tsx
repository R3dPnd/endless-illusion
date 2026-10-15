import type { ConfirmedProgram } from "../../types";
import { Select } from "../ui";

interface Props {
  programs: ConfirmedProgram[];
  value: number | null;
  onChange: (id: number | null) => void;
}

/** Only programs with operator-confirmed scope can be linked to a run. */
export default function ProgramPicker({ programs, value, onChange }: Props) {
  const current = programs.find((p) => p.id === value);
  return (
    <div className="program-picker">
      <Select
        label="Program (confirmed scope)"
        value={value == null ? "" : String(value)}
        onChange={(v) => onChange(v ? Number(v) : null)}
        options={[
          { value: "", label: "No program" },
          ...programs.map((p) => ({ value: String(p.id), label: `${p.name}${p.snapshot.stale ? " — re-verify scope" : ""}` })),
        ]}
      />
      {current?.snapshot.stale && (
        <p className="gate-warn">Scope was confirmed over 30 days ago. Re-verify it before any active work.</p>
      )}
    </div>
  );
}
