/**
 * Guard for state-changing requests to a localhost server: any web page the
 * operator visits could otherwise POST here. Requiring a JSON content type
 * forces a CORS preflight (which we never grant), and a present Origin must be
 * one of ours. Requests without an Origin (curl, server-side tools) pass.
 */
export function requireJsonSameOrigin(allowedOrigins) {
  const allowed = new Set(allowedOrigins);
  return (req, res, next) => {
    if (req.method !== "POST") return next();
    if (!req.is("application/json")) return res.status(415).json({ error: "content-type must be application/json" });
    const origin = req.get("origin");
    if (origin && !allowed.has(origin)) return res.status(403).json({ error: `origin ${origin} not allowed` });
    return next();
  };
}
