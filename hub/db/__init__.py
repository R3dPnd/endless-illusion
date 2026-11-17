"""The hub database: one SQLite file shared by the server and every agent's memory server."""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .migrate import migrate


def now_iso():
    """UTC timestamp in the same shape as JS toISOString(), e.g. 2026-10-20T16:05:28.123Z."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Database:
    """
    A connection that several threads (HTTP handlers, run readers) can share.
    Every call takes the lock; `transaction()` holds it for the whole
    BEGIN IMMEDIATE … COMMIT so no other thread interleaves statements.
    """

    def __init__(self, conn):
        self.conn = conn
        self.lock = threading.RLock()

    def run(self, sql, *params):
        """Execute a write; returns (lastrowid, changes)."""
        with self.lock:
            cur = self.conn.execute(sql, params)
            return cur.lastrowid, cur.rowcount

    def get(self, sql, *params):
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None

    def all(self, sql, *params):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    @contextmanager
    def transaction(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            self.conn.execute("COMMIT")

    def close(self):
        with self.lock:
            self.conn.close()


def open_db(file):
    """Open (and migrate) the hub database. Pass ":memory:" in tests."""
    file = str(file)
    on_disk = file != ":memory:"
    is_new = False
    if on_disk:
        Path(file).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        is_new = not os.path.exists(file)
    # Autocommit mode: transactions are explicit (BEGIN IMMEDIATE), as in the migrations.
    conn = sqlite3.connect(file, isolation_level=None, check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    if is_new:
        try:
            os.chmod(file, 0o600)
        except OSError:
            pass
    conn.execute("PRAGMA busy_timeout = 5000")
    if on_disk:
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    db = Database(conn)
    migrate(db)
    return db
