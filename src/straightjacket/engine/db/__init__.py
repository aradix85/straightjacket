"""Straightjacket database package — SQLite read model.

Public API:
    init_db()           — create tables, return connection
    close_db()          — close active connection
    sync(game)          — write full GameState to database
    query_npcs(...)     — NPCs by status/disposition/location/bond
    query_memories(...) — memories by npc_id/importance/scene range
    query_threads(...)  — threads by active/type
    query_clocks(...)   — clocks by type/fired status
"""

from .connection import close_db, get_db, init_db
from .queries import query_clocks, query_memories, query_npcs, query_threads
from .sync import sync

__all__ = [
    "close_db",
    "get_db",
    "init_db",
    "query_clocks",
    "query_memories",
    "query_npcs",
    "query_threads",
    "sync",
]
