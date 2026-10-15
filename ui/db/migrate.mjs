import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "migrations");

/** Apply migrations/NNN-*.sql newer than PRAGMA user_version. Returns the resulting version. */
export function migrate(db) {
  const files = readdirSync(DIR).filter((f) => /^\d+-.*\.sql$/.test(f)).sort();
  const readVersion = () => db.prepare("PRAGMA user_version").get().user_version;
  let version = readVersion();
  for (const file of files) {
    const n = Number.parseInt(file, 10);
    if (n <= version) continue;
    // Take the write lock before re-reading the version: several processes
    // (hub + per-agent MCP servers) may open a fresh database at once.
    db.exec("BEGIN IMMEDIATE");
    try {
      version = readVersion();
      if (n > version) {
        db.exec(readFileSync(path.join(DIR, file), "utf8"));
        db.exec(`PRAGMA user_version = ${n}`);
        version = n;
      }
      db.exec("COMMIT");
    } catch (err) {
      db.exec("ROLLBACK");
      throw new Error(`migration ${file} failed: ${err.message}`);
    }
  }
  return version;
}
