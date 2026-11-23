#!/usr/bin/env python3
"""okay-dann CLI — run, stop, and restart Endless Illusion from any terminal.

Usage:
    okay-dann app [--rebuild]   desktop app (the default `python pnd.py`)
    okay-dann dev               desktop window on the Vite dev server (hot reload)
    okay-dann web [--open]      browser setup: hub API (:8787) + Vite (:5173)
    okay-dann chat [...]        Claude Code in this repo as Dann of Thursday
    okay-dann test              hub (pytest) + client (vitest) tests
    okay-dann status            what's running, and which ports are taken
    okay-dann stop              stop every Endless Illusion process, including orphans
    okay-dann restart           stop and relaunch with the same subcommand/flags

Install: ln -sf "$PWD/okay_dann.py" ~/.local/bin/okay-dann

Starting things is delegated to pnd.py (venv, npm install, client build,
preflight). This file adds the stop/restart/status layer on top. It is stdlib
only so it runs before .venv exists. stop/restart find processes with `ps`, so
they work on macOS/Linux only.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path, PurePath

ROOT = Path(__file__).resolve().parent
PND = ROOT / "pnd.py"
UI = ROOT / "ui"
PORTS = {"hub API": 8787, "Vite": 5173}

# How the launchers appear in a command line: this file, its symlink, or pnd.py.
LAUNCHER_NAMES = {"okay_dann.py", "okay-dann"}
PND_NAMES = {"pnd.py"}
# Control subcommands: never "Endless Illusion running", so never stopped or relaunched.
CONTROL = {"stop", "restart", "status"}
# One-shot runs: stoppable, but not something `restart` should relaunch.
ONE_SHOT = CONTROL | {"test", "chat"}

TAG = "\033[1;35m[okay-dann]\033[0m"


def say(msg: str) -> None:
    print(f"{TAG} {msg}", flush=True)


# --- process discovery (pure functions over argv lists, so they're testable) ---


def script_args(argv: list[str], names: set[str]) -> list[str] | None:
    """If `argv` is a Python interpreter running a script named in `names`,
    return the arguments after the script; otherwise None. Requiring a Python
    interpreter keeps `vim okay_dann.py` from matching."""
    if not argv or not PurePath(argv[0]).name.lower().startswith("python"):
        return None
    for i, arg in enumerate(argv[1:], start=1):
        if PurePath(arg).name in names:
            return argv[i + 1:]
        if not arg.startswith("-"):
            return None  # the interpreter is running some other script
    return None


def classify(argv: list[str], root: Path = ROOT, cwd: str | None = None) -> str | None:
    """'launcher' (okay-dann / pnd.py), 'service' (hub or Vite from this repo),
    or None if the process isn't Endless Illusion's.

    On macOS a venv's python re-execs the framework binary, so the hub's
    command line carries no repo path; it's matched by `cwd` instead."""
    launcher = script_args(argv, LAUNCHER_NAMES)
    if launcher is not None and (not launcher or launcher[0] not in CONTROL):
        return "launcher"
    if script_args(argv, PND_NAMES) is not None:
        return "launcher"
    joined = " ".join(argv)
    if is_hub(argv) and (joined.startswith(str(root / ".venv")) or cwd == str(root)):
        return "service"
    if str(root / "ui") in joined and "vite" in joined and "build" not in argv:
        return "service"
    return None


def is_hub(argv: list[str]) -> bool:
    """python -m hub / -m hub.desktop (with any trailing flags)."""
    return (
        bool(argv)
        and PurePath(argv[0]).name.lower().startswith("python")
        and any(argv[i] == "-m" and argv[i + 1] in ("hub", "hub.desktop") for i in range(len(argv) - 1))
    )


def process_cwd(pid: int) -> str | None:
    out = subprocess.run(["lsof", "-a", "-d", "cwd", "-p", str(pid), "-Fn"], capture_output=True, text=True).stdout
    return next((line[1:] for line in out.splitlines() if line.startswith("n")), None)


def list_processes() -> list[tuple[int, list[str]]]:
    """(pid, argv) for every process, via `ps`. Arguments containing spaces are
    split, which is fine for the path/flag matching done here."""
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=True).stdout
    procs = []
    for line in out.splitlines():
        pid, _, command = line.strip().partition(" ")
        if pid.isdigit():
            procs.append((int(pid), command.split()))
    return procs


def find_running(exclude: set[int] | None = None) -> list[tuple[int, str, list[str]]]:
    exclude = exclude or {os.getpid(), os.getppid()}
    found = []
    for pid, argv in list_processes():
        kind = classify(argv, cwd=process_cwd(pid) if is_hub(argv) else None)
        if kind and pid not in exclude:
            found.append((pid, kind, argv))
    return found


def restart_args(running: list[tuple[int, str, list[str]]]) -> list[str] | None:
    """okay-dann arguments that would relaunch what's running: an okay-dann
    launcher's own args, or a bare pnd.py run mapped to its subcommand."""
    for _, kind, argv in running:
        args = script_args(argv, LAUNCHER_NAMES)
        if kind == "launcher" and args and args[0] not in ONE_SHOT:
            return args
    for _, kind, argv in running:
        args = script_args(argv, PND_NAMES)
        if args is None:
            continue
        if "--web" in args:
            return ["web", *(["--open"] if "--open" in args else [])]
        if "--dev" in args:
            return ["dev"]
        return ["app"]
    return None


def port_in_use(port: int) -> bool:
    import socket

    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family) as sock:
                sock.settimeout(0.3)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            pass
    return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate(pids: list[int], timeout: float = 6.0) -> list[int]:
    """SIGTERM each pid (and its process group, if it leads one — pnd.py starts
    each service in its own session so claude runs and MCP servers go too),
    wait, then SIGKILL stragglers. Returns the pids that needed SIGKILL."""

    def signal_all(sig: int) -> None:
        for pid in pids:
            try:
                if os.getpgid(pid) == pid:
                    os.killpg(pid, sig)
                else:
                    os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    signal_all(signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline and any(alive(p) for p in pids):
        time.sleep(0.2)
    stragglers = [p for p in pids if alive(p)]
    if stragglers:
        pids = stragglers
        signal_all(signal.SIGKILL)
    return stragglers


# --- subcommands ---


def run_pnd(*flags: str) -> int:
    """Run pnd.py in the foreground (Ctrl+C reaches both, as they share the
    terminal's process group). A child rather than exec, so this okay-dann
    command line, with its subcommand, stays visible for `restart` to read."""
    os.chdir(ROOT)
    proc = subprocess.run([sys.executable, str(PND), *flags])
    return proc.returncode


def cmd_app(args) -> int:
    return run_pnd(*(["--rebuild"] if args.rebuild else []))


def cmd_dev(args) -> int:
    return run_pnd("--dev")


def cmd_web(args) -> int:
    return run_pnd("--web", *(["--open"] if args.open else []))


def cmd_test(args) -> int:
    return run_pnd("--test")


def cmd_chat(args) -> int:
    os.chdir(ROOT)
    claude = os.environ.get("CLAUDE_BIN", "claude")
    try:
        os.execvp(claude, [claude, "--agent", "dann-of-thursday", *args.extra])
    except FileNotFoundError:
        say(f"`{claude}` not found on PATH (or set CLAUDE_BIN).")
        return 1


def cmd_status(args) -> int:
    running = find_running()
    if not running:
        say("Nothing running.")
    for pid, kind, argv in running:
        print(f"  {pid:>7}  {kind:<8}  {' '.join(argv)[:110]}")
    for name, port in PORTS.items():
        print(f"  :{port:<6} {name:<8}  {'in use' if port_in_use(port) else 'free'}")
    return 0


def cmd_stop(args=None) -> int:
    running = find_running()
    if not running:
        say("Nothing running.")
        return 0
    # Launchers first: pnd.py's own shutdown takes its services' process groups down cleanly.
    launchers = [pid for pid, kind, _ in running if kind == "launcher"]
    say(f"Stopping {len(running)} process(es): {[pid for pid, _, _ in running]}")
    killed = terminate(launchers) if launchers else []
    orphans = [pid for pid, kind, _ in running if kind == "service" and alive(pid)]
    if orphans:
        killed += terminate(orphans)
    if killed:
        say(f"Force-killed {len(killed)} that didn't exit cleanly: {killed}")
    say("Stopped.")
    return 0


def cmd_restart(args) -> int:
    relaunch = restart_args(find_running())
    if not relaunch:
        say("Nothing running to restart — use `okay-dann app`, `dev`, or `web`.")
        return 1
    say(f"Restarting with: okay-dann {' '.join(relaunch)}")
    cmd_stop()
    time.sleep(1)  # let the OS release :8787/:5173 before pnd.py's preflight checks them
    return main(relaunch)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="okay-dann",
        description="Run, stop, and restart Endless Illusion.",
        epilog="Starting is delegated to pnd.py; `python pnd.py --help` lists its flags.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    app = sub.add_parser("app", aliases=["start"], help="desktop app (python pnd.py)")
    app.add_argument("--rebuild", action="store_true", help="force a client build first")
    app.set_defaults(run=cmd_app)

    sub.add_parser("dev", aliases=["code"], help="desktop window on the Vite dev server").set_defaults(run=cmd_dev)

    web = sub.add_parser("web", help="browser setup: hub API (:8787) + Vite (:5173)")
    web.add_argument("--open", action="store_true", help="open the UI in a browser")
    web.set_defaults(run=cmd_web)

    chat = sub.add_parser("chat", help="Claude Code in this repo as Dann of Thursday")
    chat.add_argument("extra", nargs=argparse.REMAINDER, help="passed through to claude")
    chat.set_defaults(run=cmd_chat)

    sub.add_parser("test", help="hub + client tests").set_defaults(run=cmd_test)
    sub.add_parser("status", help="show running processes and ports").set_defaults(run=cmd_status)
    sub.add_parser("stop", help="stop every Endless Illusion process, including orphans").set_defaults(run=cmd_stop)
    sub.add_parser("restart", help="stop and relaunch with the same subcommand/flags").set_defaults(run=cmd_restart)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.run(args) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
