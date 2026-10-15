import { DatabaseSync } from "node:sqlite";
import { chmodSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { migrate } from "./migrate.mjs";

export const nowIso = () => new Date().toISOString();

/** Open (and migrate) the hub database. Pass ":memory:" in tests. */
export function openDb(file) {
  const onDisk = file !== ":memory:";
  if (onDisk) mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const isNew = onDisk && !existsSync(file);
  const db = new DatabaseSync(file);
  if (isNew) chmodSync(file, 0o600);
  db.exec("PRAGMA busy_timeout = 5000");
  if (onDisk) db.exec("PRAGMA journal_mode = WAL");
  db.exec("PRAGMA foreign_keys = ON");
  migrate(db);
  return db;
}
