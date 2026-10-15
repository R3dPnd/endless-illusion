/** One-line readout of which toolset a run will get. */
export default function GateStatus({ armed, label }: { armed: boolean; label: string }) {
  return (
    <p className="gate-status">
      <span className={armed ? "armed" : "safe"}>● {label}</span>
    </p>
  );
}
