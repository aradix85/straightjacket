from __future__ import annotations

import dataclasses
import logging
import random
import shutil
from typing import TYPE_CHECKING, Any

import yaml

from straightjacket.engine.ai.provider_base import AICallSpec
from straightjacket.engine.ai.schemas import get_brain_output_schema
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.crafters.adventure_crafter import PlotPointHit, TurningPoint
from straightjacket.engine.director import new_guidance
from straightjacket.engine.gamemaster.world import new_world
from straightjacket.engine.models import (
    BrainResult,
    ChapterSummary,
    CharacterListEntry,
    ClockData,
    GameState,
    InheritanceRollResult,
    KeyedScene,
    MemoryEntry,
    NarrativeState,
    NpcData,
    PlayerPreferences,
    PlotlineEntry,
    PredecessorRecord,
    ProgressTrack,
    RandomEvent,
    RollResult,
    SceneLogEntry,
    SceneSetup,
    ThreadEntry,
    ThreatData,
    WorldState,
    consequence,
)
from straightjacket.engine.models_story import PossibleEnding, Revelation, StoryAct, StoryBlueprint
from straightjacket.engine.prompt_action import build_action_prompt
from straightjacket.engine.prompt_dialog import build_dialog_prompt
from straightjacket.engine.prompt_shared import PromptScene, TurnEvents
from straightjacket.engine.ruleset import move_effects
from straightjacket.engine.ruleset.legacy import new_campaign
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.ruleset.outcome_result import new_outcome

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType

    import pytest

    from straightjacket.engine.models import (
        Consequence,
    )
    from straightjacket.engine.ruleset.datasworn import Asset, RulesFile
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult


def change_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    layer: ModuleType,
    section: str,
    change: Callable[[dict[str, Any]], None],
) -> None:
    layer_folder = layer.__name__.split(".")[-2]
    folder = tmp_path / layer_folder
    shutil.copytree(PROJECT_ROOT / layer_folder, folder)
    path = folder / f"{section}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data[section])
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(layer, "_CONFIG_DIR", folder)


def fix_dice(monkeypatch: pytest.MonkeyPatch, *rolls: int) -> None:
    queue = list(rolls)
    real = random.randint
    monkeypatch.setattr(random, "randint", lambda low, high: queue.pop(0) if queue else real(low, high))


def record_price_tables(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    rolled: list[str] = []
    real = move_effects.roll_oracle_result

    def recording(table: Any) -> tuple[list[str], Consequence]:
        rolled.append(table.title)
        return real(table)

    monkeypatch.setattr(move_effects, "roll_oracle_result", recording)
    return rolled


def emit_engine_log(monkeypatch: pytest.MonkeyPatch, *modules: ModuleType) -> None:
    def log(msg: str, level: str = "info") -> None:
        logger = logging.getLogger("rpg_engine")
        logger.handle(
            logger.makeRecord(logger.name, logging.getLevelNamesMapping()[level.upper()], "", 0, msg, (), None)
        )

    for module in modules:
        monkeypatch.setattr(module, "log", log)


def use_users_dir(monkeypatch: pytest.MonkeyPatch, users: Path) -> None:
    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, users)


def make_game_state(**kwargs: Any) -> GameState:
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


def make_narrative(**kwargs: Any) -> NarrativeState:
    kwargs.setdefault("scene_count", 0)
    kwargs.setdefault("story_blueprint", None)
    kwargs.setdefault("director_guidance", new_guidance())
    return NarrativeState(**kwargs)


def make_thread(**kwargs: Any) -> ThreadEntry:
    kwargs.setdefault("thread_type", "vow")
    kwargs.setdefault("source", "creation")
    kwargs.setdefault("weight", 1)
    kwargs.setdefault("linked_track_id", None)
    kwargs.setdefault("active", True)
    return ThreadEntry(**kwargs)


def make_character_entry(**kwargs: Any) -> CharacterListEntry:
    kwargs.setdefault("entry_type", "npc")
    kwargs.setdefault("weight", 1)
    kwargs.setdefault("active", True)
    kwargs.setdefault("ac_status", "")
    return CharacterListEntry(**kwargs)


def make_plotline(**kwargs: Any) -> PlotlineEntry:
    kwargs.setdefault("status", "advancement")
    kwargs.setdefault("turning_point_count", 0)
    return PlotlineEntry(**kwargs)


def make_keyed_scene(**kwargs: Any) -> KeyedScene:
    kwargs.setdefault("id", "ks_1")
    kwargs.setdefault("priority", 1)
    kwargs.setdefault("narrative_hint", "")
    kwargs.setdefault("bound_entity_id", None)
    kwargs.setdefault("source", "")
    return KeyedScene(**kwargs)


def make_turning_point(*plot_point_names: str) -> TurningPoint:
    return TurningPoint(
        plot_points=[PlotPointHit(theme="action", name=name, special_range=None) for name in plot_point_names],
        plotline="Plotline 1",
        opens_plotline=True,
        concludes_plotline=False,
    )


def make_npc(**kwargs: Any) -> NpcData:
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


def friendly_kira(**kwargs: Any) -> NpcData:
    return make_npc(id="npc_1", name="Kira", disposition="friendly", **kwargs)


def make_clock(**kwargs: Any) -> ClockData:
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


def make_progress_track(**kwargs: Any) -> ProgressTrack:
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


def docks_game(npc: NpcData | None, *, scene: int, bond: int) -> GameState:
    game = make_game_state(player_name="Ash", setting_id="starforged", setting_genre="starforged")
    game.world.current_location = "The Docks"
    game.narrative.scene_count = scene
    if npc is not None:
        game.npcs.append(npc)
        if bond > 0:
            game.progress_tracks.append(
                make_progress_track(
                    id=f"connection_{npc.id}", name=npc.name, track_type="connection", rank="dangerous", ticks=bond * 4
                )
            )
    return game


def make_threat(**kwargs: Any) -> ThreatData:
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


def make_memory(**kwargs: Any) -> MemoryEntry:
    kwargs.setdefault("scene", 1)
    kwargs.setdefault("event", "")
    kwargs.setdefault("emotional_weight", "neutral")
    kwargs.setdefault("importance", 3)
    kwargs.setdefault("type", "observation")
    kwargs.setdefault("tone", "")
    kwargs.setdefault("tone_key", "")
    kwargs.setdefault("about_npc", None)
    return MemoryEntry(**kwargs)


def make_random_event(**kwargs: Any) -> RandomEvent:
    kwargs.setdefault("focus", "npc_action")
    kwargs.setdefault("meaning_action", "Act")
    kwargs.setdefault("meaning_subject", "Thing")
    kwargs.setdefault("source", "fate_doublet")
    kwargs.setdefault("target", "")
    kwargs.setdefault("target_id", "")
    return RandomEvent(**kwargs)


def make_outcome(**kwargs: Any) -> OutcomeResult:
    return dataclasses.replace(new_outcome(), **kwargs)


def make_brain_result(**kwargs: Any) -> BrainResult:
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


def make_world_state(**kwargs: Any) -> WorldState:
    kwargs.setdefault("chaos_factor", 5)
    kwargs.setdefault("current_location", "")
    kwargs.setdefault("current_scene_context", "")
    kwargs.setdefault("time_of_day", "")
    kwargs.setdefault("combat_position", "")
    return WorldState(**kwargs)


def make_scene_setup(**kwargs: Any) -> SceneSetup:
    kwargs.setdefault("scene_type", "expected")
    kwargs.setdefault("interrupt_event", None)
    kwargs.setdefault("narrative_hint", "")
    return SceneSetup(**kwargs)


def make_scene_log_entry(**kwargs: Any) -> SceneLogEntry:
    kwargs.setdefault("scene", 1)
    kwargs.setdefault("scene_type", "expected")
    kwargs.setdefault("summary", "")
    kwargs.setdefault("move", "dialog")
    kwargs.setdefault("result", "dialog")
    for name in ("position", "effect", "rich_summary", "oracle_answer"):
        kwargs.setdefault(name, "")
    return SceneLogEntry(**kwargs)


def make_chapter_summary(**kwargs: Any) -> ChapterSummary:
    kwargs.setdefault("chapter", 1)
    kwargs.setdefault("title", "")
    kwargs.setdefault("summary", "")
    kwargs.setdefault("unresolved_threads", [])
    return ChapterSummary(**kwargs)


def make_inheritance_roll(**kwargs: Any) -> InheritanceRollResult:
    kwargs.setdefault("track_name", "quests")
    kwargs.setdefault("result", "MISS")
    kwargs.setdefault("new_filled_boxes", 0)
    return InheritanceRollResult(**kwargs)


def make_predecessor(**kwargs: Any) -> PredecessorRecord:
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


def make_npc_reflection(**kwargs: Any) -> dict[str, Any]:
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


def keyed_reflections(*refs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ref["npc_id"]: {k: v for k, v in ref.items() if k != "npc_id"} for ref in refs}


def make_npc_detail(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("npc_id", "npc_1")
    kwargs.setdefault("full_name", None)
    kwargs.setdefault("description", None)
    return kwargs


def make_npc_rename(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("npc_id", "npc_1")
    kwargs.setdefault("new_name", "")
    return kwargs


def _prompt_kwargs(overrides: dict[str, Any], **defaults: Any) -> dict[str, Any]:
    scene: dict[str, Any] = {
        "player_words": "",
        "scene_setup": make_scene_setup(),
        "activated_npcs": [],
        "mentioned_npcs": [],
    }
    events: dict[str, Any] = {
        "random_events": [],
        "threat_events": [],
        "clock_fill_results": [],
        "npc_agency": [],
        "revelation": None,
    }
    rest = dict(defaults)
    for key, value in overrides.items():
        target = scene if key in scene else events if key in events else rest
        target[key] = value
    return {"scene": PromptScene(**scene), "events": TurnEvents(**events), **rest}


def action_prompt_kwargs(**kwargs: Any) -> dict[str, Any]:
    return _prompt_kwargs(
        kwargs, consequences=[], consequence_sentences=[], position="risky", effect="standard", facts=[]
    )


def dialog_prompt_kwargs(**kwargs: Any) -> dict[str, Any]:
    return _prompt_kwargs(kwargs, result="dialog", oracle_answer="", consequence_texts=[], facts=[])


def brain_schema(move_keys: list[str], **choices: list[str]) -> dict[str, Any]:
    lists: dict[str, list[str]] = {
        "stat_names": [],
        "bonus_ids": [],
        "npc_ids": [],
        "track_ids": [],
        "clock_names": [],
        "threat_ids": [],
    }
    return get_brain_output_schema(move_keys=move_keys, **(lists | choices))


def dialog_prompt(game: Any, **kwargs: Any) -> str:
    return build_dialog_prompt(game, make_brain_result(), **dialog_prompt_kwargs(**kwargs))


def action_prompt(game: GameState, brain: BrainResult, result: str, **kwargs: Any) -> str:
    roll = RollResult(
        d1=3,
        c1=6,
        c2=7,
        stat_name=brain.stat,
        stat_value=2,
        action_score=9,
        result=result,
        move=brain.move,
        match=False,
    )
    return build_action_prompt(game, brain, roll, **action_prompt_kwargs(**kwargs))


def weak_hit_prompt(game: GameState, brain: BrainResult, player_words: str) -> str:
    return action_prompt(
        game,
        brain,
        "WEAK_HIT",
        consequences=[consequence("momentum_change", n=1)],
        consequence_sentences=["The tide shifts."],
        player_words=player_words,
    )


def make_state_op(**kwargs: Any) -> dict[str, Any]:
    for name in ("npc_id", "fields", "split_name", "split_description", "merge_source_id", "value"):
        kwargs.setdefault(name, None)
    return kwargs


def make_director_guidance(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("scene_summary", "")
    kwargs.setdefault("narrator_guidance", "")
    kwargs.setdefault("npc_guidance", {})
    kwargs.setdefault("npc_reflections", {})
    kwargs.setdefault("arc_notes", "")
    return kwargs


def make_act(**kwargs: Any) -> StoryAct:
    kwargs.setdefault("phase", "setup")
    kwargs.setdefault("title", "")
    kwargs.setdefault("goal", "")
    kwargs.setdefault("scene_range", [1, 5])
    kwargs.setdefault("mood", "")
    kwargs.setdefault("transition_trigger", "")
    return StoryAct(**kwargs)


def make_revelation(**kwargs: Any) -> Revelation:
    kwargs.setdefault("id", "r1")
    kwargs.setdefault("content", "")
    kwargs.setdefault("act_number", 1)
    kwargs.setdefault("keyed_scene_source", "")
    kwargs.setdefault("dramatic_weight", "medium")
    return Revelation(**kwargs)


def make_ending(**kwargs: Any) -> PossibleEnding:
    kwargs.setdefault("type", "")
    kwargs.setdefault("description", "")
    return PossibleEnding(**kwargs)


def make_blueprint(**kwargs: Any) -> StoryBlueprint:
    kwargs.setdefault("central_conflict", "")
    kwargs.setdefault("antagonist_force", "")
    kwargs.setdefault("thematic_thread", "")
    kwargs.setdefault("story_complete", False)
    return StoryBlueprint(**kwargs)


def schema_of(spec: AICallSpec) -> dict[str, Any]:
    assert spec.json_schema is not None
    return spec.json_schema


def make_ai_call_spec(**kwargs: Any) -> AICallSpec:
    kwargs.setdefault("model", "test-model")
    kwargs.setdefault("system", "system text")
    kwargs.setdefault("messages", [{"role": "user", "content": "hello"}])
    kwargs["sampling"] = {
        "max_tokens": kwargs.pop("max_tokens", 64),
        "max_retries": kwargs.pop("max_retries", 0),
        "temperature": kwargs.pop("temperature", None),
        "top_p": kwargs.pop("top_p", None),
        "extra_body": kwargs.pop("extra_body", {}),
    }
    for name in ("json_schema", "tools"):
        kwargs.setdefault(name, None)
    kwargs.setdefault("log_role", "narrator")
    kwargs.setdefault("cached_system_prefix", "")
    return AICallSpec(**kwargs)


def every_role(cluster: str) -> dict[str, str]:
    shipped = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
    return dict.fromkeys(shipped["ai"]["role_cluster"], cluster)


def config_data(*, providers: dict[str, Any], clusters: dict[str, Any], role_cluster: dict[str, str]) -> dict[str, Any]:
    return {
        "server": {"host": "127.0.0.1", "port": 8081, "stream_narration": True},
        "language": {"narration_language": "English"},
        "ai": {"prompts_dir": "prompts", "providers": providers, "clusters": clusters, "role_cluster": role_cluster},
    }


def known_asset(setting_file: RulesFile, category: str, asset_id: str) -> Asset:
    found = setting_file.asset(category, asset_id)
    assert found is not None
    return found
