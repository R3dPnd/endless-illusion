import os
import stat
import subprocess
import sys

import pytest

from hub.db import open_db
from hub.db.migrate import migrate
from hub.db.ownership import OWNERSHIP, OwnershipError, assert_owns, server_name
from hub.db.redact import clip, redact

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def table_names(db):
    return {r["name"] for r in db.all("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_migrations_set_user_version_and_are_idempotent(db):
    assert db.get("PRAGMA user_version")["user_version"] == 1
    assert migrate(db) == 1


def test_creates_every_owned_table_plus_hub_and_operator_tables(db):
    names = table_names(db)
    expected = {t for ts in OWNERSHIP.values() for t in ts} | {
        "runs", "run_events", "reports",
        "programs", "lead_decisions", "proposal_decisions", "scope_snapshots",
        "search_fts",
    }
    assert expected <= names


def test_on_disk_database_is_wal_and_owner_only(tmp_path):
    file = tmp_path / "data" / "ei.db"
    db = open_db(file)
    assert db.get("PRAGMA journal_mode")["journal_mode"] == "wal"
    if os.name != "nt":  # Windows has no POSIX permission bits
        assert stat.S_IMODE(os.stat(file).st_mode) == 0o600


def test_several_processes_can_migrate_a_fresh_database_at_once(tmp_path):
    file = tmp_path / "ei.db"
    script = f"import sys; sys.path.insert(0, {ROOT!r}); from hub.db import open_db; open_db({str(file)!r})"
    procs = [subprocess.Popen([sys.executable, "-c", script], stderr=subprocess.PIPE) for _ in range(8)]
    results = [(p.wait(), p.stderr.read().decode()) for p in procs]
    assert [code for code, _ in results] == [0] * 8, [err for _, err in results if err]


def test_allows_an_agent_its_own_tables_only():
    assert_owns("dahlia-of-wednesday", "cve_notes")
    with pytest.raises(OwnershipError, match="may not write"):
        assert_owns("dahlia-of-wednesday", "web_findings")


def test_gives_no_agent_the_operators_scope_tables():
    for agent in OWNERSHIP:
        for t in ["scope_snapshots", "programs", "lead_decisions", "proposal_decisions", "runs", "reports"]:
            with pytest.raises(OwnershipError):
                assert_owns(agent, t)


def test_lets_both_saudade_and_dahlia_record_program_leads():
    assert_owns("saudade-of-sunday", "program_leads")
    assert_owns("dahlia-of-wednesday", "program_leads")
    with pytest.raises(OwnershipError):
        assert_owns("diablo-of-monday", "program_leads")


def test_names_one_mcp_server_per_agent():
    assert server_name("dahlia-of-wednesday") == "ei-dahlia"
    assert server_name("metsa-of-tuesday") == "ei-metsa"


@pytest.mark.parametrize(
    "text,leaked",
    [
        ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
        ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig-part_1 here", "eyJhbGciOiJIUzI1NiJ9"),
        ("key AKIAABCDEFGHIJKLMNOP leaked", "AKIAABCDEFGHIJKLMNOP"),
        ("password=hunter2&x=1", "hunter2"),
        ("token: s3cr3tvalue", "s3cr3tvalue"),
        ("secret=topsecret", "topsecret"),
    ],
)
def test_redaction_masks_secrets(text, leaked):
    out = redact(text)
    assert "[REDACTED]" in out
    assert leaked not in out


def test_redaction_leaves_ordinary_security_text_alone():
    s = "CVE-2026-1234 affects nginx 1.24.0; see https://nvd.nist.gov/vuln/detail/CVE-2026-1234"
    assert redact(s) == s


def test_clips_text_to_64_kb():
    assert len(clip("x" * 70000)) == 65536
    assert clip("short") == "short"
