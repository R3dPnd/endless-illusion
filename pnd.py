#!/usr/bin/env python3
"""Start the Endless Illusion ecosystem.

Default: the desktop app (hub/desktop.py) — one native window (pywebview)
that hosts the Python control-plane server in-process on a random loopback
port and the built UI. The client is rebuilt first whenever ui/src is newer
than ui/dist, and the hub's .venv is created/updated from requirements.txt.

--web brings up the browser setup instead: the hub API (python -m hub,
127.0.0.1:8787) and the Vite client (http://localhost:5173), with their output
interleaved and prefixed. Ctrl+C stops everything.

Node is only needed to build or serve the React client.

Usage:
    python pnd.py                 # preflight, install/build if needed, open the desktop app
    python pnd.py --dev           # desktop window on the Vite dev server (hot reload)
    python pnd.py --rebuild       # force a client build before opening
    python pnd.py --web           # browser setup: API + Vite
    python pnd.py --web --open    # ...and open the UI in the browser
    python pnd.py --web --only server|client
    python pnd.py --sync          # regenerate agent tool lists before starting
    python pnd.py --test          # run the hub (pytest) and client (vitest) tests
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUIREMENTS = ROOT / "requirements.txt"
REQS_STAMP = VENV / ".requirements-installed"
DIST_INDEX = UI / "dist" / "index.html"
CLIENT_URL = "http://localhost:5173"
WINDOWS = os.name == "nt"

# Vite's /api proxy is hard-wired to 8787 (ui/vite.config.ts), so the port is fixed here too.
# "py" commands run with the .venv interpreter from the repo root; the rest run in ui/.
SERVICES = {
    "server": {"cmd": ["py", "-m", "hub"], "color": "35", "port": 8787},  # magenta
    "client": {"cmd": ["npx", "vite"], "color": "36", "port": 5173},  # cyan
    # The desktop shell hosts the server itself; --dev points it at Vite (and the server at 8787).
    "desktop": {"cmd": ["py", "-m", "hub.desktop"], "color": "33", "port": None},  # yellow
    "desktop-dev": {"cmd": ["py", "-m", "hub.desktop", "--dev"], "color": "33", "port": 8787},
}

# Inputs to the client build: if any is newer than dist/index.html, rebuild.
BUILD_INPUTS = ["src", "public", "index.html", "vite.config.ts", "package.json"]

if WINDOWS:
    os.system("")  # turn on ANSI colour handling in the Windows console


def log(msg):
    print(f"\033[1m[pnd]\033[0m {msg}", flush=True)


def warn(msg):
    log(f"\033[33mwarning: {msg}\033[0m")


def fail(msg):
    log(f"\033[31m{msg}\033[0m")
    sys.exit(1)


def resolve_cmd(cmd):
    """Windows can't exec npm/npx directly (they're .cmd shims); resolve them to a full path."""
    if cmd[0] == "py":
        return [str(VENV_PY), *cmd[1:]]
    exe = shutil.which(cmd[0])
    if not exe:
        fail(f"`{cmd[0]}` not found on PATH.")
    return [exe, *cmd[1:]]


def run(cmd, **kw):
    subprocess.run(resolve_cmd(cmd), check=True, **kw)


def port_in_use(port):
    # The API binds 127.0.0.1; Vite binds "localhost", which may be ::1. Check both.
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            pass  # no IPv6 on this host
    return False


def check_mcp_config():
    """The shared knowledge base (pnd-notes) is launched from a path in .mcp.json; flag a stale one."""
    try:
        servers = json.loads((ROOT / ".mcp.json").read_text(encoding="utf8")).get("mcpServers", {})
    except (OSError, ValueError):
        return
    for name, cfg in servers.items():
        scripts = [a for a in cfg.get("args", []) if a.endswith((".mjs", ".js"))]
        for script in scripts:
            if not Path(script).exists():
                warn(f"MCP server `{name}` points at {script}, which doesn't exist here; agents won't reach it.")


def preflight(names, need_node):
    busy = [f"{n} ({SERVICES[n]['port']})" for n in names if SERVICES[n]["port"] and port_in_use(SERVICES[n]["port"])]
    if busy:
        fail(f"port already in use for {', '.join(busy)} -- is Endless Illusion already running?")
    if need_node:
        for tool in ("node", "npm"):
            if not shutil.which(tool):
                fail(f"`{tool}` not found on PATH (needed to build or serve the client).")
    claude_bin = os.environ.get("CLAUDE_BIN", "claude")
    if not shutil.which(claude_bin):
        warn(f"`{claude_bin}` not on PATH; runs will fail until it is (or set CLAUDE_BIN).")
    check_mcp_config()


def ensure_venv(force):
    """Create .venv on first run and (re)install requirements.txt whenever it changes."""
    if not VENV_PY.exists():
        log("creating the hub's virtual environment (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    stamp = REQS_STAMP.stat().st_mtime if REQS_STAMP.exists() else 0
    if force or REQUIREMENTS.stat().st_mtime > stamp:
        log("installing hub requirements (pip install -r requirements.txt)...")
        subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)], check=True)
        REQS_STAMP.touch()


def ensure_deps(force):
    if force or not (UI / "node_modules").is_dir():
        log("installing ui dependencies (npm install)...")
        run(["npm", "install"], cwd=UI)


def newest_mtime(path):
    if path.is_file():
        return path.stat().st_mtime
    if not path.is_dir():
        return 0
    return max((p.stat().st_mtime for p in path.rglob("*") if p.is_file()), default=0)


def build_needed(force):
    built = DIST_INDEX.stat().st_mtime if DIST_INDEX.exists() else 0
    return force or max(newest_mtime(UI / name) for name in BUILD_INPUTS) > built


def build_client():
    log("building the client (vite build)...")
    run(["npx", "vite", "build"], cwd=UI)


def sync_agent_tools():
    log("syncing agent tool lists...")
    run(["py", "-m", "hub.sync_agent_tools"], cwd=ROOT)


def run_tests():
    log("hub tests (pytest)...")
    hub = subprocess.run([str(VENV_PY), "-m", "pytest", "-q"], cwd=ROOT).returncode
    log("client tests (vitest)...")
    client = subprocess.run(resolve_cmd(["npx", "vitest", "run"]), cwd=UI).returncode
    sys.exit(hub or client)


def pump(name, color, proc):
    prefix = f"\033[{color}m[{name}]\033[0m "
    for line in proc.stdout:
        sys.stdout.write(prefix + line)
        sys.stdout.flush()


def start(name):
    svc = SERVICES[name]
    # Own process group, so stop() takes children (claude runs, MCP servers) with it.
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {"start_new_session": True}
    proc = subprocess.Popen(
        resolve_cmd(svc["cmd"]),
        cwd=ROOT if svc["cmd"][0] == "py" else UI,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **group,
    )
    threading.Thread(target=pump, args=(name, svc["color"], proc), daemon=True).start()
    log(f"started {name} (pid {proc.pid})")
    return proc


def kill_tree(proc, force):
    if proc.poll() is not None:
        return
    if WINDOWS:
        # No process groups to signal; taskkill /T walks the tree. Without /F it asks windows to close.
        flags = ["/T", "/F"] if force else ["/T"]
        subprocess.run(["taskkill", *flags, "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass


def stop(procs):
    for proc in procs.values():
        kill_tree(proc, force=False)
    deadline = time.time() + 5
    for proc in procs.values():
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            kill_tree(proc, force=True)


def on_sigterm(*_):
    raise KeyboardInterrupt  # VS Code's stop button sends SIGTERM; shut down the same way as Ctrl+C


def main():
    parser = argparse.ArgumentParser(description="Start the Endless Illusion ecosystem.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--web", action="store_true", help="browser setup (API + Vite) instead of the desktop app")
    mode.add_argument("--dev", action="store_true", help="desktop app on the Vite dev server, with hot reload")
    parser.add_argument("--only", choices=["server", "client"], help="with --web: start just one service")
    parser.add_argument("--rebuild", action="store_true", help="force a client build before opening the desktop app")
    parser.add_argument("--install", action="store_true", help="force npm install first")
    parser.add_argument("--sync", action="store_true", help="run sync-agent-tools.mjs first")
    parser.add_argument("--open", action="store_true", help="with --web: open the UI in a browser")
    parser.add_argument("--test", action="store_true", help="run the hub and client tests, then exit")
    args = parser.parse_args()
    if args.only and not args.web:
        parser.error("--only needs --web")
    if args.open and not args.web:
        parser.error("--open needs --web (the desktop app opens its own window)")

    if args.web:
        names = [args.only] if args.only else ["server", "client"]
    elif args.dev:
        names = ["desktop-dev", "client"]
    else:
        names = ["desktop"]

    if args.test:
        ensure_venv(args.install)
        ensure_deps(args.install)
        run_tests()

    rebuild = names == ["desktop"] and build_needed(args.rebuild)
    need_node = rebuild or "client" in names
    preflight(names, need_node)
    ensure_venv(args.install)
    if need_node:
        ensure_deps(args.install)
    if args.sync:
        sync_agent_tools()
    if rebuild:
        build_client()

    procs = {name: start(name) for name in names}

    if args.open and "client" in procs:
        threading.Timer(2.0, webbrowser.open, args=(CLIENT_URL,)).start()
    if args.web and "client" in procs:
        log(f"UI: {CLIENT_URL}")
    log("close the window or press Ctrl+C to stop." if not args.web else "Ctrl+C to stop.")

    signal.signal(signal.SIGTERM, on_sigterm)
    exit_code = 0
    try:
        while True:
            exited = [n for n, p in procs.items() if p.poll() is not None]
            if exited:
                exit_code = procs[exited[0]].returncode or 0
                log(f"{exited[0]} exited with code {exit_code}; shutting down.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        log("stopping...")
    finally:
        stop(procs)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
