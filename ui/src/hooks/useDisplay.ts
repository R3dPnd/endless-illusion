import { useEffect, useMemo, useState } from "react";
import {
  applyResolved,
  browserDisplay,
  clampScale,
  DEFAULT_PREFS,
  isDesktop,
  loadPrefs,
  resolve,
  savePrefs,
  SCALE_STEP,
  shellApi,
  type DisplayInfo,
  type Prefs,
} from "../display";

/** Detected display + the operator's visual prefs, kept applied to the page. */
export function useDisplay() {
  const [display, setDisplay] = useState<DisplayInfo>(browserDisplay);
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [fullscreen, setFullscreen] = useState(false);
  const resolved = useMemo(() => resolve(prefs, display), [prefs, display]);

  useEffect(() => applyResolved(resolved), [resolved]);

  // Follow the display: a resize, or a devicePixelRatio change when the window
  // moves to a monitor with a different scale.
  useEffect(() => {
    void shellApi().then((api) => api?.is_fullscreen().then(setFullscreen));
    const onFullscreenChange = () => setFullscreen(!!document.fullscreenElement);
    if (!isDesktop) document.addEventListener("fullscreenchange", onFullscreenChange);
    let mq: MediaQueryList | null = null;
    const refresh = () => {
      setDisplay(browserDisplay());
      mq?.removeEventListener("change", refresh);
      mq = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
      mq.addEventListener("change", refresh);
    };
    refresh();
    window.addEventListener("resize", refresh);
    return () => {
      window.removeEventListener("resize", refresh);
      mq?.removeEventListener("change", refresh);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
    };
  }, []);

  function update(patch: Partial<Prefs>) {
    setPrefs((prev) => {
      const next = { ...prev, ...patch };
      savePrefs(next);
      return next;
    });
  }

  const stepScale = (dir: 1 | -1) => update({ scale: clampScale(resolved.scale + dir * SCALE_STEP) });
  const reset = () => update({ ...DEFAULT_PREFS });
  const toggleFullscreen = () => {
    if (isDesktop) void shellApi().then((api) => api?.toggle_fullscreen().then(setFullscreen));
    else if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.();
  };

  // Ctrl + / Ctrl - / Ctrl 0 drive the UI scale (and persist it); F11 is fullscreen in the desktop shell.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isDesktop && e.key === "F11") {
        e.preventDefault();
        toggleFullscreen();
        return;
      }
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      if (e.key === "=" || e.key === "+") stepScale(1);
      else if (e.key === "-" || e.key === "_") stepScale(-1);
      else if (e.key === "0") update({ scale: "auto" });
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return { display, prefs, resolved, update, stepScale, reset, fullscreen, toggleFullscreen, isDesktop };
}

export type DisplayState = ReturnType<typeof useDisplay>;
