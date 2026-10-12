import type { AgentPolicy } from "../types";
import { prettyName, classTag } from "../util";

interface Props {
  agents: AgentPolicy[];
  selected: string | null;
  onSelect: (agent: string) => void;
}

export default function AgentPicker({ agents, selected, onSelect }: Props) {
  return (
    <div className="agent-list">
      {agents.map((a) => {
        const active = a.agent === selected;
        return (
          <button
            key={a.agent}
            className={`agent-card ${active ? "is-selected" : ""}`}
            onClick={() => onSelect(a.agent)}
          >
            <div className="agent-card__top">
              <span className="agent-card__name">{prettyName(a.agent)}</span>
              {a.day && <span className="agent-card__day">{a.day}</span>}
            </div>
            <div className="agent-card__role">{a.role}</div>
            <span className={`tag tag--${classTag(a.classification)}`}>
              {a.classification}
            </span>
          </button>
        );
      })}
    </div>
  );
}
