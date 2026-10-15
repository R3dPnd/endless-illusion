import { nowIso } from "./index.mjs";
import { assertOwns } from "./ownership.mjs";
import { WRITE_TABLES } from "./tables.mjs";
import { normalizeUrl } from "./url.mjs";
import { validateFields } from "./validate.mjs";

/**
 * Append one row to an agent-owned table. The only write path agents have:
 * ownership is checked first, fields are validated and redacted, and
 * agent / run_id / created_at are stamped here. Rows are never updated or
 * deleted; a correction is a new row whose `supersedes` names the old one.
 */
export function insertAgentRow(db, { agent, runId, table, fields }) {
  assertOwns(agent, table);
  const def = WRITE_TABLES[table];
  if (!def) throw new Error(`no write definition for table ${table}`);

  const row = validateFields(table, def.columns, fields ?? {});

  if (row.supersedes !== undefined) {
    const prior = db.prepare(`SELECT id FROM ${table} WHERE id = ?`).get(row.supersedes);
    if (!prior) throw new Error(`${table}.supersedes: no row ${row.supersedes} in ${table}`);
  }
  if (table === "program_leads") row.normalized_url = normalizeUrl(row.url);

  row.agent = agent;
  row.run_id = runId ?? null;
  row.created_at = nowIso();

  const cols = Object.keys(row);
  const sql = `INSERT INTO ${table} (${cols.join(", ")}) VALUES (${cols.map(() => "?").join(", ")})`;
  const result = db.prepare(sql).run(...cols.map((c) => row[c]));
  return { id: Number(result.lastInsertRowid) };
}
