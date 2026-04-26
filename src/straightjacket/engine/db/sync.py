from __future__ import annotations

import json
import sqlite3

from ..logging_util import log
from ..models import GameState
from .connection import get_db


def sync(game: GameState) -> None:
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM memories")
        conn.execute("DELETE FROM npcs")
        conn.execute("DELETE FROM threads")
        conn.execute("DELETE FROM characters_list")
        conn.execute("DELETE FROM clocks")
        conn.execute("DELETE FROM scene_log")
        conn.execute("DELETE FROM narration_history")
        conn.execute("DELETE FROM progress_tracks")
        conn.execute("DELETE FROM threats")

        _insert_npcs(conn, game)
        _insert_memories(conn, game)
        _insert_threads(conn, game)
        _insert_characters_list(conn, game)
        _insert_clocks(conn, game)
        _insert_scene_log(conn, game)
        _insert_narration_history(conn, game)
        _insert_progress_tracks(conn, game)
        _insert_threats(conn, game)
    log(f"[DB] Synced: {len(game.npcs)} npcs, {len(game.world.clocks)} clocks, scene {game.narrative.scene_count}")


def _insert_npcs(conn: sqlite3.Connection, game: GameState) -> None:
    for n in game.npcs:
        conn.execute(
            "INSERT INTO npcs (id, name, description, agenda, instinct, arc, secrets, "
            "disposition, status, introduced, aliases, keywords, "
            "importance_accumulator, last_reflection_scene, last_location, needs_reflection, "
            "gather_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                n.id,
                n.name,
                n.description,
                n.agenda,
                n.instinct,
                n.arc,
                json.dumps(n.secrets, ensure_ascii=False),
                n.disposition,
                n.status,
                int(n.introduced),
                json.dumps(n.aliases, ensure_ascii=False),
                json.dumps(n.keywords, ensure_ascii=False),
                n.importance_accumulator,
                n.last_reflection_scene,
                n.last_location,
                int(n.needs_reflection),
                n.gather_count,
            ),
        )


def _insert_memories(conn: sqlite3.Connection, game: GameState) -> None:
    for n in game.npcs:
        for m in n.memory:
            conn.execute(
                "INSERT INTO memories (npc_id, scene, event, emotional_weight, importance, "
                "type, about_npc, tone, tone_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (n.id, m.scene, m.event, m.emotional_weight, m.importance, m.type, m.about_npc, m.tone, m.tone_key),
            )


def _insert_threads(conn: sqlite3.Connection, game: GameState) -> None:
    for t in game.narrative.threads:
        conn.execute(
            "INSERT INTO threads (id, name, thread_type, weight, source, linked_track_id, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (t.id, t.name, t.thread_type, t.weight, t.source, t.linked_track_id, int(t.active)),
        )


def _insert_characters_list(conn: sqlite3.Connection, game: GameState) -> None:
    for c in game.narrative.characters_list:
        conn.execute(
            "INSERT OR IGNORE INTO characters_list (id, name, entry_type, weight, active) VALUES (?, ?, ?, ?, ?)",
            (c.id, c.name, c.entry_type, c.weight, int(c.active)),
        )


def _insert_clocks(conn: sqlite3.Connection, game: GameState) -> None:
    for c in game.world.clocks:
        conn.execute(
            "INSERT INTO clocks (name, clock_type, segments, filled, trigger_description, "
            "owner, fired, fired_at_scene) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                c.name,
                c.clock_type,
                c.segments,
                c.filled,
                c.trigger_description,
                c.owner,
                int(c.fired),
                c.fired_at_scene,
            ),
        )


def _insert_scene_log(conn: sqlite3.Connection, game: GameState) -> None:
    for s in game.narrative.session_log:
        conn.execute(
            "INSERT INTO scene_log (scene, summary, move, result, consequences, clock_events, "
            "position, effect, scene_type, npc_activation, validator, rich_summary, "
            "director_trigger, oracle_answer, revelation_check) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                s.scene,
                s.summary,
                s.move,
                s.result,
                json.dumps(s.consequences, ensure_ascii=False),
                json.dumps([e.to_dict() for e in s.clock_events], ensure_ascii=False),
                s.position,
                s.effect,
                s.scene_type,
                json.dumps(s.npc_activation, ensure_ascii=False),
                json.dumps(s.validator, ensure_ascii=False),
                s.rich_summary,
                s.director_trigger,
                s.oracle_answer,
                json.dumps(s.revelation_check, ensure_ascii=False),
            ),
        )


def _insert_narration_history(conn: sqlite3.Connection, game: GameState) -> None:
    for n in game.narrative.narration_history:
        conn.execute(
            "INSERT INTO narration_history (scene, prompt_summary, narration) VALUES (?, ?, ?)",
            (n.scene, n.prompt_summary, n.narration),
        )


def _insert_progress_tracks(conn: sqlite3.Connection, game: GameState) -> None:
    for t in game.progress_tracks:
        conn.execute(
            "INSERT INTO progress_tracks (id, name, track_type, rank, ticks, max_ticks, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (t.id, t.name, t.track_type, t.rank, t.ticks, t.max_ticks, t.status),
        )


def _insert_threats(conn: sqlite3.Connection, game: GameState) -> None:
    for t in game.threats:
        conn.execute(
            "INSERT INTO threats (id, name, category, description, linked_vow_id, "
            "rank, menace_ticks, max_menace_ticks, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                t.id,
                t.name,
                t.category,
                t.description,
                t.linked_vow_id,
                t.rank,
                t.menace_ticks,
                t.max_menace_ticks,
                t.status,
            ),
        )
