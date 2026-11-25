import { useState } from "react";
import { Banner, Button, Segmented, TextField, TextInput } from "pnd-lib-react";
import { createEngagement } from "../../api";
import { newEngagementHosts } from "../../engagement";
import { useGuarded } from "../../hooks/useEngagement";
import ProgramPicker from "../run/ProgramPicker";
import type { ConfirmedProgram, Engagement } from "../../types";

interface Props {
  programs: ConfirmedProgram[];
  onCreated: (e: Engagement) => void;
  onCancel: () => void;
}

// A lab's scope hosts are typed one per line; a bounty's come from the confirmed snapshot (shown read-only).

export default function NewEngagementForm({ programs, onCreated, onCancel }: Props) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"lab" | "bounty">("lab");
  const [hosts, setHosts] = useState("");
  const [notes, setNotes] = useState("");
  const [authorization, setAuthorization] = useState("");
  const [programId, setProgramId] = useState<number | null>(null);
  const { error, busy, run } = useGuarded();

  const picked = kind === "bounty" ? programs.find((p) => p.id === programId) : undefined;
  const ready = name.trim() && (kind === "lab" || (picked != null && picked.snapshot.scopeHosts.length > 0));

  async function submit() {
    const created = await run(() =>
      createEngagement({
        name: name.trim(),
        kind,
        scopeHosts: newEngagementHosts(kind, hosts),
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
      {kind === "lab" ? (
        <TextField label="Scope hosts (one per line)" value={hosts} onChange={setHosts} rows={4} placeholder={"127.0.0.1:3000\n*.example.com"} />
      ) : (
        picked && (
          <div className="eng-form__derived">
            <strong>Scope hosts (from the confirmed scope snapshot, read-only)</strong>
            {picked.snapshot.scopeHosts.length > 0 ? (
              <ul>
                {picked.snapshot.scopeHosts.map((h) => (
                  <li key={h}>
                    <code>{h}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <Banner tone="error">This program's confirmed scope names no in-scope host; it can't be an engagement.</Banner>
            )}
            {picked.snapshot.stale && <p className="gate-warn">The snapshot is over 30 days old: stages can't be armed until the scope is re-confirmed.</p>}
          </div>
        )
      )}
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
