import type { CSSProperties } from "react";
import type { AgentPolicy } from "../../types";
import { speakerFor } from "../../speakers";
import { classTag, prettyName } from "../../util";
import { Tag } from "../ui";

interface Props {
  agent: AgentPolicy;
  selected: boolean;
  onSelect: (agent: string) => void;
}

export default function AgentCard({ agent, selected, onSelect }: Props) {
  return (
    <button
      className={`agent-card ${selected ? "is-selected" : ""}`}
      style={{ "--who": speakerFor(agent.agent).color } as CSSProperties}
      onClick={() => onSelect(agent.agent)}
    >
      <div className="agent-card__top">
        <span className="agent-card__name">{prettyName(agent.agent)}</span>
        {agent.day && <span className="agent-card__day">{agent.day}</span>}
      </div>
      <div className="agent-card__role">{agent.role}</div>
      <Tag tone={classTag(agent.classification)}>{agent.classification}</Tag>
    </button>
  );
}
