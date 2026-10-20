#!/usr/bin/env python3
"""Start the Endless Illusion ecosystem.

Brings up the control plane in ui/: the Express API (server.mjs, 127.0.0.1:8787)
and the Vite client (http://localhost:5173), with their output interleaved and
prefixed. Ctrl+C stops both.

Usage:
    python3 pnd.py              # preflight, install deps if missing, start both
    python3 pnd.py --open       # ...and open the UI in the browser
    python3 pnd.py --sync       # regenerate agent tool lists before starting
    python3 pnd.py --only server|client
"""

import argparse
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
CLIENT_URL = "http://localhost:5173"

# Vite's /api proxy is hard-wired to 8787 (ui/vite.config.ts), so the port is fixed here too.
SERVICES = {
    "server": {"cmd": ["node", "server.mjs"], "color": "35", "port": 8787},  # magenta
    "client": {"cmd": ["npx", "vite"], "color": "36", "port": 5173},  # cyan
}


def log(msg):
    print(f"\033[1m[pnd]\033[0m {msg}", flush=True)


def fail(msg):
    log(f"\033[31m{msg}\033[0m")
    sys.exit(1)


def port_in_use(port):
    # The API binds 127.0.0.1; Vite binds "localhost", which is ::1 on macOS. Check both.
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family) as sock:
            if sock.connect_ex((host, port)) == 0:
                return True
    return False


def preflight(names):
    busy = [f"{n} ({SERVICES[n]['port']})" for n in names if port_in_use(SERVICES[n]["port"])]
    if busy:
        fail(f"port already in use for {', '.join(busy)} -- is Endless Illusion already running?")
    for tool in ("node", "npm"):
        if not shutil.which(tool):
            fail(f"`{tool}` not found on PATH.")
    claude_bin = os.environ.get("CLAUDE_BIN", "claude")
    if not shutil.which(claude_bin):
        log(f"\033[33mwarning: `{claude_bin}` not on PATH; runs will fail until it is (or set CLAUDE_BIN).\033[0m")


def ensure_deps(force):
    if force or not (UI / "node_modules").is_dir():
        log("installing ui dependencies (npm install)...")
        subprocess.run(["npm", "install"], cwd=UI, check=True)


def sync_agent_tools():
    log("syncing agent tool lists...")
    subprocess.run(["node", "ui/scripts/sync-agent-tools.mjs"], cwd=ROOT, check=True)


def pump(name, color, proc):
    prefix = f"\033[{color}m[{name}]\033[0m "
    for line in proc.stdout:
        sys.stdout.write(prefix + line)
        sys.stdout.flush()


def start(name):
    svc = SERVICES[name]
    proc = subprocess.Popen(
        svc["cmd"],
        cwd=UI,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,  # own process group, so stop() takes children with it
    )
    threading.Thread(target=pump, args=(name, svc["color"], proc), daemon=True).start()
    log(f"started {name} (pid {proc.pid})")
    return proc


def stop(procs):
    for proc in procs.values():
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.time() + 5
    for proc in procs.values():
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def on_sigterm(*_):
    raise KeyboardInterrupt  # VS Code's stop button sends SIGTERM; shut down the same way as Ctrl+C


def main():
    parser = argparse.ArgumentParser(description="Start the Endless Illusion ecosystem.")
    parser.add_argument("--only", choices=sorted(SERVICES), help="start just one service")
    parser.add_argument("--install", action="store_true", help="force npm install first")
    parser.add_argument("--sync", action="store_true", help="run sync-agent-tools.mjs first")
    parser.add_argument("--open", action="store_true", help="open the UI in a browser")
    args = parser.parse_args()

    names = [args.only] if args.only else list(SERVICES)
    preflight(names)
    ensure_deps(args.install)
    if args.sync:
        sync_agent_tools()

    procs = {name: start(name) for name in names}

    if args.open and "client" in procs:
        threading.Timer(2.0, webbrowser.open, args=(CLIENT_URL,)).start()
    if "client" in procs:
        log(f"UI: {CLIENT_URL}")
    log("Ctrl+C to stop.")

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
