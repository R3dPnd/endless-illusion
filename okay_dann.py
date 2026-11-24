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
    okay-dann backup setup      store Cloudflare R2 credentials for Litestream
    okay-dann backup status     replication status and the newest backups
    okay-dann backup now        one immediate sync (when the hub isn't running)
    okay-dann backup restore    restore the hub database from R2
    okay-dann lab start|stop|status   OWASP Juice Shop on 127.0.0.1:3000 (local rehearsal target)

Backups: once `backup setup` has run, app/dev/web also run `litestream
replicate` beside the hub, continuously streaming data/endless-illusion.db to
R2 (litestream.yml). Credentials live in litestream.env, which is gitignored.

Install: ln -sf "$PWD/okay_dann.py" ~/.local/bin/okay-dann

Starting things is delegated to pnd.py (venv, npm install, client build,
preflight). This file adds the stop/restart/status layer on top. It is stdlib
only so it runs before .venv exists. stop/restart find processes with `ps`, so
they work on macOS/Linux only.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import tarfile
import threading
import urllib.request
import zipfile
import signal
import subprocess
import sys
import time
from pathlib import Path, PurePath

ROOT = Path(__file__).resolve().parent
PND = ROOT / "pnd.py"
UI = ROOT / "ui"
LAB_DIR = Path.home() / ".local" / "share" / "endless-illusion" / "juice-shop"
LAB_PORT = 3000
LAB_HOST = "127.0.0.1"
LAB_URL = f"http://{LAB_HOST}:{LAB_PORT}/"
LAB_RELEASES = "https://api.github.com/repos/juice-shop/juice-shop/releases/latest"
PORTS = {"hub API": 8787, "Vite": 5173}
DB_PATH = ROOT / "data" / "endless-illusion.db"
LITESTREAM_CONFIG = ROOT / "litestream.yml"
LITESTREAM_ENV = ROOT / "litestream.env"  # gitignored (*.env)
# What `backup setup` asks for, in order: (key, prompt, secret?)
BACKUP_FIELDS = [
    ("R2_ACCOUNT_ID", "Cloudflare account ID", False),
    ("R2_BUCKET", "R2 bucket name", False),
    ("LITESTREAM_ACCESS_KEY_ID", "R2 API token Access Key ID", False),
    ("LITESTREAM_SECRET_ACCESS_KEY", "R2 API token Secret Access Key", True),
]

# How the launchers appear in a command line: this file, its symlink, or pnd.py.
LAUNCHER_NAMES = {"okay_dann.py", "okay-dann"}
PND_NAMES = {"pnd.py"}
# Control subcommands: never "Endless Illusion running", so never stopped or relaunched.
CONTROL = {"stop", "restart", "status", "backup", "lab"}
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
    if is_litestream(argv, root):
        return "service"
    if is_lab(argv):
        return "service"
    return None


def is_lab(argv: list[str]) -> bool:
    """`node <lab dir>/<ver>/juice-shop_*/build/app.js`: the local Juice Shop."""
    return (
        len(argv) >= 2
        and PurePath(argv[0]).name == "node"
        and any(arg.startswith(str(LAB_DIR) + os.sep) and arg.endswith("app.js") for arg in argv[1:])
    )


def is_litestream(argv: list[str], root: Path = ROOT) -> bool:
    """`litestream replicate -config <this repo>/litestream.yml` (not -once)."""
    return (
        bool(argv)
        and PurePath(argv[0]).name == "litestream"
        and "replicate" in argv
        and "-once" not in argv
        and str(root / "litestream.yml") in argv
    )


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


# --- Juice Shop lab (a deliberately vulnerable app the operator owns) ---

# Juice Shop calls server.listen(port) with no host, so it binds every interface,
# and it has no config option for the bind address. This preload (our own file,
# loaded with NODE_OPTIONS=--require; Juice Shop's code is untouched) makes any
# listen() that names no host use 127.0.0.1.
BIND_SHIM = """\
'use strict'
const net = require('net')
const HOST = process.env.EI_BIND_HOST || '127.0.0.1'
const WILDCARDS = new Set(['', '0.0.0.0', '::', '::0', '0:0:0:0:0:0:0:0'])
const wide = (h) => h === undefined || h === null || (typeof h === 'string' && WILDCARDS.has(h))
const orig = net.Server.prototype.listen
net.Server.prototype.listen = function (...args) {
  const first = args[0]
  if (typeof first === 'number' || (typeof first === 'string' && /^[0-9]+$/.test(first))) {
    if (typeof args[1] === 'string') {
      if (wide(args[1])) args[1] = HOST
    } else {
      args.splice(1, 0, HOST)
    }
  } else if (first && typeof first === 'object' && first.path === undefined &&
             first.fd === undefined && first.handle === undefined && wide(first.host)) {
    args[0] = { ...first, host: HOST }
  }
  return orig.apply(this, args)
}
"""


def lab_release_asset(version: str, node_major: int, machine: str, system: str = "darwin") -> str:
    """Packaged-release file name, e.g. juice-shop-20.4.0_node26_darwin_arm64.zip
    (macOS and Windows ship zips, Linux tgz)."""
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64"}.get(machine.lower(), machine.lower())
    ext = "tgz" if system == "linux" else "zip"
    return f"juice-shop-{version}_node{node_major}_{system}_{arch}.{ext}"


def lab_pick_node_major(asset_names: list[str], local_major: int, machine: str, system: str = "darwin") -> int | None:
    """Highest Node major with a published package for this OS/arch that is <= the local one."""
    for major in range(local_major, 0, -1):
        tail = lab_release_asset("0", major, machine, system).split("0_", 1)[1]
        if any(name.startswith("juice-shop-") and name.endswith("_" + tail) for name in asset_names):
            return major
    return None


def lab_app_dir() -> Path | None:
    """The installed Juice Shop directory (newest version), or None."""
    found = sorted(LAB_DIR.glob("[0-9]*/juice-shop_*/build/app.js"), key=lambda p: [int(x) for x in re.findall(r"\d+", p.parts[-4])])
    return found[-1].parent.parent if found else None


def node_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-v"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)", out)
    return int(m.group(1)) if m else None


def lab_valid_tag(tag: object) -> bool:
    """A release tag is used as a directory name, so only accept plain versions."""
    return isinstance(tag, str) and re.fullmatch(r"v?\d+(\.\d+)*", tag) is not None


def lab_digest_ok(archive: Path, asset: dict) -> bool:
    """True only if the release publishes a SHA-256 for the asset and it matches."""
    expected = (asset.get("digest") or "").removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        say(f"no published SHA-256 for {asset.get('name')}; not installing")
        return False
    h = hashlib.sha256()
    with open(archive, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        say(f"SHA-256 mismatch for {asset.get('name')} (expected {expected}, got {h.hexdigest()}); not installing.")
        return False
    say(f"SHA-256 verified ({expected[:16]}...).")
    return True


def lab_install() -> Path | None:
    """Download (into a fresh directory), verify, and extract the packaged release."""
    try:
        return _lab_install()
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        say(f"Juice Shop install failed: {type(exc).__name__}: {exc}")
        return None


def _lab_install() -> Path | None:
    local = node_major()
    if local is None:
        say("`node` isn't on PATH; Juice Shop needs it.")
        return None
    system, machine = platform.system().lower(), platform.machine()
    say("Looking up the latest Juice Shop release...")
    request = urllib.request.Request(LAB_RELEASES, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        release = json.load(resp)
    tag = release["tag_name"]
    if not lab_valid_tag(tag):
        say(f"Unexpected release tag {tag!r}; not installing.")
        return None
    version = tag.lstrip("v")
    assets = {a["name"]: a for a in release["assets"]}
    major = lab_pick_node_major(list(assets), local, machine, system)
    if major is None:
        say(f"Release {version} has no package for {system}/{machine} with Node <= {local}.")
        return None
    if major != local:
        say(f"WARNING: no Juice Shop package for Node {local}; using the Node {major} build. It may not start.")
    name = lab_release_asset(version, major, machine, system)
    asset = assets[name]
    downloads = LAB_DIR / "downloads" / version
    if downloads.exists():
        shutil.rmtree(downloads)  # always a fresh, empty directory
    downloads.mkdir(parents=True)
    archive = downloads / name
    say(f"Downloading {name}...")
    with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as resp, open(archive, "wb") as out:
        shutil.copyfileobj(resp, out)
    if not lab_digest_ok(archive, asset):
        return None
    target = LAB_DIR / version
    staging = LAB_DIR / f".staging-{version}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(staging)  # zipfile drops absolute and `..` member paths
        else:
            with tarfile.open(archive) as t:
                t.extractall(staging, filter="data")
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return lab_app_dir()


def lab_listening() -> bool:
    """Is anything accepting on 127.0.0.1:3000? IPv4 only: another project's dev
    server on [::1]:3000 doesn't stop Juice Shop binding 127.0.0.1."""
    import socket

    with socket.socket(socket.AF_INET) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((LAB_HOST, LAB_PORT)) == 0


def lab_pids() -> list[int]:
    return [pid for pid, _, argv in find_running() if is_lab(argv)]


def lab_bad_sockets(pid: int) -> list[str]:
    """Listening sockets of `pid` that are not 127.0.0.1:<LAB_PORT> (lsof -Fn names)."""
    out = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{LAB_PORT}", "-sTCP:LISTEN", "-a", "-p", str(pid), "-Fn"], capture_output=True, text=True
    ).stdout
    names = [line[1:] for line in out.splitlines() if line.startswith("n")]
    return [n for n in names if n != f"{LAB_HOST}:{LAB_PORT}"]


def cmd_lab_start(args) -> int:
    if lab_pids() and lab_listening():
        say(f"Juice Shop is already up at {LAB_URL}.")
        return 0
    if lab_listening():
        say(f"Something else already listens on {LAB_HOST}:{LAB_PORT}; not starting.")
        return 1
    app = lab_app_dir() or lab_install()
    if app is None:
        return 1
    LAB_DIR.mkdir(parents=True, exist_ok=True)
    shim = LAB_DIR / "bind-localhost.cjs"
    shim.write_text(BIND_SHIM, encoding="utf8")
    env = {k: v for k, v in os.environ.items() if k != "NODE_ENV"}
    node_options = f"{env['NODE_OPTIONS']} " if env.get("NODE_OPTIONS") else ""
    env.update(PORT=str(LAB_PORT), EI_BIND_HOST=LAB_HOST, NODE_OPTIONS=f'{node_options}--require "{shim}"')
    log = LAB_DIR / "juice-shop.log"
    with open(log, "ab") as logfile:
        proc = subprocess.Popen(
            [shutil.which("node"), str(app / "build" / "app.js")],
            cwd=app, env=env, stdin=subprocess.DEVNULL, stdout=logfile, stderr=subprocess.STDOUT, start_new_session=True,
        )
    say(f"Starting Juice Shop (pid {proc.pid}), log: {log}")
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            say(f"Juice Shop exited with code {proc.returncode}; see {log}")
            return 1
        if lab_listening():
            bad = lab_bad_sockets(proc.pid)
            if bad:
                terminate([proc.pid])
                say(f"Juice Shop listened on {bad}, not {LAB_HOST} only; stopped it.")
                return 1
            say(f"Juice Shop is up at {LAB_URL} (bound to {LAB_HOST} only).")
            return 0
        time.sleep(0.5)
    terminate([proc.pid])
    say(f"Juice Shop didn't open :{LAB_PORT} within 90s; stopped it. See {log}")
    return 1


def cmd_lab_stop(args) -> int:
    pids = lab_pids()
    if pids:
        terminate(pids)
        say(f"Stopped Juice Shop ({pids}).")
    else:
        say("Juice Shop isn't running.")
    return 0


def cmd_lab_status(args) -> int:
    say(f"Juice Shop: {'up' if lab_listening() and lab_pids() else 'down'}  {LAB_URL}")
    return 0


# --- Litestream (backup to Cloudflare R2) ---


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; blank lines and # comments ignored, optional quotes stripped."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("'\"")
    return env


def replica_url(env: dict[str, str]) -> str | None:
    """EI_REPLICA_URL if set (any Litestream URL, e.g. file:// for testing),
    otherwise the R2 bucket built from the account ID and bucket name."""
    if env.get("EI_REPLICA_URL"):
        return env["EI_REPLICA_URL"]
    account, bucket = env.get("R2_ACCOUNT_ID"), env.get("R2_BUCKET")
    if not (account and bucket):
        return None
    return f"s3://{bucket}/endless-illusion?endpoint=https://{account}.r2.cloudflarestorage.com&region=auto"


def litestream_env(file_env: dict[str, str] | None = None, base: dict[str, str] | None = None) -> dict[str, str] | None:
    """Environment for litestream (litestream.yml reads it via ${VAR}), or None
    when backups aren't configured. Shell variables override the file."""
    env = {**(read_env_file(LITESTREAM_ENV) if file_env is None else file_env), **{
        k: v for k, v in (os.environ if base is None else base).items()
        if k.startswith(("R2_", "LITESTREAM_", "EI_REPLICA_URL"))
    }}
    url = replica_url(env)
    if not url:
        return None
    if url.startswith("s3://") and not (env.get("LITESTREAM_ACCESS_KEY_ID") and env.get("LITESTREAM_SECRET_ACCESS_KEY")):
        return None
    env.setdefault("LITESTREAM_ACCESS_KEY_ID", "")
    env.setdefault("LITESTREAM_SECRET_ACCESS_KEY", "")
    return {**(os.environ if base is None else base), **env, "EI_REPLICA_URL": url, "EI_DB_PATH": str(DB_PATH)}


def litestream(command: str, *args: str, env: dict[str, str], **kw) -> subprocess.CompletedProcess:
    """`litestream <command> -config litestream.yml <args>`: flags must precede any DB path."""
    return subprocess.run(["litestream", command, "-config", str(LITESTREAM_CONFIG), *args], env=env, **kw)


def start_replication() -> subprocess.Popen | None:
    """Start continuous replication beside the hub, if backups are configured.
    Its own session, so Ctrl+C reaches pnd.py first and litestream is stopped
    afterwards — catching the hub's final writes on the way out."""
    env = litestream_env()
    if env is None:
        return None
    if not shutil.which("litestream"):
        say("backups are configured but `litestream` isn't on PATH; running without them.")
        return None
    if any(kind == "service" and is_litestream(argv) for _, kind, argv in find_running()):
        return None  # another launcher is already replicating
    proc = subprocess.Popen(
        ["litestream", "replicate", "-config", str(LITESTREAM_CONFIG)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
    )

    def pump() -> None:
        for line in proc.stdout:
            print(f"\033[32m[backup]\033[0m {line}", end="", flush=True)

    threading.Thread(target=pump, daemon=True).start()
    say(f"backing up the hub database to {env['EI_REPLICA_URL'].split('?')[0]} (pid {proc.pid})")
    return proc


def run_pnd(*flags: str, backup: bool = True) -> int:
    """Run pnd.py in the foreground (Ctrl+C reaches both, as they share the
    terminal's process group), with Litestream beside it when configured. A
    child rather than exec, so this okay-dann command line, with its
    subcommand, stays visible for `restart` to read."""
    os.chdir(ROOT)
    replication = start_replication() if backup else None

    # Ctrl+C and `okay-dann stop` both reach pnd.py directly (same terminal
    # process group / it's in stop's target list), so here we only keep
    # waiting for pnd.py's own shutdown, then stop litestream after it.
    signal.signal(signal.SIGTERM, lambda *_: None)
    proc = subprocess.Popen([sys.executable, str(PND), *flags])
    try:
        while True:
            try:
                return proc.wait()
            except KeyboardInterrupt:
                continue
    finally:
        if proc.poll() is None:
            terminate([proc.pid])
        if replication is not None:
            terminate([replication.pid], timeout=15)  # litestream flushes pending WAL on SIGTERM


def cmd_app(args) -> int:
    return run_pnd(*(["--rebuild"] if args.rebuild else []))


def cmd_dev(args) -> int:
    return run_pnd("--dev")


def cmd_web(args) -> int:
    return run_pnd("--web", *(["--open"] if args.open else []))


def cmd_test(args) -> int:
    return run_pnd("--test", backup=False)


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
    print(f"  :{LAB_PORT:<6} {'Juice Shop':<8}  {'up' if lab_listening() and lab_pids() else 'down'} ({LAB_URL})")
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


def require_backup_env() -> dict[str, str] | None:
    if not shutil.which("litestream"):
        say("`litestream` isn't on PATH. Install it: https://litestream.io/install/")
        return None
    env = litestream_env()
    if env is None:
        say("Backups aren't configured yet — run `okay-dann backup setup`.")
    return env


def replicating_now() -> bool:
    return any(is_litestream(argv) for _, _, argv in find_running())


def cmd_backup_setup(args) -> int:
    current = read_env_file(LITESTREAM_ENV)
    say("Store R2 credentials for Litestream (written to litestream.env, mode 600, gitignored).")
    print("  Create the bucket and an R2 API token with Object Read & Write on that bucket only:")
    print("  Cloudflare dashboard → R2 → Create bucket, then R2 → Manage API tokens.")
    values = {}
    for key, prompt, secret in BACKUP_FIELDS:
        have = current.get(key, "")
        hint = " [keep current]" if secret and have else (f" [{have}]" if have else "")
        ask = getpass.getpass if secret else input
        values[key] = ask(f"  {prompt}{hint}: ").strip() or have
        if not values[key]:
            say(f"{prompt} is required; nothing written.")
            return 1
    LITESTREAM_ENV.write_text(
        "# Litestream → Cloudflare R2 credentials for okay-dann. Never commit.\n"
        + "".join(f"{k}={v}\n" for k, v in values.items()),
        encoding="utf8",
    )
    LITESTREAM_ENV.chmod(0o600)
    say(f"Saved {LITESTREAM_ENV.name}. Run `okay-dann backup now` to take the first backup.")
    return 0


def cmd_backup_status(args) -> int:
    env = require_backup_env()
    if env is None:
        return 1
    say(f"replica: {env['EI_REPLICA_URL'].split('?')[0]}")
    say("continuous replication: " + ("running" if replicating_now() else "not running (starts with app/dev/web)"))
    status = litestream("status", env=env).returncode
    say("snapshots on the replica:")
    ltx = litestream("ltx", "-level", "9", str(DB_PATH), env=env).returncode
    return status or ltx


def cmd_backup_now(args) -> int:
    env = require_backup_env()
    if env is None:
        return 1
    if replicating_now():
        say("Already replicating continuously beside the hub; nothing to do.")
        return 0
    if not DB_PATH.exists():
        say(f"No database at {DB_PATH} yet — start the hub once first.")
        return 1
    say("Syncing the hub database to the replica...")
    code = litestream("replicate", "-once", "-force-snapshot", env=env).returncode
    say("Done." if code == 0 else f"litestream exited with code {code}.")
    return code


def cmd_backup_restore(args) -> int:
    env = require_backup_env()
    if env is None:
        return 1
    if args.in_place:
        if find_running():
            say("Stop Endless Illusion first (`okay-dann stop`): restoring in place under a live hub corrupts it.")
            return 1
        out = DB_PATH
    else:
        out = Path(args.to) if args.to else ROOT / "data" / "restored" / f"endless-illusion-{time.strftime('%Y%m%d-%H%M%S')}.db"
    out.parent.mkdir(parents=True, exist_ok=True)
    flags = ["-o", str(out)]
    if args.timestamp:
        flags += ["-timestamp", args.timestamp]
    if args.dry_run:
        flags.append("-dry-run")
    if out == DB_PATH and DB_PATH.exists() and not args.dry_run:
        backup = DB_PATH.with_name(f"endless-illusion.pre-restore-{time.strftime('%Y%m%d-%H%M%S')}.db")
        for suffix in ("", "-wal", "-shm"):
            src = Path(f"{DB_PATH}{suffix}")
            if src.exists():
                shutil.move(src, f"{backup}{suffix}")
        say(f"Moved the current database aside to {backup.name}")
    code = litestream("restore", *flags, str(DB_PATH), env=env).returncode
    if code == 0 and not args.dry_run:
        say(f"Restored to {out}")
    return code


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

    backup = sub.add_parser("backup", help="Litestream backups of the hub database to Cloudflare R2")
    backup_sub = backup.add_subparsers(dest="backup_command", metavar="<action>", required=True)
    backup_sub.add_parser("setup", help="store R2 credentials in litestream.env").set_defaults(run=cmd_backup_setup)
    backup_sub.add_parser("status", help="replication status and snapshots on R2").set_defaults(run=cmd_backup_status)
    backup_sub.add_parser("now", help="one immediate sync (when the hub isn't running)").set_defaults(run=cmd_backup_now)
    restore = backup_sub.add_parser("restore", help="restore the hub database from R2")
    restore.add_argument("--to", help="output path (default: data/restored/endless-illusion-<time>.db)")
    restore.add_argument("--in-place", action="store_true", help="replace data/endless-illusion.db (hub must be stopped; the old one is kept aside)")
    restore.add_argument("--timestamp", help="point in time to restore to, e.g. 2026-11-23T14:00:00Z")
    restore.add_argument("--dry-run", action="store_true", help="print the restore plan only")
    restore.set_defaults(run=cmd_backup_restore)

    lab = sub.add_parser("lab", help="OWASP Juice Shop on 127.0.0.1:3000 (local rehearsal target)")
    lab_sub = lab.add_subparsers(dest="lab_command", metavar="<action>", required=True)
    lab_sub.add_parser("start", help="install on first use, then start in the background").set_defaults(run=cmd_lab_start)
    lab_sub.add_parser("stop", help="stop Juice Shop").set_defaults(run=cmd_lab_stop)
    lab_sub.add_parser("status", help="up/down and URL").set_defaults(run=cmd_lab_status)
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
