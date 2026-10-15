import { useState } from "react";
import { Button, TextField, TextInput } from "../ui";

interface Props {
  onAdd: (p: { name: string; url: string; platform?: string; policyText?: string }) => Promise<void>;
}

export default function AddProgramForm({ onAdd }: Props) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [platform, setPlatform] = useState("");
  const [policyText, setPolicyText] = useState("");

  if (!open) {
    return (
      <Button variant="ghost" onClick={() => setOpen(true)}>
        + Add program
      </Button>
    );
  }

  return (
    <form
      className="add-program"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim() || !url.trim()) return;
        await onAdd({ name, url, platform: platform || undefined, policyText });
        setName("");
        setUrl("");
        setPlatform("");
        setPolicyText("");
        setOpen(false);
      }}
    >
      <div className="filters">
        <TextInput label="Name" value={name} onChange={setName} placeholder="Acme" />
        <TextInput label="Program URL" type="url" value={url} onChange={setUrl} placeholder="https://hackerone.com/acme" />
        <TextInput label="Platform" value={platform} onChange={setPlatform} placeholder="HackerOne" />
      </div>
      <TextField label="Policy / scope text" value={policyText} onChange={setPolicyText} rows={4} placeholder="Paste the program's scope and rules" />
      <div className="card__actions">
        <Button type="submit" variant="ghost" disabled={!name.trim() || !url.trim()}>
          Add to tracked
        </Button>
        <Button variant="danger" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
