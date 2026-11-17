import json
import re

import pytest

from hub.db import now_iso
from hub.db.ownership import OWNERSHIP, OwnershipError
from hub.db.read import find_prior_work, get_cve_note, get_scope, list_programs, search_reports
from hub.db.tables import WRITE_TABLES
from hub.db.url import normalize_url
from hub.db.validate import ValidationError
from hub.db.write import insert_agent_row

DAHLIA = "dahlia-of-wednesday"
SAUDADE = "saudade-of-sunday"
DIABLO = "diablo-of-monday"
SEN = "sen-of-saturday"


def cve(**over):
    return {
        "cve_id": "CVE-2021-44228", "product": "Apache Log4j", "affected_versions": "2.0-beta9 to 2.14.1",
        "kev": True, "public_exploit": True, "summary": "JNDI lookup RCE in nginx-fronted apps",
        "sources": ["https://nvd.nist.gov"], **over,
    }


def add_program(db, name="Acme", url="https://hackerone.com/acme"):
    row_id, _ = db.run(
        "INSERT INTO programs(name, url, normalized_url, source, created_at) VALUES (?,?,?, 'manual', ?)",
        name, url, normalize_url(url), now_iso(),
    )
    return row_id


def insert(db, agent, table, fields, run_id="r"):
    return insert_agent_row(db, agent, run_id, table, fields)


def test_defines_a_tool_for_every_owned_table():
    for t in {t for ts in OWNERSHIP.values() for t in ts}:
        assert re.fullmatch(r"[a-z_]+", WRITE_TABLES[t]["tool"]), t


def test_stamps_agent_and_run_id(db):
    row_id = insert(db, DAHLIA, "cve_notes", cve(), run_id="run-1")["id"]
    row = db.get("SELECT * FROM cve_notes WHERE id = ?", row_id)
    assert row["agent"] == DAHLIA
    assert row["run_id"] == "run-1"
    assert row["kev"] == 1
    assert json.loads(row["sources"]) == ["https://nvd.nist.gov"]


def test_refuses_another_agents_table(db):
    with pytest.raises(OwnershipError, match="may not write"):
        insert(db, DAHLIA, "web_findings", {})


def test_rejects_unknown_columns(db):
    with pytest.raises(ValidationError, match="unknown field"):
        insert(db, DAHLIA, "cve_notes", cve(agent="sen-of-saturday"))


def test_rejects_bad_enum_values(db):
    with pytest.raises(ValidationError, match="severity"):
        insert(db, DIABLO, "web_findings", {"target": "a.example", "title": "x", "status": "confirmed", "severity": "apocalyptic", "description": "d"})


def test_rejects_missing_required_fields(db):
    with pytest.raises(ValidationError, match="required"):
        insert(db, DAHLIA, "cve_notes", {"cve_id": "CVE-1"})


def test_rejects_booleans_as_integers(db):
    with pytest.raises(ValidationError, match="integer"):
        insert(db, SEN, "scope_proposals", {"program_id": True, "in_scope": [], "out_of_scope": [], "exclusions": []})


def test_redacts_secrets_in_stored_text(db):
    row_id = insert(db, DIABLO, "web_findings", {
        "target": "app.example.com", "title": "Token in response", "status": "confirmed", "severity": "high",
        "description": "Response leaks Authorization: Bearer sk_live_123456", "evidence": "password=hunter2"})["id"]
    row = db.get("SELECT description, evidence FROM web_findings WHERE id = ?", row_id)
    assert "sk_live_123456" not in row["description"]
    assert "hunter2" not in row["evidence"]


def test_only_supersedes_an_existing_row_in_the_same_table(db):
    with pytest.raises(ValidationError, match="supersedes"):
        insert(db, DAHLIA, "cve_notes", cve(supersedes=999))


def test_derives_normalized_url_for_program_leads(db):
    row_id = insert(db, SAUDADE, "program_leads", {"name": "Acme", "url": "https://HackerOne.com/acme/", "found_via": "security.txt"})["id"]
    assert db.get("SELECT normalized_url FROM program_leads WHERE id = ?", row_id)["normalized_url"] == "hackerone.com/acme"


def test_returns_the_latest_note_in_a_supersede_chain(db):
    a = insert(db, DAHLIA, "cve_notes", cve(cvss="9.0"), run_id="r1")
    insert(db, DAHLIA, "cve_notes", cve(cvss="10.0", supersedes=a["id"]), run_id="r2")
    assert get_cve_note(db, "cve-2021-44228")["cvss"] == "10.0"


def test_finds_records_by_full_text_search_with_agent_filter(db):
    insert(db, DAHLIA, "cve_notes", cve(), run_id="r1")
    assert "cve_note" in [h["kind"] for h in search_reports(db, "nginx")]
    assert search_reports(db, "nginx", agent=DIABLO) == []


def test_tolerates_fts_syntax_characters_in_queries(db):
    search_reports(db, 'log4j "AND (OR')


def test_finds_prior_work_for_a_target_across_domains(db):
    insert(db, SAUDADE, "assets", {"host": "api.example.com", "kind": "subdomain"})
    insert(db, DIABLO, "web_findings", {
        "target": "https://www.example.com/login", "title": "Open redirect", "status": "suspected", "severity": "low", "description": "d"})
    insert(db, SAUDADE, "program_leads", {"name": "Example", "url": "https://example.com/security", "found_via": "security.txt"})
    w = find_prior_work(db, "example.com")
    assert len(w["assets"]) == 1
    assert len(w["web_findings"]) == 1
    assert len(w["program_leads"]) == 1
    assert find_prior_work(db, "%")["assets"] == []


def test_never_returns_a_proposal_as_scope(db):
    pid = add_program(db)
    insert(db, SEN, "scope_proposals", {
        "program_id": pid, "in_scope": [{"asset": "*.acme.com", "type": "wildcard"}], "out_of_scope": [], "exclusions": []})
    assert get_scope(db, pid)["confirmed"] is None
    db.run(
        "INSERT INTO scope_snapshots(program_id, in_scope, out_of_scope, exclusions, confirmed_at) VALUES (?,?,?,?,?)",
        pid, '[{"asset":"app.acme.com","type":"domain"}]', "[]", "[]", now_iso(),
    )
    assert get_scope(db, "acme")["confirmed"]["in_scope"][0]["asset"] == "app.acme.com"


def test_groups_repeat_lead_sightings_by_normalized_url(db):
    insert(db, SAUDADE, "program_leads", {"name": "Acme", "url": "https://hackerone.com/acme", "found_via": "security.txt"}, run_id="r1")
    insert(db, DAHLIA, "program_leads", {"name": "Acme VDP", "url": "https://www.HackerOne.com/acme/", "found_via": "advisory"}, run_id="r2")
    leads = list_programs(db, "leads")
    assert len(leads) == 1
    assert leads[0]["sightings"] == 2
    assert leads[0]["name"] == "Acme VDP"


def test_keeps_the_latest_non_empty_scope_summary_across_sightings(db):
    insert(db, SAUDADE, "program_leads", {
        "name": "Acme", "url": "https://hackerone.com/acme", "found_via": "security.txt", "scope_summary": "*.acme.com per policy"}, run_id="r1")
    insert(db, DAHLIA, "program_leads", {"name": "Acme", "url": "https://hackerone.com/acme", "found_via": "advisory"}, run_id="r2")
    assert list_programs(db, "leads")[0]["scope_summary"] == "*.acme.com per policy"


def test_lists_programs_by_stage(db):
    insert(db, DAHLIA, "program_leads", {"name": "Lead Co", "url": "https://bugcrowd.com/leadco", "found_via": "advisory"})
    add_program(db)
    assert [lead["name"] for lead in list_programs(db, "leads")] == ["Lead Co"]
    assert [p["name"] for p in list_programs(db, "tracked")] == ["Acme"]
    assert list_programs(db, "confirmed") == []
