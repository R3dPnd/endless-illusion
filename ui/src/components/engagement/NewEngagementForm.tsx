import { useState } from "react";
import { Banner, Button, Segmented, TextField, TextInput } from "pnd-lib-react";
import { createEngagement } from "../../api";
import { useGuarded } from "../../hooks/useEngagement";
import ProgramPicker from "../run/ProgramPicker";
import type { ConfirmedProgram, Engagement } from "../../types";

interface Props {
  programs: ConfirmedProgram[];
  onCreated: (e: Engagement) => void;
  onCancel: () => void;
}

/** Scope hosts are typed one per line. */
const hostLines = (text: string) =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

export default function NewEngagementForm({ programs, onCreated, onCancel }: Props) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"lab" | "bounty">("lab");
  const [hosts, setHosts] = useState("");
  const [notes, setNotes] = useState("");
  const [authorization, setAuthorization] = useState("");
  const [programId, setProgramId] = useState<number | null>(null);
  const { error, busy, run } = useGuarded();

  const ready = name.trim() && (kind === "lab" || programId != null);

  async function submit() {
    const created = await run(() =>
      createEngagement({
        name: name.trim(),
        kind,
        scopeHosts: hostLines(hosts),
        scopeNotes: notes,
        authorization,
        ...(kind === "bounty" && programId != null ? { programId } : {}),
      })
    );
    if (created) onCreated(created);
  }

  return (
    <form
      className="eng-form"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <TextInput label="Name" value={name} onChange={setName} placeholder="juice-shop-lab" />
      <Segmented
        label="Kind"
        value={kind}
        onChange={setKind}
        options={[
          { id: "lab", label: "Lab" },
          { id: "bounty", label: "Bounty" },
        ]}
      />
      {kind === "bounty" &&
        (programs.length > 0 ? (
          <ProgramPicker programs={programs} value={programId} onChange={setProgramId} />
        ) : (
          <Banner>No confirmed bounty programs yet. Confirm a program's scope on the Bounties tab first.</Banner>
        ))}
      <TextField label="Scope hosts (one per line)" value={hosts} onChange={setHosts} rows={4} placeholder={"127.0.0.1:3000\n*.example.com"} />
      <TextField label="Scope notes" value={notes} onChange={setNotes} rows={2} />
      <TextField label="Authorization" value={authorization} onChange={setAuthorization} rows={2} placeholder="operator-owned local lab" />
      {error && <Banner tone="error">{error}</Banner>}
      <div className="toolbar">
        <Button variant="primary" type="submit" disabled={!ready || busy}>
          Create
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
