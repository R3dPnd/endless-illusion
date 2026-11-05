// Display detection and the operator's visual preferences.
//
// Display metrics come from the page itself (window.screen is in DIPs and, with
// no browser zoom in the desktop shell, devicePixelRatio is the OS scale).
// The desktop shell (pywebview) injects the saved prefs as
// window.__EI_DESKTOP__ and stores changes through /api/display-prefs; a
// plain browser keeps them in localStorage.

export interface DisplayInfo {
  scaleFactor: number;
  size: { width: number; height: number };
  workArea: { width: number; height: number };
  physical: { width: number; height: number };
  touch: boolean;
}

export type Profile = "handheld" | "compact" | "desktop" | "large";
export type Density = "compact" | "comfortable" | "spacious";
export type Effects = "full" | "reduced" | "off";
export type Font = "pixel" | "readable";

export interface Prefs {
  scale: "auto" | number;
  density: "auto" | Density;
  effects: "auto" | Effects;
  touch: "auto" | "on" | "off";
  font: Font;
}

export interface Resolved {
  profile: Profile;
  scale: number;
  density: Density;
  effects: Effects;
  touch: boolean;
  font: Font;
}

interface DesktopBoot {
  prefs: Partial<Prefs> | null;
}

/** Methods the pywebview shell exposes (available once "pywebviewready" fires). */
interface ShellApi {
  toggle_fullscreen(): Promise<boolean>;
  is_fullscreen(): Promise<boolean>;
}

declare global {
  interface Window {
    __EI_DESKTOP__?: DesktopBoot;
    pywebview?: { api: ShellApi };
  }
}

const boot = window.__EI_DESKTOP__;
export const isDesktop = !!boot;

/** The shell's API, waiting for pywebview to finish injecting it. Null in a browser. */
export function shellApi(): Promise<ShellApi | null> {
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
  if (!isDesktop) return Promise.resolve(null);
  return new Promise((resolve) => window.addEventListener("pywebviewready", () => resolve(window.pywebview?.api ?? null), { once: true }));
}

export const DEFAULT_PREFS: Prefs = { scale: "auto", density: "auto", effects: "auto", touch: "auto", font: "pixel" };
export const SCALE_MIN = 0.6;
export const SCALE_MAX = 2;
export const SCALE_STEP = 0.05;

const STORAGE_KEY = "ei.display";

export const clampScale = (n: number) => Math.round(Math.min(SCALE_MAX, Math.max(SCALE_MIN, n)) * 100) / 100;

const coarsePointer = () => window.matchMedia?.("(any-pointer: coarse)").matches ?? false;

/** Display metrics as the browser sees them (no shell). */
export function browserDisplay(): DisplayInfo {
  const s = window.screen;
  const dpr = window.devicePixelRatio || 1;
  return {
    scaleFactor: dpr,
    size: { width: s.width, height: s.height },
    workArea: { width: s.availWidth, height: s.availHeight },
    physical: { width: Math.round(s.width * dpr), height: Math.round(s.height * dpr) },
    touch: coarsePointer(),
  };
}

/** Classify a display by its logical (DIP) size and input. */
export function profileOf(d: DisplayInfo): Profile {
  const w = Math.max(d.size.width, d.size.height);
  const h = Math.min(d.size.width, d.size.height);
  if (w <= 1366 && h <= 800) return d.touch ? "handheld" : "compact";
  if (w < 1100) return "compact";
  if (w >= 2400) return "large";
  return "desktop";
}

/** Turn "auto" choices into concrete ones for this display. */
export function resolve(prefs: Prefs, d: DisplayInfo): Resolved {
  const profile = profileOf(d);
  const w = d.workArea.width;
  const autoScale = profile === "large" ? (w >= 3200 ? 1.5 : 1.25) : 1;
  const autoDensity: Density =
    profile === "handheld" || profile === "compact" ? "compact" : profile === "large" ? "spacious" : d.workArea.height < 900 ? "compact" : "comfortable";
  // Handhelds run on battery: skip the full-screen scanline layer and heavy glows.
  const autoEffects: Effects = profile === "handheld" ? "reduced" : "full";
  return {
    profile,
    scale: prefs.scale === "auto" ? autoScale : clampScale(prefs.scale),
    density: prefs.density === "auto" ? autoDensity : prefs.density,
    effects: prefs.effects === "auto" ? autoEffects : prefs.effects,
    touch: prefs.touch === "auto" ? d.touch : prefs.touch === "on",
    font: prefs.font,
  };
}

function sanitize(raw: unknown): Prefs {
  const p = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const pick = <T extends string>(v: unknown, allowed: readonly T[], fallback: T): T => (allowed.includes(v as T) ? (v as T) : fallback);
  return {
    scale: typeof p.scale === "number" && Number.isFinite(p.scale) ? clampScale(p.scale) : "auto",
    density: pick(p.density, ["auto", "compact", "comfortable", "spacious"] as const, "auto"),
    effects: pick(p.effects, ["auto", "full", "reduced", "off"] as const, "auto"),
    touch: pick(p.touch, ["auto", "on", "off"] as const, "auto"),
    font: pick(p.font, ["pixel", "readable"] as const, "pixel"),
  };
}

export function loadPrefs(): Prefs {
  if (boot) return sanitize(boot.prefs);
  try {
    return sanitize(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(prefs: Prefs) {
  if (isDesktop) {
    void fetch("/api/display-prefs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(prefs) });
    return;
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable: prefs last for this session only */
  }
}

/** Push the resolved look onto <html>: data-* attributes for CSS, and the scale as CSS zoom. */
export function applyResolved(r: Resolved) {
  const root = document.documentElement;
  root.dataset.profile = r.profile;
  root.dataset.density = r.density;
  root.dataset.effects = r.effects;
  root.dataset.touch = r.touch ? "on" : "off";
  root.dataset.font = r.font;
  root.style.setProperty("--zoom", String(r.scale));
}

/** Describe a display for the settings panel, e.g. "1280×720 @150% · 1920×1080 px · touch". */
export function describeDisplay(d: DisplayInfo): string {
  const parts = [`${d.size.width}×${d.size.height} @${Math.round(d.scaleFactor * 100)}%`, `${d.physical.width}×${d.physical.height} px`];
  if (d.touch) parts.push("touch");
  return parts.join(" · ");
}
