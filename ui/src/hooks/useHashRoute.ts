import { useEffect, useState } from "react";

export const ROUTES = ["console", "bounties", "archive"] as const;
export type Route = (typeof ROUTES)[number];

function readHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  return (ROUTES as readonly string[]).includes(h) ? (h as Route) : "console";
}

/** Current top-level tab, kept in the URL hash (#/bounties) so links and reloads work. */
export function useHashRoute(): [Route, (r: Route) => void] {
  const [route, setRoute] = useState<Route>(readHash);
  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return [route, (r) => (window.location.hash = `/${r}`)];
}
