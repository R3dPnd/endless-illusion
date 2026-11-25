import { useCallback, useEffect, useRef, useState } from "react";
import { getEngagement, getPendingGate, listEngagements, openRunStream } from "../api";
import type { Engagement, EngagementDetail, PendingGate, RunEvent } from "../types";

const DETAIL_MS = 1000;
const BADGE_MS = 2000;

/** Calls `fn` now and then every `ms` while the page is visible; clears its timer on unmount. */
function usePoll(fn: () => Promise<void>, ms: number, key: unknown) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (alive && document.visibilityState === "visible") void ref.current();
    };
    tick();
    const t = setInterval(tick, ms);
    document.addEventListener("visibilitychange", tick);
    return () => {
      alive = false;
      clearInterval(t);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [ms, key]);
}

/** One engagement's detail (stages, plan, pending approvals, questions), refreshed every second. */
export function useEngagement(id: number | null) {
  const [detail, setDetail] = useState<EngagementDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (id == null) return;
    try {
      setDetail(await getEngagement(id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => setDetail(null), [id]);
  usePoll(refresh, DETAIL_MS, id);
  return { detail: id == null ? null : detail, error, refresh };
}

/** The engagement list; reloaded on demand (after a create). */
export function useEngagementList() {
  const [list, setList] = useState<Engagement[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      setList(await listEngagements());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return { list, error, refresh };
}

/** Every pending approval across engagements (the tab badge and the page's "pending elsewhere" banner), every 2 s. */
export function usePendingGate(): PendingGate {
  const [pending, setPending] = useState<PendingGate>({ count: 0, items: [] });
  usePoll(
    async () => {
      try {
        setPending(await getPendingGate());
      } catch {
        /* the badge is best-effort; the page shows real errors */
      }
    },
    BADGE_MS,
    null
  );
  return pending;
}

/** The live event feed of one stage run (replayed from the start by the hub's stream). */
export function useRunFeed(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [closed, setClosed] = useState<string | null>(null);
  useEffect(() => {
    setEvents([]);
    setClosed(null);
    if (!runId) return;
    return openRunStream(
      runId,
      (evt) => {
        setEvents((prev) => [...prev, evt]);
        if (evt.kind === "closed") setClosed(evt.status);
      },
      () => setClosed((c) => c ?? "done")
    );
  }, [runId]);
  return { events, closed };
}

/** Runs an async action, keeping its error visible (never swallowed) until the next attempt. */
export function useGuarded() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { error, busy, run };
}
