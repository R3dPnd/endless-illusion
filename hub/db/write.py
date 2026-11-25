from . import now_iso
from .ownership import assert_owns
from .tables import WRITE_TABLES
from .url import normalize_url
from .validate import ValidationError, validate_fields


def insert_agent_row(db, agent, run_id, table, fields):
    """
    Append one row to an agent-owned table. The only write path agents have:
    ownership is checked first, fields are validated and redacted, and
    agent / run_id / created_at are stamped here. Rows are never updated or
    deleted; a correction is a new row whose `supersedes` names the old one.
    """
    assert_owns(agent, table)
    definition = WRITE_TABLES.get(table)
    if not definition:
        raise ValidationError(f"no write definition for table {table}")

    row = validate_fields(table, definition["columns"], fields or {})

    if "supersedes" in row and not db.get(f"SELECT id FROM {table} WHERE id = ?", row["supersedes"]):
        raise ValidationError(f"{table}.supersedes: no row {row['supersedes']} in {table}")
    if table == "program_leads":
        row["normalized_url"] = normalize_url(row["url"])
    if table == "plan_drafts":
        # A plan draft belongs to the engagement whose stage the writing run is (its ops_stages row):
        # a run cannot plant a plan in another engagement, and a run with no stage cannot write one.
        stage = db.get("SELECT engagement_id FROM ops_stages WHERE run_id = ? ORDER BY id DESC LIMIT 1", run_id) if run_id else None
        if stage is None or stage["engagement_id"] != row["engagement_id"]:
            raise ValidationError("plan_drafts.engagement_id: must be the engagement of this run's stage")

    row["agent"] = agent
    row["run_id"] = run_id
    row["created_at"] = now_iso()

    cols = list(row)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    row_id, _ = db.run(sql, *(row[c] for c in cols))
    return {"id": row_id}
