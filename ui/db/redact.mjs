export const MAX_TEXT = 65536;

const MASK = "[REDACTED]";

// Patterns for secrets that must never be persisted (RoE §4).
const PATTERNS = [
  [/(authorization:\s*bearer\s+)[^\s"']+/gi, `$1${MASK}`],
  [/\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+/g, MASK],
  [/\b(AKIA|ASIA)[0-9A-Z]{16}\b/g, MASK],
  [/\b(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key)(\s*[=:]\s*)[^\s&"',;]+/gi, `$1$2${MASK}`],
];

/** Mask obvious secrets in free text. */
export function redact(text) {
  if (typeof text !== "string") return text;
  return PATTERNS.reduce((s, [re, rep]) => s.replace(re, rep), text);
}

/** Cap text at MAX_TEXT characters. */
export function clip(text, max = MAX_TEXT) {
  return typeof text === "string" && text.length > max ? text.slice(0, max) : text;
}
