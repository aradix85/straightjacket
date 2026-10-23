from __future__ import annotations

import dataclasses
import logging
import random
import shutil
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml


def change_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    layer: ModuleType,
    cache: str,
    section: str,
    change: Callable[[dict[str, Any]], None],
) -> None:
    folder = tmp_path / layer._CONFIG_DIR.name
    shutil.copytree(layer._CONFIG_DIR, folder)
    path = folder / f"{section}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data[section])
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(layer, "_CONFIG_DIR", folder)
    monkeypatch.setattr(layer, cache, None)


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


def emit_engine_log(monkeypatch: pytest.MonkeyPatch, *modules: ModuleType) -> None:
    def log(msg: str, level: str = "info") -> None:
        logger = logging.getLogger("rpg_engine")
        logger.handle(logger.makeRecord(logger.name, logging.getLevelName(level.upper()), "", 0, msg, None, None))

    for module in modules:
        monkeypatch.setattr(module, "log", log)


def make_game_state(**kwargs: Any) -> Any:
    from straightjacket.engine.gamemaster.world import new_world
    from straightjacket.engine.models import GameState, PlayerPreferences
    from straightjacket.engine.ruleset.legacy import new_campaign
    from straightjacket.engine.ruleset.meters import starting_resources

    kwargs.setdefault("setting_id", "starforged")
    for name in ("player_name", "character_concept", "pronouns", "background_vow", "setting_genre"):
        kwargs.setdefault(name, "")
    for name in ("setting_tone", "setting_description", "backstory", "end_reason"):
        kwargs.setdefault(name, "")
    kwargs.setdefault("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    kwargs.setdefault("resources", starting_resources(kwargs["setting_id"]))
    kwargs.setdefault("world", new_world())
    kwargs.setdefault("narrative", make_narrative())
    kwargs.setdefault("campaign", new_campaign(kwargs["setting_id"]))
    kwargs.setdefault("preferences", PlayerPreferences(player_wishes="", content_lines=""))
    kwargs.setdefault("crisis_mode", False)
    kwargs.setdefault("last_turn_snapshot", None)
    kwargs.setdefault("post_epilogue_director_done", False)
    return GameState(**kwargs)


def make_narrative(**kwargs: Any) -> Any:
    from straightjacket.engine.director import new_guidance
    from straightjacket.engine.models import NarrativeState

    kwargs.setdefault("scene_count", 0)
    kwargs.setdefault("story_blueprint", None)
    kwargs.setdefault("director_guidance", new_guidance())
    return NarrativeState(**kwargs)


def make_thread(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ThreadEntry

    kwargs.setdefault("thread_type", "vow")
    kwargs.setdefault("source", "creation")
    kwargs.setdefault("weight", 1)
    kwargs.setdefault("linked_track_id", None)
    kwargs.setdefault("active", True)
    return ThreadEntry(**kwargs)


def make_character_entry(**kwargs: Any) -> Any:
    from straightjacket.engine.models import CharacterListEntry

    kwargs.setdefault("entry_type", "npc")
    kwargs.setdefault("weight", 1)
    kwargs.setdefault("active", True)
    kwargs.setdefault("ac_status", "")
    return CharacterListEntry(**kwargs)


def make_plotline(**kwargs: Any) -> Any:
    from straightjacket.engine.models import PlotlineEntry

    kwargs.setdefault("status", "advancement")
    kwargs.setdefault("turning_point_count", 0)
    return PlotlineEntry(**kwargs)


def make_keyed_scene(**kwargs: Any) -> Any:
    from straightjacket.engine.models import KeyedScene

    kwargs.setdefault("id", "ks_1")
    kwargs.setdefault("priority", 1)
    kwargs.setdefault("narrative_hint", "")
    kwargs.setdefault("bound_entity_id", None)
    kwargs.setdefault("source", "")
    return KeyedScene(**kwargs)


def make_npc(**kwargs: Any) -> Any:
    from straightjacket.engine.models import NpcData

    kwargs.setdefault("disposition", "neutral")
    kwargs.setdefault("status", "active")
    kwargs.setdefault("name_rolled", False)
    for name in ("description", "agenda", "instinct", "arc", "last_location"):
        kwargs.setdefault(name, "")
    kwargs.setdefault("introduced", False)
    kwargs.setdefault("importance_accumulator", 0)
    kwargs.setdefault("last_reflection_scene", 0)
    kwargs.setdefault("needs_reflection", False)
    kwargs.setdefault("gather_count", 0)
    return NpcData(**kwargs)


def make_clock(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ClockData

    kwargs.setdefault("clock_type", "threat")
    kwargs.setdefault("segments", 6)
    kwargs.setdefault("trigger_description", "")
    kwargs.setdefault("owner_kind", "world")
    kwargs.setdefault("creation_source", "setup")
    kwargs.setdefault("filled", 0)
    kwargs.setdefault("owner_id", None)
    kwargs.setdefault("fired", False)
    kwargs.setdefault("fired_at_scene", 0)
    return ClockData(**kwargs)


def make_progress_track(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ProgressTrack

    kwargs.setdefault("id", "track_test")
    kwargs.setdefault("name", "Test Track")
    kwargs.setdefault("track_type", "vow")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_ticks", 40)
    kwargs.setdefault("bound_impact", "")
    kwargs.setdefault("vowed_to", None)
    kwargs.setdefault("ticks", 0)
    kwargs.setdefault("status", "active")
    kwargs.setdefault("completions", 0)
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
    kwargs.setdefault("menace_ticks", 0)
    kwargs.setdefault("status", "active")
    return ThreatData(**kwargs)


def make_memory(**kwargs: Any) -> Any:
    from straightjacket.engine.models import MemoryEntry

    kwargs.setdefault("scene", 1)
    kwargs.setdefault("event", "")
    kwargs.setdefault("emotional_weight", "neutral")
    kwargs.setdefault("importance", 3)
    kwargs.setdefault("type", "observation")
    kwargs.setdefault("tone", "")
    kwargs.setdefault("tone_key", "")
    kwargs.setdefault("about_npc", None)
    return MemoryEntry(**kwargs)


def make_random_event(**kwargs: Any) -> Any:
    from straightjacket.engine.models import RandomEvent

    kwargs.setdefault("focus", "npc_action")
    kwargs.setdefault("meaning_action", "Act")
    kwargs.setdefault("meaning_subject", "Thing")
    kwargs.setdefault("source", "fate_doublet")
    kwargs.setdefault("target", "")
    kwargs.setdefault("target_id", "")
    return RandomEvent(**kwargs)


def make_outcome(**kwargs: Any) -> Any:
    from straightjacket.engine.ruleset.outcome_result import new_outcome

    return dataclasses.replace(new_outcome(), **kwargs)


def make_brain_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import BrainResult

    kwargs.setdefault("move", "dialog")
    kwargs.setdefault("stat", "none")
    kwargs.setdefault("approach", "")
    kwargs.setdefault("dialog_only", False)
    kwargs.setdefault("player_intent", "")
    for name in ("target_npc", "world_addition", "location_change", "track_name", "track_rank"):
        kwargs.setdefault(name, None)
    for name in ("target_track", "target_clock", "target_threat", "bonus_id"):
        kwargs.setdefault(name, None)
    return BrainResult(**kwargs)


def make_world_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import WorldState

    kwargs.setdefault("chaos_factor", 5)
    kwargs.setdefault("current_location", "")
    kwargs.setdefault("current_scene_context", "")
    kwargs.setdefault("time_of_day", "")
    kwargs.setdefault("combat_position", "")
    return WorldState(**kwargs)


def make_scene_setup(**kwargs: Any) -> Any:
    from straightjacket.engine.models import SceneSetup

    kwargs.setdefault("scene_type", "expected")
    kwargs.setdefault("interrupt_event", None)
    kwargs.setdefault("narrative_hint", "")
    return SceneSetup(**kwargs)


def make_scene_log_entry(**kwargs: Any) -> Any:
    from straightjacket.engine.models import SceneLogEntry

    kwargs.setdefault("scene", 1)
    kwargs.setdefault("scene_type", "expected")
    kwargs.setdefault("summary", "")
    kwargs.setdefault("move", "dialog")
    kwargs.setdefault("result", "dialog")
    for name in ("position", "effect", "rich_summary", "oracle_answer"):
        kwargs.setdefault(name, "")
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
    kwargs.setdefault("legacy_filled_boxes", {})
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
    kwargs.setdefault("consequence_sentences", [])
    kwargs.setdefault("player_words", "")
    kwargs.setdefault("scene_setup", make_scene_setup())
    kwargs.setdefault("activated_npcs", [])
    kwargs.setdefault("mentioned_npcs", [])
    kwargs.setdefault("position", "risky")
    kwargs.setdefault("effect", "standard")
    kwargs.setdefault("random_events", [])
    kwargs.setdefault("threat_events", [])
    kwargs.setdefault("clock_fill_results", [])
    kwargs.setdefault("facts", [])
    kwargs.setdefault("revelation", None)
    return kwargs


def dialog_prompt_kwargs(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("player_words", "")
    kwargs.setdefault("scene_setup", make_scene_setup())
    kwargs.setdefault("activated_npcs", [])
    kwargs.setdefault("mentioned_npcs", [])
    kwargs.setdefault("oracle_answer", "")
    kwargs.setdefault("random_events", [])
    kwargs.setdefault("threat_events", [])
    kwargs.setdefault("consequence_texts", [])
    kwargs.setdefault("clock_fill_results", [])
    kwargs.setdefault("npc_agency", [])
    kwargs.setdefault("facts", [])
    kwargs.setdefault("revelation", None)
    return kwargs


def dialog_prompt(game: Any, **kwargs: Any) -> str:
    from straightjacket.engine.prompt_dialog import build_dialog_prompt

    return build_dialog_prompt(game, make_brain_result(), **dialog_prompt_kwargs(**kwargs))


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
    kwargs.setdefault("act_number", 1)
    kwargs.setdefault("keyed_scene_source", "")
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
    kwargs.setdefault("story_complete", False)
    return StoryBlueprint(**kwargs)


def install_config(settings: tuple) -> None:
    from straightjacket.engine import engine_loader
    from straightjacket.engine.crafters import config as crafters_config
    from straightjacket.engine.gamemaster import config as gamemaster_config
    from straightjacket.engine.ruleset import config as ruleset_config

    engine_loader._eng, gamemaster_config._gm, crafters_config._crafter, ruleset_config._rules = settings
