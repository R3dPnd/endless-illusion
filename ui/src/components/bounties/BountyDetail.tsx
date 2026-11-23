import { useEffect, useRef, useState } from "react";
import { Button } from "pnd-lib-react";
import { dannSession, type BoardItem, type DannSession } from "../../bounties";
import { speakerFor } from "../../speakers";
import SpeakerChip from "../chat/SpeakerChip";
import BoardFacts from "./BoardFacts";
import ExternalLink from "./ExternalLink";
import ScopeList from "./ScopeList";

interface Props {
  item: BoardItem;
  /** A run is in progress; a new session can start once it finishes. */
  busy: boolean;
  onClose: () => void;
  onStartDann: (session: DannSession) => void;
  onTrack?: () => void;
  onDismiss?: () => void;
}

const STAGE_LABEL = { lead: "Discovered lead", tracked: "Tracked", confirmed: "Scope confirmed" } as const;

/** A bounty's full details, with an editable brief to open a session with Dann. */
export default function BountyDetail({ item, busy, onClose, onStartDann, onTrack, onDismiss }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const defaults = dannSession(item);
  const [task, setTask] = useState(defaults.task);
  const b = item.bounty;
  const dann = speakerFor("dann-of-thursday");

  // Open as a modal; Esc and the backdrop close it. The parent keys this by item, so the brief resets per bounty.
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);

  const canStart = !busy && task.trim().length > 0;

  return (
    <dialog
      ref={ref}
      className={`bounty-detail bounty-col--${item.stage}`}
      aria-labelledby="bounty-detail-title"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current?.close()}
    >
      <div className="bounty-detail__body">
        <header className="bounty-detail__head">
          <div>
            <p className="bounty-detail__stage">{STAGE_LABEL[item.stage]}</p>
            <h2 id="bounty-detail-title">{b.name}</h2>
            <div className="card__top">
              {b.platform && <span className="chip">{b.platform}</span>}
              {b.programUpdated && <span className="chip tone--muted">updated {b.programUpdated.slice(0, 10)}</span>}
            </div>
          </div>
          <Button variant="ghost" onClick={() => ref.current?.close()} aria-label="Close">
            ✕
          </Button>
        </header>

        <ExternalLink href={b.url} />
        <BoardFacts b={b} />
        {b.details && <p className="bounty-detail__details">{b.details}</p>}

        {item.stage === "confirmed" ? (
          <>
            <div className="cell-sub">
              scope snapshot #{item.bounty.snapshot.id} · confirmed {item.bounty.snapshot.confirmedAt.slice(0, 10)}
              {item.bounty.snapshot.stale && <span className="chip tone--orange">re-verify scope</span>}
            </div>
            <ScopeList title="In scope" items={item.bounty.snapshot.inScope} />
            {item.bounty.snapshot.exclusions.length > 0 && <ScopeList title="Exclusions" items={item.bounty.snapshot.exclusions} />}
          </>
        ) : (
          b.scopeSummary && (
            <p className="bounty-card__unverified">
              <span className="chip tone--orange">unverified scope</span> {b.scopeSummary}
            </p>
          )
        )}

        {item.stage === "lead" && (
          <div className="bounty-card__found">
            {item.bounty.sightings} sighting{item.bounty.sightings === 1 ? "" : "s"} · found by{" "}
            {item.bounty.agents.map((a) => (
              <SpeakerChip key={a} id={a} />
            ))}{" "}
            via {item.bounty.foundVia}
          </div>
        )}

        {b.sources.length > 0 && (
          <details className="bounty-detail__sources">
            <summary>Sources ({b.sources.length})</summary>
            <ul>
              {b.sources.map((s) => (
                <li key={s}>
                  <ExternalLink href={s} />
                </li>
              ))}
            </ul>
          </details>
        )}

        <form
          className="bounty-detail__dann"
          onSubmit={(e) => {
            e.preventDefault();
            if (!canStart) return;
            onStartDann({ ...defaults, task: task.trim() });
          }}
        >
          <label className="field" style={{ color: dann.color }}>
            Brief for {dann.name}
            <textarea value={task} rows={8} onChange={(e) => setTask(e.target.value)} />
          </label>
          <p className="cell-sub">
            {item.stage === "confirmed"
              ? "Runs under this program's confirmed scope snapshot. Active tooling stays off; arm it from the Trigger form when you're ready."
              : "No confirmed scope, so Dann's team keeps this to passive public research."}
          </p>
          <div className="card__actions">
            <Button type="submit" variant="primary" disabled={!canStart}>
              {busy ? "A run is in progress…" : `Start session with ${dann.name}`}
            </Button>
            <Button type="button" variant="link" onClick={() => setTask(defaults.task)}>
              Reset brief
            </Button>
            {onTrack && (
              <Button type="button" variant="ghost" className="push-right" onClick={onTrack}>
                Track
              </Button>
            )}
            {onDismiss && (
              <Button type="button" variant="danger" onClick={onDismiss}>
                Dismiss
              </Button>
            )}
          </div>
        </form>
      </div>
    </dialog>
  );
}
