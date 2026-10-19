from __future__ import annotations

import random
from typing import Any

import pytest


def fix_dice(monkeypatch: pytest.MonkeyPatch, *rolls: int) -> None:
    queue = list(rolls)
    real = random.randint
    monkeypatch.setattr(random, "randint", lambda low, high: queue.pop(0) if queue else real(low, high))


def record_price_tables(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from straightjacket.engine.ruleset import move_effects

    rolled: list[str] = []
    real = move_effects.roll_oracle_result

    def recording(table: Any) -> tuple[list[str], str]:
        rolled.append(table.title)
        return real(table)

    monkeypatch.setattr(move_effects, "roll_oracle_result", recording)
    return rolled


def make_game_state(**kwargs: Any) -> Any:
    from straightjacket.engine.gamemaster.world import new_world
    from straightjacket.engine.models import GameState
    from straightjacket.engine.ruleset.legacy import new_campaign
    from straightjacket.engine.ruleset.meters import starting_resources

    kwargs.setdefault("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    kwargs.setdefault("resources", starting_resources())
    kwargs.setdefault("world", new_world())
    kwargs.setdefault("campaign", new_campaign())
    return GameState(**kwargs)


def make_npc(**kwargs: Any) -> Any:
    from straightjacket.engine.models import NpcData

    kwargs.setdefault("disposition", "neutral")
    kwargs.setdefault("status", "active")
    kwargs.setdefault("name_rolled", False)
    return NpcData(**kwargs)


def make_clock(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ClockData

    kwargs.setdefault("clock_type", "threat")
    kwargs.setdefault("segments", 6)
    kwargs.setdefault("trigger_description", "")
    kwargs.setdefault("owner_kind", "world")
    kwargs.setdefault("creation_source", "setup")
    return ClockData(**kwargs)


def make_progress_track(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ProgressTrack

    kwargs.setdefault("id", "track_test")
    kwargs.setdefault("name", "Test Track")
    kwargs.setdefault("track_type", "vow")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_ticks", 40)
    kwargs.setdefault("bound_impact", "")
    return ProgressTrack(**kwargs)


def make_threat(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ThreatData

    kwargs.setdefault("id", "threat_test")
    kwargs.setdefault("name", "Test Threat")
    kwargs.setdefault("category", "scheming_leader")
    kwargs.setdefault("linked_vow_id", None)
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_menace_ticks", 40)
    kwargs.setdefault("description", "")
    kwargs.setdefault("creation_source", "setup")
    return ThreatData(**kwargs)


def make_memory(**kwargs: Any) -> Any:
    from straightjacket.engine.models import MemoryEntry

    kwargs.setdefault("scene", 1)
    kwargs.setdefault("event", "")
    kwargs.setdefault("emotional_weight", "neutral")
    kwargs.setdefault("importance", 3)
    kwargs.setdefault("type", "observation")
    return MemoryEntry(**kwargs)


def make_random_event(**kwargs: Any) -> Any:
    from straightjacket.engine.models import RandomEvent

    kwargs.setdefault("focus", "npc_action")
    kwargs.setdefault("meaning_action", "Act")
    kwargs.setdefault("meaning_subject", "Thing")
    kwargs.setdefault("source", "fate_doublet")
    return RandomEvent(**kwargs)


def make_brain_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import BrainResult

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
    return ChapterSummary(**kwargs)


def make_inheritance_roll(**kwargs: Any) -> Any:
    from straightjacket.engine.models import InheritanceRollResult

    kwargs.setdefault("track_name", "quests")
    kwargs.setdefault("result", "MISS")
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


def make_npc_reflection(**kwargs: Any) -> dict:
    kwargs.setdefault("npc_id", "npc_1")
    kwargs.setdefault("reflection", "Reflection text.")
    kwargs.setdefault("tone", "")
    kwargs.setdefault("tone_key", "neutral")
    kwargs.setdefault("updated_description", "")
    kwargs.setdefault("about_npc", "")
    kwargs.setdefault("agenda", "")
    kwargs.setdefault("instinct", "")
    kwargs.setdefault("updated_agenda", "")
    kwargs.setdefault("updated_arc", "")
    return kwargs


def keyed_reflections(*refs: dict) -> dict:
    return {ref["npc_id"]: {k: v for k, v in ref.items() if k != "npc_id"} for ref in refs}


def make_npc_detail(**kwargs: Any) -> dict:
    kwargs.setdefault("npc_id", "npc_1")
    kwargs.setdefault("full_name", None)
    kwargs.setdefault("description", None)
    return kwargs


def make_npc_rename(**kwargs: Any) -> dict:
    kwargs.setdefault("npc_id", "npc_1")
    kwargs.setdefault("new_name", "")
    return kwargs


def action_prompt_kwargs(**kwargs: Any) -> dict[str, Any]:
    from straightjacket.engine.models import SceneSetup

    kwargs.setdefault("consequence_sentences", [])
    kwargs.setdefault("player_words", "")
    kwargs.setdefault("scene_setup", SceneSetup(scene_type="expected"))
    kwargs.setdefault("activated_npcs", [])
    kwargs.setdefault("mentioned_npcs", [])
    kwargs.setdefault("position", "risky")
    kwargs.setdefault("effect", "standard")
    kwargs.setdefault("random_events", [])
    kwargs.setdefault("threat_events", [])
    kwargs.setdefault("clock_fill_results", [])
    kwargs.setdefault("facts", [])
    return kwargs


def dialog_prompt_kwargs(**kwargs: Any) -> dict[str, Any]:
    from straightjacket.engine.models import SceneSetup

    kwargs.setdefault("player_words", "")
    kwargs.setdefault("scene_setup", SceneSetup(scene_type="expected"))
    kwargs.setdefault("activated_npcs", [])
    kwargs.setdefault("mentioned_npcs", [])
    kwargs.setdefault("oracle_answer", "")
    kwargs.setdefault("random_events", [])
    kwargs.setdefault("threat_events", [])
    kwargs.setdefault("consequences", [])
    kwargs.setdefault("clock_fill_results", [])
    kwargs.setdefault("npc_agency", [])
    kwargs.setdefault("facts", [])
    return kwargs


def make_director_guidance(**kwargs: Any) -> dict:
    kwargs.setdefault("scene_summary", "")
    kwargs.setdefault("narrator_guidance", "")
    kwargs.setdefault("npc_guidance", {})
    kwargs.setdefault("npc_reflections", {})
    kwargs.setdefault("arc_notes", "")
    return kwargs


def make_act(**kwargs: Any) -> Any:
    from straightjacket.engine.models_story import StoryAct

    kwargs.setdefault("phase", "setup")
    kwargs.setdefault("title", "")
    kwargs.setdefault("goal", "")
    kwargs.setdefault("scene_range", [1, 5])
    kwargs.setdefault("mood", "")
    kwargs.setdefault("transition_trigger", "")
    return StoryAct(**kwargs)


def make_revelation(**kwargs: Any) -> Any:
    from straightjacket.engine.models_story import Revelation

    kwargs.setdefault("id", "r1")
    kwargs.setdefault("content", "")
    kwargs.setdefault("earliest_scene", 1)
    kwargs.setdefault("dramatic_weight", "medium")
    return Revelation(**kwargs)


def make_ending(**kwargs: Any) -> Any:
    from straightjacket.engine.models_story import PossibleEnding

    kwargs.setdefault("type", "")
    kwargs.setdefault("description", "")
    return PossibleEnding(**kwargs)


def make_blueprint(**kwargs: Any) -> Any:
    from straightjacket.engine.models_story import StoryBlueprint

    kwargs.setdefault("central_conflict", "")
    kwargs.setdefault("antagonist_force", "")
    kwargs.setdefault("thematic_thread", "")
    kwargs.setdefault("structure_type", "3act")
    return StoryBlueprint(**kwargs)


def install_config(settings: tuple) -> None:
    from straightjacket.engine import engine_loader
    from straightjacket.engine.crafters import config as crafters_config
    from straightjacket.engine.gamemaster import config as gamemaster_config
    from straightjacket.engine.ruleset import config as ruleset_config

    engine_loader._eng, gamemaster_config._gm, crafters_config._crafter, ruleset_config._rules = settings
