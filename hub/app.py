"""
HTTP API for the control plane (stdlib only). Binds to loopback; the UI talks
to it directly (desktop shell) or through Vite's /api proxy (browser dev).
"""

import json
import mimetypes
import queue
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import REPO_ROOT
from .db import open_db
from .db.archive import get_run, get_run_events, list_runs, mark_interrupted, to_json
from .db.bounties import (
    HttpError,
    add_program,
    confirm_proposal,
    dismiss_lead,
    list_bounties,
    reject_proposal,
    require_confirmed_snapshot,
    track_lead,
)
from .db.read import current, parse_json
from .policies import load_policies
from .runner import Runner

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8787", "http://127.0.0.1:8787")
MAX_BODY = 1024 * 1024
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/ttf", ".ttf")


# ---- archive views ----------------------------------------------------------


def findings(db):
    rows = [
        {**r, "kind": kind}
        for kind in ("web", "api")
        for r in db.all(f"SELECT * FROM {kind}_findings t WHERE {current(f'{kind}_findings')}")
    ]
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    rows.sort(key=lambda r: SEVERITY_RANK.get(r["severity"], 9))
    return rows


def cve_notes(db):
    return [
        {**r, "kev": bool(r["kev"]), "public_exploit": bool(r["public_exploit"]), "sources": parse_json(r["sources"], [])}
        for r in db.all(f"SELECT * FROM cve_notes t WHERE {current('cve_notes')} ORDER BY t.created_at DESC")
    ]


def submissions(db):
    rows = db.all(
        f"""SELECT t.*, p.name AS program_name, p.url AS program_url FROM submissions t
            JOIN programs p ON p.id = t.program_id
            WHERE {current('submissions')} ORDER BY t.created_at DESC"""
    )
    return [{**r, "finding_refs": parse_json(r["finding_refs"], [])} for r in rows]


def export_submission(db, repo_root, sub_id):
    """Fill the engagement-report header for a submission and append Sen's body."""
    sub = next((s for s in submissions(db) if s["id"] == sub_id), None)
    if not sub:
        raise HttpError(404, f"no submission {sub_id}")
    snap = db.get("SELECT id, confirmed_at FROM scope_snapshots WHERE program_id = ? ORDER BY confirmed_at DESC LIMIT 1", sub["program_id"])
    template = (Path(repo_root) / "templates" / "engagement-report.md").read_text(encoding="utf8")
    header = template[: template.find("## Summary")].rstrip()
    basis = (
        f"{sub['program_name']} ({sub['program_url']}), scope snapshot #{snap['id']} confirmed {snap['confirmed_at'][:10]}"
        if snap
        else f"{sub['program_name']} ({sub['program_url']}) — no confirmed scope snapshot"
    )
    filled = (
        header.replace("<name>", f"{sub['program_name']} — {sub['title']}", 1)
        .replace("<YYYY-MM-DD>", sub["created_at"][:10], 1)
        .replace("<codenames>", sub["agent"], 1)
        .replace("<in-scope assets>", sub["program_url"], 1)
        .replace("<contract / bounty program + link / written permission reference>", basis, 1)
        .replace("<summary>", "See program scope snapshot.", 1)
    )
    return f"{filled}\n\n## {sub['title']}\n\n- **Severity:** {sub['severity']}\n\n{sub['body_markdown']}\n"


def _proposal_id(value):
    if not re.fullmatch(r"-?\d+", value):
        raise HttpError(400, "bad proposal id")
    return int(value)


def _lead_url(body):
    url = body.get("normalizedUrl")
    if not isinstance(url, str) or not url:
        raise HttpError(400, "normalizedUrl is required")
    return url


# ---- the hub ----------------------------------------------------------------


class Hub:
    """Database, run manager, and HTTP routes. Serving is `serve()`'s job."""

    def __init__(
        self,
        repo_root=REPO_ROOT,
        data_dir=None,
        db_file=None,
        claude_cmd="claude",
        static_dir=None,
        allowed_origins=DEFAULT_ORIGINS,
        prefs_file=None,
        index_bootstrap=None,
    ):
        self.repo_root = Path(repo_root)
        self.data_dir = Path(data_dir) if data_dir else self.repo_root / "data"
        self.db_file = Path(db_file) if db_file else self.data_dir / "endless-illusion.db"
        self.static_dir = Path(static_dir).resolve() if static_dir else None
        self.allowed_origins = set(allowed_origins)
        self.prefs_file = Path(prefs_file) if prefs_file else None
        self.index_bootstrap = index_bootstrap  # callable -> dict injected as window.__EI_DESKTOP__

        self.db = open_db(self.db_file)
        interrupted = mark_interrupted(self.db)
        if interrupted:
            print(f"[archive] marked {interrupted} unfinished run(s) interrupted")
        self.runner = Runner(self.db, self.db_file, self.data_dir, claude_cmd, self.repo_root)

        db = self.db
        # (method, pattern, handler(match, query, body) -> JSON-able | None)
        self.routes = [
            ("GET", r"/api/agents", lambda m, q, b: load_policies(self.repo_root / "agents")),
            ("POST", r"/api/runs", lambda m, q, b: self.start_run(b)),
            ("POST", r"/api/runs/([^/]+)/stop", lambda m, q, b: self.stop_run(m.group(1))),
            ("GET", r"/api/runs", lambda m, q, b: list_runs(db, **q)),
            ("GET", r"/api/runs/([^/]+)", lambda m, q, b: self.run_detail(m.group(1))),
            ("GET", r"/api/findings", lambda m, q, b: findings(db)),
            ("GET", r"/api/cve-notes", lambda m, q, b: cve_notes(db)),
            ("GET", r"/api/submissions", lambda m, q, b: submissions(db)),
            ("GET", r"/api/bounties", lambda m, q, b: list_bounties(db)),
            ("POST", r"/api/programs", lambda m, q, b: {"programId": add_program(db, **_str_keys(b))}),
            ("POST", r"/api/leads/track", lambda m, q, b: {"programId": track_lead(db, _lead_url(b))}),
            ("POST", r"/api/leads/dismiss", lambda m, q, b: dismiss_lead(db, _lead_url(b))),
            ("POST", r"/api/proposals/([^/]+)/confirm", lambda m, q, b: {"snapshotId": confirm_proposal(db, _proposal_id(m.group(1)))}),
            ("POST", r"/api/proposals/([^/]+)/reject", lambda m, q, b: reject_proposal(db, _proposal_id(m.group(1)))),
        ]
        if self.prefs_file:
            self.routes += [
                ("GET", r"/api/display-prefs", lambda m, q, b: self.read_prefs()),
                ("POST", r"/api/display-prefs", lambda m, q, b: self.write_prefs(b)),
            ]
        self.routes = [(method, re.compile(f"^{pattern}$"), fn) for method, pattern, fn in self.routes]

    def start_run(self, body):
        link = {}
        if body.get("programId") is not None:
            link = {"programId": int(body["programId"]), "snapshotId": require_confirmed_snapshot(self.db, body["programId"])}
        try:
            return self.runner.start(body, link).public()
        except ValueError as err:
            raise HttpError(400, str(err)) from err

    def stop_run(self, run_id):
        run = self.runner.stop(run_id)
        if not run:
            raise HttpError(404, "no such run")
        return {"status": run.status}

    def run_detail(self, run_id):
        run = get_run(self.db, run_id)
        if not run:
            raise HttpError(404, "no such run")
        reports = self.db.all("SELECT id, agent, kind, text, meta, created_at FROM reports WHERE run_id = ? ORDER BY id", run_id)
        return {**run, "reports": [{**r, "meta": parse_json(r["meta"], None)} for r in reports]}

    def read_prefs(self):
        try:
            return json.loads(self.prefs_file.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return None

    def write_prefs(self, body):
        self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
        self.prefs_file.write_text(json.dumps(body, indent=2), encoding="utf8")

    def serve(self, host="127.0.0.1", port=8787):
        """Bind and return the server; call serve_forever() (or run it in a thread)."""
        hub = self

        class Handler(HubHandler):
            pass

        Handler.hub = hub
        server = ThreadingHTTPServer((host, port), Handler)
        server.daemon_threads = True
        return server


def _str_keys(body):
    return {str(k): v for k, v in body.items()} if isinstance(body, dict) else {}


class HubHandler(BaseHTTPRequestHandler):
    hub: Hub
    server_version = "EndlessIllusion"

    def log_message(self, fmt, *args):
        pass  # quiet; errors are printed where they happen

    # ---- responses ----
    def send_body(self, status, body, content_type, headers=None):
        data = body.encode("utf8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status, value):
        self.send_body(status, to_json(value), "application/json; charset=utf-8")

    # ---- dispatch ----
    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        url = urlsplit(self.path)
        path = unquote(url.path)
        try:
            if path.startswith("/api/"):
                return self.api(method, path, url.query)
            if method == "GET" and self.hub.static_dir:
                return self.static(path)
            self.send_json(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def api(self, method, path, raw_query):
        hub = self.hub
        if method == "POST":
            # Cross-site guard: any page the operator visits could otherwise POST here.
            # A JSON content type forces a CORS preflight (never granted), and a present
            # Origin must be one of ours. Requests without an Origin (curl, tools) pass.
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                return self.send_json(415, {"error": "content-type must be application/json"})
            origin = self.headers.get("Origin")
            if origin and origin not in hub.allowed_origins:
                return self.send_json(403, {"error": f"origin {origin} not allowed"})

        m = re.fullmatch(r"/api/runs/([^/]+)/events", path)
        if method == "GET" and m:
            return self.events(m.group(1))
        m = re.fullmatch(r"/api/submissions/(\d+)/export", path)
        if method == "GET" and m:
            try:
                md = export_submission(hub.db, hub.repo_root, int(m.group(1)))
            except HttpError as err:
                return self.send_json(err.status, {"error": str(err)})
            return self.send_body(
                200, md, "text/markdown; charset=utf-8", {"Content-Disposition": f'attachment; filename="submission-{m.group(1)}.md"'}
            )

        for route_method, pattern, fn in hub.routes:
            m = pattern.match(path)
            if not m or route_method != method:
                continue
            query = {k: v[0] for k, v in parse_qs(raw_query).items()}
            body = {}
            if method == "POST":
                body = self.read_json()
                if body is None:
                    return
            try:
                result = fn(m, query, body)
            except HttpError as err:
                return self.send_json(err.status, {"error": str(err)})
            except (ValueError, TypeError, PermissionError) as err:
                return self.send_json(400, {"error": str(err)})
            except Exception as err:
                print(f"[api] {method} {path}: {err!r}", file=sys.stderr)
                return self.send_json(500, {"error": str(err)})
            return self.send_json(200, {"ok": True} if result is None else result)
        self.send_json(404, {"error": "not found"})

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.send_json(413, {"error": "request body too large"})
            return None
        raw = self.rfile.read(length) if length else b""
        if not raw.strip():
            return {}
        try:
            body = json.loads(raw)
        except ValueError:
            self.send_json(400, {"error": "invalid JSON body"})
            return None
        if not isinstance(body, dict):
            self.send_json(400, {"error": "JSON body must be an object"})
            return None
        return body

    # ---- server-sent events ----
    def events(self, run_id):
        hub = self.hub
        run = hub.runner.get(run_id)
        if not run:
            # Not live (finished before a restart, or from an earlier session): replay from the archive.
            if not get_run(hub.db, run_id):
                return self.send_json(404, {"error": "no such run"})
            self.start_sse()
            for evt in get_run_events(hub.db, run_id):
                self.sse(evt)
            self.wfile.write(b"event: done\ndata: {}\n\n")
            return
        backlog, q = run.subscribe()
        try:
            self.start_sse()
            self.wfile.write(b"retry: 2000\n\n")
            for evt in backlog:
                self.sse(evt)
            while True:
                try:
                    evt = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")  # also notices a client that went away
                    self.wfile.flush()
                    continue
                if evt is None:
                    break
                self.sse(evt)
            self.wfile.write(b"event: done\ndata: {}\n\n")
        finally:
            run.unsubscribe(q)

    def start_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True

    def sse(self, evt):
        self.wfile.write(f"data: {to_json(evt)}\n\n".encode("utf8"))
        self.wfile.flush()

    # ---- the built client ----
    def static(self, path):
        root = self.hub.static_dir
        target = (root / path.lstrip("/")).resolve()
        if root not in target.parents or not target.is_file():
            target = root / "index.html"  # client-side routes and anything unknown get the app
        if target.name == "index.html":
            html = target.read_text(encoding="utf8")
            if self.hub.index_bootstrap:
                boot = to_json(self.hub.index_bootstrap()).replace("</", "<\\/")
                html = html.replace("<head>", f"<head>\n    <script>window.__EI_DESKTOP__ = {boot};</script>", 1)
            return self.send_body(200, html, "text/html; charset=utf-8")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_body(200, target.read_bytes(), ctype)


def main():
    """`python -m hub` — the API on 127.0.0.1:8787 for the browser setup (Vite proxies /api here)."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Endless Illusion control-plane server.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    parser.add_argument("--static", help="also serve this built client directory (e.g. ui/dist)")
    args = parser.parse_args()

    claude = os.environ.get("CLAUDE_BIN", "claude")
    hub = Hub(claude_cmd=claude, static_dir=args.static, data_dir=os.environ.get("EI_DATA_DIR") or None)
    server = hub.serve("127.0.0.1", args.port)
    print(f"Endless Illusion control plane on http://127.0.0.1:{args.port}", flush=True)
    print(f"claude bin: {claude}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        hub.runner.stop_all()
        server.server_close()
