from __future__ import annotations

from typing import Any


def make_game_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import GameState

    kwargs.setdefault("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    return GameState(**kwargs)


def make_npc(**kwargs: Any) -> Any:
    from straightjacket.engine.models import NpcData

    kwargs.setdefault("disposition", "neutral")
    kwargs.setdefault("status", "active")
    return NpcData(**kwargs)


def make_clock(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ClockData

    kwargs.setdefault("clock_type", "threat")
    kwargs.setdefault("segments", 6)
    kwargs.setdefault("trigger_description", "")
    return ClockData(**kwargs)


def make_progress_track(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ProgressTrack

    kwargs.setdefault("id", "track_test")
    kwargs.setdefault("name", "Test Track")
    kwargs.setdefault("track_type", "vow")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_ticks", 40)
    return ProgressTrack(**kwargs)


def make_threat(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ThreatData

    kwargs.setdefault("id", "threat_test")
    kwargs.setdefault("name", "Test Threat")
    kwargs.setdefault("category", "scheming_leader")
    kwargs.setdefault("linked_vow_id", "")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_menace_ticks", 40)
    kwargs.setdefault("description", "")
    return ThreatData(**kwargs)


def make_memory(**kwargs: Any) -> Any:
    from straightjacket.engine.models import MemoryEntry

    kwargs.setdefault("scene", 1)
    kwargs.setdefault("event", "")
    kwargs.setdefault("emotional_weight", "neutral")
    kwargs.setdefault("importance", 3)
    kwargs.setdefault("type", "observation")
    return MemoryEntry(**kwargs)


def make_fate_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import FateResult

    kwargs.setdefault("answer", "yes")
    kwargs.setdefault("odds", "fifty_fifty")
    kwargs.setdefault("chaos_factor", 5)
    kwargs.setdefault("method", "fate_chart")
    kwargs.setdefault("roll", 50)
    kwargs.setdefault("question", "")
    return FateResult(**kwargs)


def make_random_event(**kwargs: Any) -> Any:
    from straightjacket.engine.models import RandomEvent

    kwargs.setdefault("focus", "npc_action")
    kwargs.setdefault("focus_roll", 50)
    kwargs.setdefault("meaning_action", "Act")
    kwargs.setdefault("meaning_subject", "Thing")
    kwargs.setdefault("meaning_table", "actions")
    kwargs.setdefault("source", "fate_doublet")
    return RandomEvent(**kwargs)


def make_brain_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import BrainResult

    kwargs.setdefault("type", "action")
    kwargs.setdefault("move", "dialog")
    kwargs.setdefault("stat", "none")
    return BrainResult(**kwargs)


def make_world_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import WorldState

    kwargs.setdefault("chaos_factor", 5)
    return WorldState(**kwargs)


def make_scene_log_entry(**kwargs: Any) -> Any:
    from straightjacket.engine.models import SceneLogEntry

    kwargs.setdefault("scene_type", "expected")
    return SceneLogEntry(**kwargs)


def make_chapter_summary(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ChapterSummary

    kwargs.setdefault("chapter", 1)
    kwargs.setdefault("title", "")
    kwargs.setdefault("summary", "")
    kwargs.setdefault("unresolved_threads", [])
    kwargs.setdefault("character_growth", "")
    kwargs.setdefault("npc_evolutions", [])
    kwargs.setdefault("thematic_question", "")
    kwargs.setdefault("post_story_location", "")
    kwargs.setdefault("scenes", 0)
    kwargs.setdefault("progress_tracks", [])
    kwargs.setdefault("threats", [])
    kwargs.setdefault("impacts", [])
    kwargs.setdefault("assets", [])
    kwargs.setdefault("threads", [])
    return ChapterSummary(**kwargs)


def make_inheritance_roll(**kwargs: Any) -> Any:
    from straightjacket.engine.models import InheritanceRollResult

    kwargs.setdefault("track_name", "quests")
    kwargs.setdefault("predecessor_filled_boxes", 0)
    kwargs.setdefault("result", "MISS")
    kwargs.setdefault("fraction", 0.0)
    kwargs.setdefault("new_filled_boxes", 0)
    return InheritanceRollResult(**kwargs)


def make_predecessor(**kwargs: Any) -> Any:
    from straightjacket.engine.models import PredecessorRecord

    kwargs.setdefault("player_name", "Aria")
    kwargs.setdefault("pronouns", "she/her")
    kwargs.setdefault("character_concept", "")
    kwargs.setdefault("background_vow", "")
    kwargs.setdefault("setting_id", "classic")
    kwargs.setdefault("chapters_played", 1)
    kwargs.setdefault("scenes_played", 1)
    kwargs.setdefault("end_reason", "death")
    kwargs.setdefault("legacy_quests_filled_boxes", 0)
    kwargs.setdefault("legacy_bonds_filled_boxes", 0)
    kwargs.setdefault("legacy_discoveries_filled_boxes", 0)
    kwargs.setdefault("inheritance_rolls", [])
    return PredecessorRecord(**kwargs)
