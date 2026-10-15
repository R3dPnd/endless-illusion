import { useEffect, useState } from "react";
import type { AgentPolicy } from "../types";
import { getAgents } from "../api";

/** Load the agent roster and track which agent is selected. */
export function useAgents() {
  const [agents, setAgents] = useState<AgentPolicy[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAgents()
      .then((list) => {
        setAgents(list);
        setSelected((cur) => cur ?? list[0]?.agent ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);

  const selectedAgent = agents.find((a) => a.agent === selected);
  return { agents, selected, setSelected, selectedAgent, error };
}
