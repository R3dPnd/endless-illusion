/**
 * Canonical key for a program URL so repeat sightings group together:
 * lowercase host without "www.", path without trailing slash, no scheme or query.
 */
export function normalizeUrl(url) {
  const raw = String(url).trim();
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : `https://${raw}`;
  let parsed;
  try {
    parsed = new URL(withScheme);
  } catch {
    return raw.toLowerCase().replace(/\/+$/, "");
  }
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
  return host + parsed.pathname.toLowerCase().replace(/\/+$/, "");
}
