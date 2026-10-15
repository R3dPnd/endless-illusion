interface Props {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: "text" | "search" | "url";
}

export default function TextInput({ label, value, onChange, placeholder, type = "text" }: Props) {
  return (
    <label className="control">
      <span className="control__label">{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
