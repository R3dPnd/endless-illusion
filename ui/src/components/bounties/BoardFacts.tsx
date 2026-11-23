import type { BoardDetails } from "../../types";

/** Rewards, program type, and asset types as a row of chips; renders nothing if an agent supplied none. */
export default function BoardFacts({ b }: { b: BoardDetails }) {
  if (!b.programType && !b.rewards && b.assetTypes.length === 0) return null;
  return (
    <div className="board-facts">
      {b.rewards ? (
        <span className="chip tone--green board-facts__reward">{b.rewards}</span>
      ) : (
        b.programType === "bounty" && <span className="chip tone--green">paid bounty</span>
      )}
      {b.programType === "vdp" && <span className="chip tone--muted">VDP · no bounty</span>}
      {b.assetTypes.map((t) => (
        <span key={t} className="chip tone--cyan">
          {t}
        </span>
      ))}
    </div>
  );
}
