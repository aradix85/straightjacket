#!/usr/bin/env python3
"""Read-only query functions. Each returns dataclass instances."""

from __future__ import annotations

import json
import sqlite3

from ..models import ClockData, MemoryEntry, NpcData, ThreadEntry
from .connection import get_db


def _row_to_npc(row: sqlite3.Row) -> NpcData:
    """Convert a database row to NpcData."""
    return NpcData(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        agenda=row["agenda"],
        instinct=row["instinct"],
        arc=row["arc"],
        secrets=json.loads(row["secrets"]),
        disposition=row["disposition"],
        bond=row["bond"],
        bond_max=row["bond_max"],
        status=row["status"],
        introduced=bool(row["introduced"]),
        aliases=json.loads(row["aliases"]),
        keywords=json.loads(row["keywords"]),
        importance_accumulator=row["importance_accumulator"],
        last_reflection_scene=row["last_reflection_scene"],
        last_location=row["last_location"],
        needs_reflection=bool(row["needs_reflection"]),
        gather_count=row["gather_count"],
    )


def query_npcs(
    status: str | None = None,
    disposition: str | None = None,
    location: str | None = None,
    bond_min: int | None = None,
    bond_max: int | None = None,
    introduced: bool | None = None,
) -> list[NpcData]:
    """Query NPCs with optional filters. Returns NpcData instances without memories."""
    conn = get_db()
    clauses: list[str] = []
    params: list[str | int] = []

    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if disposition is not None:
        clauses.append("disposition = ?")
        params.append(disposition)
    if location is not None:
        clauses.append("last_location = ?")
        params.append(location)
    if bond_min is not None:
        clauses.append("bond >= ?")
        params.append(bond_min)
    if bond_max is not None:
        clauses.append("bond <= ?")
        params.append(bond_max)
    if introduced is not None:
        clauses.append("introduced = ?")
        params.append(int(introduced))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM npcs{where}", params).fetchall()
    return [_row_to_npc(row) for row in rows]


def query_memories(
    npc_id: str | None = None,
    min_importance: int | None = None,
    scene_min: int | None = None,
    scene_max: int | None = None,
    memory_type: str | None = None,
    limit: int | None = None,
) -> list[MemoryEntry]:
    """Query memories with optional filters. Returns MemoryEntry instances."""
    conn = get_db()
    clauses: list[str] = []
    params: list[str | int] = []

    if npc_id is not None:
        clauses.append("npc_id = ?")
        params.append(npc_id)
    if min_importance is not None:
        clauses.append("importance >= ?")
        params.append(min_importance)
    if scene_min is not None:
        clauses.append("scene >= ?")
        params.append(scene_min)
    if scene_max is not None:
        clauses.append("scene <= ?")
        params.append(scene_max)
    if memory_type is not None:
        clauses.append("type = ?")
        params.append(memory_type)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    order = " ORDER BY scene DESC, importance DESC"
    limit_clause = f" LIMIT {limit}" if limit is not None else ""
    rows = conn.execute(f"SELECT * FROM memories{where}{order}{limit_clause}", params).fetchall()

    return [
        MemoryEntry(
            scene=row["scene"],
            event=row["event"],
            emotional_weight=row["emotional_weight"],
            importance=row["importance"],
            type=row["type"],
            about_npc=row["about_npc"],
            tone=row["tone"],
            tone_key=row["tone_key"],
        )
        for row in rows
    ]


def query_threads(
    active: bool | None = None,
    thread_type: str | None = None,
) -> list[ThreadEntry]:
    """Query threads with optional filters."""
    conn = get_db()
    clauses: list[str] = []
    params: list[str | int] = []

    if active is not None:
        clauses.append("active = ?")
        params.append(int(active))
    if thread_type is not None:
        clauses.append("thread_type = ?")
        params.append(thread_type)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM threads{where}", params).fetchall()

    return [
        ThreadEntry(
            id=row["id"],
            name=row["name"],
            thread_type=row["thread_type"],
            weight=row["weight"],
            source=row["source"],
            linked_track_id=row["linked_track_id"],
            active=bool(row["active"]),
        )
        for row in rows
    ]


def query_clocks(
    clock_type: str | None = None,
    fired: bool | None = None,
    owner: str | None = None,
) -> list[ClockData]:
    """Query clocks with optional filters."""
    conn = get_db()
    clauses: list[str] = []
    params: list[str | int] = []

    if clock_type is not None:
        clauses.append("clock_type = ?")
        params.append(clock_type)
    if fired is not None:
        clauses.append("fired = ?")
        params.append(int(fired))
    if owner is not None:
        clauses.append("owner = ?")
        params.append(owner)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM clocks{where}", params).fetchall()

    return [
        ClockData(
            name=row["name"],
            clock_type=row["clock_type"],
            segments=row["segments"],
            filled=row["filled"],
            trigger_description=row["trigger_description"],
            owner=row["owner"],
            fired=bool(row["fired"]),
            fired_at_scene=row["fired_at_scene"],
        )
        for row in rows
    ]
