import re

from .. import HUB_DIR

DIR = HUB_DIR / "migrations"


def migrate(db):
    """Apply migrations/NNN-*.sql newer than PRAGMA user_version. Returns the resulting version."""
    files = sorted(f for f in DIR.iterdir() if re.match(r"^\d+-.*\.sql$", f.name))

    def read_version():
        return db.get("PRAGMA user_version")["user_version"]

    version = read_version()
    for file in files:
        n = int(file.name.split("-", 1)[0])
        if n <= version:
            continue
        # Take the write lock before re-reading the version: several processes
        # (hub + per-agent MCP servers) may open a fresh database at once.
        with db.lock:
            db.conn.execute("BEGIN IMMEDIATE")
            try:
                version = read_version()
                if n > version:
                    # executescript() would COMMIT first; run statement by statement inside our transaction.
                    for stmt in _statements(file.read_text(encoding="utf8")):
                        db.conn.execute(stmt)
                    db.conn.execute(f"PRAGMA user_version = {n}")
                    version = n
                db.conn.execute("COMMIT")
            except Exception as err:
                db.conn.execute("ROLLBACK")
                raise RuntimeError(f"migration {file.name} failed: {err}") from err
    return version


def _statements(sql):
    """Split a migration into statements, keeping CREATE TRIGGER … BEGIN … END; bodies whole."""
    import sqlite3

    out, buf = [], ""
    for line in sql.splitlines(keepends=True):
        if not buf and line.strip().startswith("--"):
            continue
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
