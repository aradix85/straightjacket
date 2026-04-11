#!/usr/bin/env python3
"""Tests for database layer: schema, sync, queries, restore rebuild.

Run: python -m pytest tests/test_db.py -v
"""

# Stubs are set up in conftest.py

import sqlite3

from straightjacket.engine.db.connection import close_db, get_db, init_db, reset_db
from straightjacket.engine.db.queries import query_clocks, query_memories, query_npcs, query_threads
from straightjacket.engine.db.sync import sync
from straightjacket.engine.models import (
    ClockData,
    GameState,
    MemoryEntry,
    NpcData,
    ProgressTrack,
    ThreadEntry,
    CharacterListEntry,
    NarrationEntry,
    SceneLogEntry,
)


def _fresh_db() -> sqlite3.Connection:
    """Reset and return a fresh database connection."""
    return reset_db()


def _game_with_npcs() -> GameState:
    """GameState with two NPCs, memories, a thread, a clock, and a scene log entry."""
    game = GameState(player_name="Ash", setting_id="starforged")
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Kira",
            description="A smuggler with cold eyes",
            agenda="Access the vault",
            disposition="distrustful",
            bond=1,
            status="active",
            last_location="docks",
            aliases=["K"],
            secrets=["Knows the vault code"],
            memory=[
                MemoryEntry(scene=1, event="Met the player at the docks", importance=5, emotional_weight="curious"),
                MemoryEntry(scene=3, event="Player broke a promise", importance=8, emotional_weight="betrayed"),
            ],
        ),
        NpcData(
            id="npc_2",
            name="Rowan",
            description="A healer",
            disposition="friendly",
            bond=3,
            status="background",
            last_location="clinic",
            memory=[
                MemoryEntry(scene=2, event="Healed the player's wound", importance=4, type="observation"),
                MemoryEntry(
                    scene=4, event="Growing respect for the player", importance=7, type="reflection", tone="protective"
                ),
            ],
        ),
    ]
    game.narrative.threads.append(
        ThreadEntry(id="thread_1", name="Find the vault", thread_type="vow", weight=2, active=True)
    )
    game.narrative.threads.append(
        ThreadEntry(id="thread_2", name="Old grudge", thread_type="tension", weight=1, active=False)
    )
    game.narrative.characters_list.append(CharacterListEntry(id="npc_1", name="Kira", entry_type="npc", weight=2))
    game.world.clocks.append(ClockData(name="Vault heist", clock_type="scheme", segments=6, filled=2, owner="Kira"))
    game.world.clocks.append(
        ClockData(name="Storm", clock_type="threat", segments=4, filled=4, fired=True, fired_at_scene=5)
    )
    game.narrative.scene_count = 5
    game.narrative.session_log.append(
        SceneLogEntry(scene=1, summary="Arrived at docks", move="adventure/face_danger", result="WEAK_HIT")
    )
    game.narrative.narration_history.append(
        NarrationEntry(scene=1, prompt_summary="Opening", narration="The salt air bit at your skin.")
    )
    game.vow_tracks.append(
        ProgressTrack(id="vow_bg", name="Find the vault", track_type="vow", rank="dangerous", ticks=8)
    )
    return game


# ── Schema ────────────────────────────────────────────────────


def test_init_creates_tables() -> None:
    conn = _fresh_db()
    tables = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        if not r[0].startswith("sqlite_")
    ]
    expected = [
        "characters_list",
        "clocks",
        "memories",
        "narration_history",
        "npcs",
        "scene_log",
        "threads",
        "vow_tracks",
    ]
    assert tables == expected
    close_db()


def test_init_idempotent() -> None:
    _fresh_db()
    conn2 = init_db()
    assert conn2 is get_db()
    close_db()


# ── Sync ──────────────────────────────────────────────────────


def test_sync_npcs() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT id, name, status FROM npcs ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["name"] == "Kira"
    assert rows[1]["status"] == "background"
    close_db()


def test_sync_memories() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM memories ORDER BY scene").fetchall()
    assert len(rows) == 4
    assert rows[0]["npc_id"] == "npc_1"
    assert rows[3]["type"] == "reflection"
    close_db()


def test_sync_threads() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM threads ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["name"] == "Find the vault"
    assert rows[1]["active"] == 0
    close_db()


def test_sync_clocks() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM clocks ORDER BY name").fetchall()
    assert len(rows) == 2
    assert rows[0]["name"] == "Storm"
    assert rows[0]["fired"] == 1
    close_db()


def test_sync_scene_log() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM scene_log").fetchall()
    assert len(rows) == 1
    assert rows[0]["move"] == "adventure/face_danger"
    close_db()


def test_sync_narration_history() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM narration_history").fetchall()
    assert len(rows) == 1
    assert "salt air" in rows[0]["narration"]
    close_db()


def test_sync_vow_tracks() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    conn = get_db()
    rows = conn.execute("SELECT * FROM vow_tracks").fetchall()
    assert len(rows) == 1
    assert rows[0]["ticks"] == 8
    assert rows[0]["rank"] == "dangerous"
    close_db()


def test_sync_replaces_not_appends() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    sync(game)
    conn = get_db()
    assert conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 4
    close_db()


def test_sync_empty_game() -> None:
    _fresh_db()
    game = GameState()
    sync(game)
    conn = get_db()
    assert conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0
    close_db()


# ── Queries ───────────────────────────────────────────────────


def test_query_npcs_all() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    npcs = query_npcs()
    assert len(npcs) == 2
    assert all(isinstance(n, NpcData) for n in npcs)
    close_db()


def test_query_npcs_by_status() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    active = query_npcs(status="active")
    assert len(active) == 1
    assert active[0].name == "Kira"
    bg = query_npcs(status="background")
    assert len(bg) == 1
    assert bg[0].name == "Rowan"
    close_db()


def test_query_npcs_by_disposition() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    result = query_npcs(disposition="friendly")
    assert len(result) == 1
    assert result[0].name == "Rowan"
    close_db()


def test_query_npcs_by_location() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    result = query_npcs(location="docks")
    assert len(result) == 1
    assert result[0].name == "Kira"
    close_db()


def test_query_npcs_by_bond_range() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    result = query_npcs(bond_min=2)
    assert len(result) == 1
    assert result[0].name == "Rowan"
    result = query_npcs(bond_max=1)
    assert len(result) == 1
    assert result[0].name == "Kira"
    close_db()


def test_query_npcs_combined_filters() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    result = query_npcs(status="active", disposition="distrustful")
    assert len(result) == 1
    assert result[0].id == "npc_1"
    result = query_npcs(status="active", disposition="friendly")
    assert len(result) == 0
    close_db()


def test_query_npcs_preserves_json_fields() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    kira = query_npcs(status="active")[0]
    assert kira.aliases == ["K"]
    assert kira.secrets == ["Knows the vault code"]
    close_db()


def test_query_npcs_no_memories() -> None:
    """query_npcs returns NpcData without memories (lightweight query)."""
    _fresh_db()
    sync(_game_with_npcs())
    kira = query_npcs(status="active")[0]
    assert kira.memory == []
    close_db()


def test_query_memories_by_npc() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    mems = query_memories(npc_id="npc_1")
    assert len(mems) == 2
    assert all(isinstance(m, MemoryEntry) for m in mems)
    close_db()


def test_query_memories_by_importance() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    high = query_memories(min_importance=7)
    assert len(high) == 2
    events = {m.event for m in high}
    assert "Player broke a promise" in events
    assert "Growing respect for the player" in events
    close_db()


def test_query_memories_by_scene_range() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    recent = query_memories(scene_min=3)
    assert len(recent) == 2
    assert all(m.scene >= 3 for m in recent)
    close_db()


def test_query_memories_by_type() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    refs = query_memories(memory_type="reflection")
    assert len(refs) == 1
    assert refs[0].tone == "protective"
    close_db()


def test_query_memories_with_limit() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    limited = query_memories(limit=2)
    assert len(limited) == 2
    close_db()


def test_query_memories_combined() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    result = query_memories(npc_id="npc_2", min_importance=5)
    assert len(result) == 1
    assert result[0].event == "Growing respect for the player"
    close_db()


def test_query_threads_all() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    threads = query_threads()
    assert len(threads) == 2
    close_db()


def test_query_threads_active() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    active = query_threads(active=True)
    assert len(active) == 1
    assert active[0].name == "Find the vault"
    inactive = query_threads(active=False)
    assert len(inactive) == 1
    close_db()


def test_query_threads_by_type() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    vows = query_threads(thread_type="vow")
    assert len(vows) == 1
    close_db()


def test_query_clocks_all() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    clocks = query_clocks()
    assert len(clocks) == 2
    assert all(isinstance(c, ClockData) for c in clocks)
    close_db()


def test_query_clocks_by_type() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    threats = query_clocks(clock_type="threat")
    assert len(threats) == 1
    assert threats[0].name == "Storm"
    close_db()


def test_query_clocks_by_fired() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    fired = query_clocks(fired=True)
    assert len(fired) == 1
    unfired = query_clocks(fired=False)
    assert len(unfired) == 1
    close_db()


def test_query_clocks_by_owner() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    kira_clocks = query_clocks(owner="Kira")
    assert len(kira_clocks) == 1
    assert kira_clocks[0].name == "Vault heist"
    close_db()


# ── Reset/restore ─────────────────────────────────────────────


def test_reset_clears_data() -> None:
    _fresh_db()
    sync(_game_with_npcs())
    conn = reset_db()
    assert conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0] == 0
    close_db()


def test_reset_then_sync_rebuilds() -> None:
    _fresh_db()
    game = _game_with_npcs()
    sync(game)
    reset_db()
    sync(game)
    assert len(query_npcs()) == 2
    assert len(query_memories()) == 4
    close_db()
