from __future__ import annotations

import sqlite3
from pathlib import Path

from ..logging_util import log

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_conn: sqlite3.Connection | None = None


def init_db() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    _conn = sqlite3.connect(":memory:", check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    _conn.executescript(schema)
    log("[DB] Initialized in-memory database")
    return _conn


def get_db() -> sqlite3.Connection:
    if _conn is None:
        return init_db()
    return _conn


def reset_db() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None
    return init_db()


def close_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
        log("[DB] Connection closed")
