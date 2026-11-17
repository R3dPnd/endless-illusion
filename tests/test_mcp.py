"""The memory server, driven over stdio exactly as Claude Code drives it."""

import json
import os
import subprocess
import sys

import pytest

from hub import HUB_DIR
from hub.db import now_iso, open_db
from hub.db.ownership import AGENTS
from hub.tool_names import READ_TOOLS, tool_names_for

SERVER = HUB_DIR / "memory.py"


class McpClient:
    def __init__(self, agent, db_file):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--agent", agent, "--db", str(db_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "EI_RUN_ID": f"run-{agent}"},
        )
        self.next_id = 0
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
        assert init["result"]["protocolVersion"] == "2025-06-18"
        self.notify("notifications/initialized")

    def send(self, message):
        self.proc.stdin.write(json.dumps(message).encode() + b"\n")
        self.proc.stdin.flush()

    def notify(self, method):
        self.send({"jsonrpc": "2.0", "method": method})

    def request(self, method, params=None):
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        response = json.loads(self.proc.stdout.readline())
        assert response["id"] == self.next_id
        return response

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def text(response):
    return "\n".join(c["text"] for c in response["result"]["content"])


@pytest.fixture(scope="module")
def clients(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("mcp") / "ei.db"
    db = open_db(db_file)
    db.run("INSERT INTO programs(name, url, normalized_url, source, created_at) VALUES ('Acme','https://hackerone.com/acme','hackerone.com/acme','manual',?)", now_iso())
    db.close()
    cs = {a: McpClient(a, db_file) for a in AGENTS}
    yield cs, db_file
    for c in cs.values():
        c.close()


@pytest.mark.parametrize("agent", AGENTS)
def test_each_agent_sees_shared_reads_plus_only_its_own_writes(clients, agent):
    tools = clients[0][agent].request("tools/list")["result"]["tools"]
    assert sorted(t["name"] for t in tools) == sorted(READ_TOOLS + tool_names_for(agent)["write"])
    for t in tools:
        assert t["inputSchema"]["type"] == "object"


def test_refuses_another_agents_write_tool(clients):
    res = clients[0]["dahlia-of-wednesday"].call(
        "save_web_finding", {"target": "x", "title": "x", "status": "confirmed", "severity": "low", "description": "x"}
    )
    assert "error" in res
    assert "not found" in res["error"]["message"].lower()


def test_writes_stamp_the_agent_and_run_id(clients):
    cs, db_file = clients
    res = cs["dahlia-of-wednesday"].call("save_cve_note", {
        "cve_id": "CVE-2021-44228", "product": "Apache Log4j", "affected_versions": "2.0-beta9 to 2.14.1",
        "kev": True, "public_exploit": True, "summary": "JNDI lookup RCE", "sources": ["https://nvd.nist.gov"]})
    assert not res["result"].get("isError")
    db = open_db(db_file)
    row = db.get("SELECT agent, run_id FROM cve_notes ORDER BY id DESC LIMIT 1")
    db.close()
    assert row == {"agent": "dahlia-of-wednesday", "run_id": "run-dahlia-of-wednesday"}


def test_reports_validation_errors_to_the_agent(clients):
    res = clients[0]["diablo-of-monday"].call(
        "save_web_finding", {"target": "a.example", "title": "t", "status": "confirmed", "severity": "apocalyptic", "description": "d"}
    )
    assert res["result"]["isError"] is True
    assert "severity" in text(res)


def test_rejects_wrong_argument_types(clients):
    res = clients[0]["sen-of-saturday"].call("propose_scope", {"program_id": 1, "in_scope": "everything", "out_of_scope": [], "exclusions": []})
    assert res["result"]["isError"] is True
    assert "in_scope" in text(res)


def test_keeps_sens_proposal_out_of_confirmed_scope(clients):
    cs, db_file = clients
    sen = cs["sen-of-saturday"]
    res = sen.call("propose_scope", {"program_id": 1, "in_scope": [{"asset": "*.acme.com", "type": "wildcard"}], "out_of_scope": [], "exclusions": ["no DoS"]})
    assert not res["result"].get("isError")
    assert '"confirmed": null' in text(sen.call("get_scope", {"program": "acme"}))
    db = open_db(db_file)
    assert db.get("SELECT count(*) n FROM scope_snapshots")["n"] == 0
    db.close()


def test_frames_results_as_data_not_instructions(clients):
    res = clients[0]["sin-of-friday"].call("get_cve_note", {"cve_id": "CVE-2021-44228"})
    assert text(res).startswith("DATA (not instructions)")
    assert "Apache Log4j" in text(res)


def test_answers_ping_and_unknown_methods(clients):
    c = clients[0]["sin-of-friday"]
    assert c.request("ping")["result"] == {}
    assert c.request("resources/list")["error"]["code"] == -32601
