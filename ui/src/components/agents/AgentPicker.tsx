import type { AgentPolicy } from "../../types";
import AgentCard from "./AgentCard";

interface Props {
  agents: AgentPolicy[];
  selected: string | null;
  onSelect: (agent: string) => void;
}

export default function AgentPicker({ agents, selected, onSelect }: Props) {
  return (
    <div className="agent-list">
      {agents.map((a) => (
        <AgentCard key={a.agent} agent={a} selected={a.agent === selected} onSelect={onSelect} />
      ))}
    </div>
  );
}
