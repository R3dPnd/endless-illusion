import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_CLAUDE = [sys.executable, str(FIXTURES / "fake_claude.py")]
ORIGIN = "http://localhost:5173"

from hub.db import open_db  # noqa: E402


@pytest.fixture
def db():
    return open_db(":memory:")


class Client:
    """Tiny HTTP client against a running hub."""

    def __init__(self, base):
        self.base = base

    def request(self, method, path, body=None, headers=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, res.headers, res.read().decode("utf8")
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read().decode("utf8")

    def get(self, path):
        status, headers, text = self.request("GET", path)
        body = json.loads(text) if "json" in (headers.get("Content-Type") or "") else text
        return status, body

    def post(self, path, body=None, headers=None):
        hdrs = {"Content-Type": "application/json", "Origin": ORIGIN, **(headers or {})}
        status, _, text = self.request("POST", path, body if body is not None else {}, hdrs)
        try:
            return status, json.loads(text)
        except ValueError:
            return status, None


def start_hub(tmp_path, **kw):
    from hub.app import Hub

    hub = Hub(data_dir=tmp_path / "data", claude_cmd=FAKE_CLAUDE, **kw)
    server = hub.serve("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return hub, server, Client(f"http://127.0.0.1:{server.server_address[1]}")
