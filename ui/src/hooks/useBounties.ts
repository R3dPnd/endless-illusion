import { useCallback, useEffect, useState } from "react";
import { addProgram, confirmProposal, dismissLead, getBounties, rejectProposal, trackLead } from "../api";
import type { Bounties } from "../types";

const POLL_MS = 5000;

/**
 * The bounty pipeline. Agents add leads and proposals from a separate MCP
 * process, so this re-fetches every 5 s while a run is active and whenever
 * the window regains focus.
 */
export function useBounties(pollWhile: boolean) {
  const [data, setData] = useState<Bounties | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await getBounties());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refresh();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [refresh]);

  useEffect(() => {
    if (!pollWhile) return;
    const t = setInterval(refresh, POLL_MS);
    return () => {
      clearInterval(t);
      void refresh(); // pick up whatever the run wrote last
    };
  }, [pollWhile, refresh]);

  // Each action refreshes after it lands; errors surface through `error`.
  const act =
    <A extends unknown[]>(fn: (...args: A) => Promise<unknown>) =>
    async (...args: A) => {
      try {
        await fn(...args);
      } catch (e) {
        setError((e as Error).message);
      }
      await refresh();
    };

  return {
    data,
    error,
    refresh,
    track: act(trackLead),
    dismiss: act(dismissLead),
    confirm: act(confirmProposal),
    reject: act(rejectProposal),
    addProgram: act(addProgram),
  };
}
