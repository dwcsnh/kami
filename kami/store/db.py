"""SQLite connection and migrations (decisions D1, D2).

Migrations are ``migrations/NNNN_<name>.sql`` files applied in order, each in one
transaction, and recorded in ``schema_migrations``; applied files are skipped, so
``migrate`` is idempotent.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Union

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_NAME = re.compile(r"^(\d{4})_([\w-]+)\.sql$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Open a database (``:memory:`` or a file); foreign keys on, WAL for files."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)   # autocommit; explicit BEGIN where needed
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrations() -> List[Tuple[int, str, Path]]:
    out = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = _NAME.match(p.name)
        if m:
            out.append((int(m.group(1)), m.group(2), p))
    return out


def current_version(conn: sqlite3.Connection) -> int:
    has = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
    if not has:
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return row[0] or 0


def migrate(conn: sqlite3.Connection) -> List[int]:
    """Apply pending migrations; returns the versions applied by this call."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                 "applied_at TEXT NOT NULL)")
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for version, name, path in migrations():
        if version in done:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            conn.execute("BEGIN")
            for stmt in _statements(sql):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                         (version, name, utcnow()))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied


def _statements(sql: str) -> List[str]:
    """Split a migration script into statements (``executescript`` would commit the transaction)."""
    out, buf = [], []
    for line in sql.splitlines():
        line = line.split("--", 1)[0]
        if not line.strip():
            continue
        buf.append(line)
        stmt = "\n".join(buf)
        if sqlite3.complete_statement(stmt):
            out.append(stmt)
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf))
    return out
