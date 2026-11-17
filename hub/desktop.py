"""
Endless Illusion — desktop shell (pywebview).

Hosts the control-plane server in-process on a loopback port, serves the
built client from it, and shows it in a native window (Edge WebView2 on
Windows) sized to the display it opens on. The page detects the display
itself; its visual prefs persist in the user's app-data folder.

    python -m hub.desktop          # built client (ui/dist)
    python -m hub.desktop --dev    # Vite dev server on :5173 (server on :8787 for its proxy)
    python -m hub.desktop --debug  # with WebView devtools (F12)
"""

import argparse
import json
import os
import sys
import threading
from pathlib import Path

from . import REPO_ROOT
from .app import Hub

UI_DIST = REPO_ROOT / "ui" / "dist"
DEV_URL = "http://localhost:5173"
TITLE = "Endless Illusion"


def app_data_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = base / "EndlessIllusion"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(file, fallback=None):
    try:
        return json.loads(Path(file).read_text(encoding="utf8"))
    except (OSError, ValueError):
        return fallback


def single_instance():
    """True if this is the only shell running (a second one just exits)."""
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\EndlessIllusionDesktop")
        return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    import fcntl

    single_instance.handle = open(app_data_dir() / "desktop.lock", "w")  # kept open for the process lifetime
    try:
        fcntl.flock(single_instance.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def work_area():
    """Logical (DIP) size of the primary display's work area, if we can tell."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        try:
            scale = ctypes.windll.user32.GetDpiForSystem() / 96
        except AttributeError:
            scale = 1
        # The process may be DPI-aware (pywebview makes it so) or not; normalise to DIPs.
        width, height = rect.right - rect.left, rect.bottom - rect.top
        aware = ctypes.windll.user32.IsProcessDPIAware()
        return (round(width / scale), round(height / scale)) if aware else (width, height)
    return None


def initial_geometry(state):
    """Restore the last window if we have it; small screens get maximized, big ones a centred window."""
    if state and state.get("width") and state.get("height"):
        return state
    area = work_area()
    if not area or area[0] <= 1600 or area[1] <= 900:
        return {"width": 1280, "height": 720, "maximized": True}
    width, height = min(1600, round(area[0] * 0.8)), min(1000, round(area[1] * 0.85))
    return {"width": width, "height": height, "maximized": False}


class Api:
    """
    Methods the page can call as window.pywebview.api.<name>(). pywebview
    exposes every public attribute, walking into objects, so state stays
    underscored: walking the Window object from the GUI thread deadlocks.
    """

    def __init__(self):
        self._window = None
        self._fullscreen = False

    def toggle_fullscreen(self):
        self._window.toggle_fullscreen()
        self._fullscreen = not self._fullscreen
        return self._fullscreen

    def is_fullscreen(self):
        return self._fullscreen


def main():
    parser = argparse.ArgumentParser(description="Endless Illusion desktop app.")
    parser.add_argument("--dev", action="store_true", help="load the Vite dev server (hot reload)")
    parser.add_argument("--debug", action="store_true", help="enable WebView devtools")
    args = parser.parse_args()

    if not single_instance():
        print("[desktop] Endless Illusion is already open.", file=sys.stderr)
        sys.exit(0)
    if not args.dev and not (UI_DIST / "index.html").exists():
        sys.exit("[desktop] ui/dist is missing - build the client first (python pnd.py does it for you).")

    import webview  # imported late so --help and the checks above stay fast

    data = app_data_dir()
    prefs_file = data / "display-prefs.json"
    state_file = data / "window-state.json"

    port = int(os.environ.get("PORT", 8787)) if args.dev else int(os.environ.get("EI_PORT", 0))
    hub = Hub(
        claude_cmd=os.environ.get("CLAUDE_BIN", "claude"),
        static_dir=None if args.dev else UI_DIST,
        data_dir=os.environ.get("EI_DATA_DIR") or None,
        prefs_file=prefs_file,
        index_bootstrap=lambda: {"prefs": read_json(prefs_file)},
        allowed_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    server = hub.serve("127.0.0.1", port)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    hub.allowed_origins.add(origin)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[desktop] control plane on {origin}", flush=True)

    geometry = initial_geometry(read_json(state_file))
    api = Api()
    window = webview.create_window(
        TITLE,
        DEV_URL if args.dev else f"{origin}/",
        js_api=api,
        width=geometry["width"],
        height=geometry["height"],
        x=geometry.get("x"),
        y=geometry.get("y"),
        min_size=(640, 420),
        background_color="#07070d",
        maximized=bool(geometry.get("maximized")),
        text_select=True,
    )
    api._window = window

    maximized = [bool(geometry.get("maximized"))]
    window.events.maximized += lambda: maximized.__setitem__(0, True)
    window.events.restored += lambda: maximized.__setitem__(0, False)

    def on_closing():
        state = {"maximized": maximized[0]}
        if not maximized[0] and not api._fullscreen:
            state.update(width=window.width, height=window.height, x=window.x, y=window.y)
        else:
            previous = read_json(state_file) or {}
            state.update({k: previous[k] for k in ("width", "height", "x", "y") if k in previous})
        try:
            state_file.write_text(json.dumps(state, indent=2), encoding="utf8")
        except OSError:
            pass

    window.events.closing += on_closing

    try:
        webview.start(debug=args.debug)
    finally:
        hub.runner.stop_all()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
