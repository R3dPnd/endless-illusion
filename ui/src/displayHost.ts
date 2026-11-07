// Where display prefs live. The desktop shell (pywebview) injects the saved
// prefs as window.__EI_DESKTOP__ and stores changes through /api/display-prefs;
// a plain browser keeps them in localStorage.
import { localStorageHost, type DisplayHost, type Prefs } from "pnd-lib-react";

/** Methods the pywebview shell exposes (available once "pywebviewready" fires). */
interface ShellApi {
  toggle_fullscreen(): Promise<boolean>;
  is_fullscreen(): Promise<boolean>;
}

declare global {
  interface Window {
    __EI_DESKTOP__?: { prefs: Partial<Prefs> | null };
    pywebview?: { api: ShellApi };
  }
}

/** The shell's API, waiting for pywebview to finish injecting it. */
function shellApi(): Promise<ShellApi | null> {
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
  return new Promise((resolve) => window.addEventListener("pywebviewready", () => resolve(window.pywebview?.api ?? null), { once: true }));
}

const boot = window.__EI_DESKTOP__;

export const displayHost: DisplayHost = boot
  ? {
      isDesktop: true,
      load: () => boot.prefs,
      save: (prefs) =>
        void fetch("/api/display-prefs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(prefs) }),
      fullscreen: {
        toggle: () => shellApi().then((api) => api?.toggle_fullscreen() ?? false),
        get: () => shellApi().then((api) => api?.is_fullscreen() ?? false),
      },
    }
  : localStorageHost("ei.display");
