interface Tab<T extends string> {
  id: T;
  label: string;
  count?: number;
}

interface Props<T extends string> {
  tabs: Tab<T>[];
  active: T;
  onChange: (id: T) => void;
  size?: "lg" | "sm";
  label: string;
}

export default function Tabs<T extends string>({ tabs, active, onChange, size = "lg", label }: Props<T>) {
  return (
    <div className={`tabs tabs--${size}`} role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          aria-selected={t.id === active}
          className={`tab ${t.id === active ? "is-active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count != null && <span className="tab__count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
