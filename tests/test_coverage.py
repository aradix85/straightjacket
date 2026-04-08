#!/usr/bin/env python3
"""Targeted tests for modules not covered by domain-specific test files.

Every test here exists because it catches a real bug or verifies a non-obvious behavior.
Coverage-padding tests (empty-input returns empty, pass-through returns same object) removed.
"""

import json

from straightjacket.engine import engine_loader, emotions_loader
from straightjacket.engine.config_loader import _ConfigNode
from straightjacket.engine.models import (
    ClockData,
    GameState,
    NpcData,
    SceneLogEntry,
    StoryAct,
    StoryBlueprint,
)


def _stub() -> None:
    engine_loader._eng = _ConfigNode(
        {
            "bonds": {"start": 0, "max": 4},
            "npc": {
                "max_active": 12,
                "reflection_threshold": 30,
                "max_memory_entries": 25,
                "max_observations": 15,
                "max_reflections": 8,
                "memory_recency_decay": 0.92,
                "activation_threshold": 0.7,
                "mention_threshold": 0.3,
                "max_activated": 3,
            },
            "activation_scores": {
                "target": 1.0,
                "name_match": 0.8,
                "name_part": 0.6,
                "alias_match": 0.7,
                "location_match": 0.3,
                "recent_interaction": 0.2,
                "max_recursive": 1,
            },
            "resources": {"health_max": 5, "spirit_max": 5, "supply_max": 5},
            "momentum": {
                "floor": -6,
                "max": 10,
                "start": 2,
                "gain": {"weak_hit": 1, "strong_hit": {"standard": 2, "great": 3}},
                "loss": {"risky": 2, "desperate": 3},
            },
            "chaos": {"min": 3, "max": 9, "start": 5, "interrupt_types": ["twist"]},
            "pacing": {
                "window_size": 5,
                "intense_threshold": 3,
                "calm_threshold": 2,
                "max_narration_history": 5,
                "max_session_log": 50,
                "director_interval": 3,
                "autonomous_clock_tick_chance": 0.20,
                "weak_hit_clock_tick_chance": 0.50,
            },
            "location": {"history_size": 5},
            "narrative_direction": {
                "intensity": {"critical_below": 1, "high_below": 3, "moderate_below": 4},
                "result_map": {
                    "MISS": {"tempo": "slow", "perspective": "sensory_loss"},
                    "WEAK_HIT": {"tempo": "moderate", "perspective": "action_detail"},
                    "STRONG_HIT": {"tempo": "brisk", "perspective": "action_detail"},
                    "dialog": {"tempo": "measured", "perspective": "dialogue_rhythm"},
                    "_default": {"tempo": "moderate", "perspective": "action_detail"},
                },
            },
            "move_categories": {
                "combat": ["clash"],
                "social": ["compel"],
                "endure": [],
                "recovery": [],
                "bond_on_weak_hit": [],
                "bond_on_strong_hit": [],
                "disposition_shift_on_strong_hit": [],
            },
            "disposition_shifts": {"neutral": "friendly"},
            "disposition_to_seed_emotion": {"neutral": "neutral", "friendly": "curious"},
            "story": {"kishotenketsu_probability": {}, "kishotenketsu_default": 0.5},
            "creativity_seeds": ["amber", "coyote"],
        },
        "engine",
    )
    emotions_loader._data = {
        "importance": {"neutral": 2, "curious": 3},
        "keyword_boosts": {},
        "disposition_map": {"neutral": "neutral", "friendly": "friendly"},
    }


def _game() -> GameState:
    g = GameState(
        player_name="Hero",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A dark world.",
        edge=1,
        heart=2,
        iron=1,
        shadow=1,
        wits=2,
        backstory="Was a farmer.",
    )
    g.narrative.scene_count = 5
    g.world.current_location = "Tavern"
    g.world.time_of_day = "evening"
    g.world.chaos_factor = 5
    g.resources.health = 3
    g.resources.spirit = 4
    g.preferences.content_lines = "no spiders"
    g.preferences.player_wishes = "a loyal dog"
    g.npcs = [NpcData(id="npc_1", name="Kira", disposition="friendly", bond=2)]
    return g


class _MockResponse:
    def __init__(self, content: str, stop_reason: str = "complete") -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.tool_calls: list = []
        self.usage = {"input_tokens": 10, "output_tokens": 10}


class _MockProvider:
    def __init__(self, response_content: str = "", fail: bool = False) -> None:
        self._content = response_content
        self._fail = fail
        self.calls: list = []

    def create_message(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
        json_schema: dict | None = None,
        tools: list | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
    ) -> _MockResponse:
        self.calls.append({"system": system, "json_schema": json_schema})
        if self._fail:
            raise ConnectionError("mock fail")
        return _MockResponse(self._content)


# ── validator.py ─────────────────────────────────────────────


def test_validate_narration_returns_violations() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_narration

    provider = _MockProvider(
        json.dumps({"pass": False, "violations": ["Silver lining on MISS"], "correction": "Make it worse."})
    )
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "Bad narration.",
        "MISS",
        "dark_fantasy",
    )
    assert result["pass"] is False
    assert len(result["violations"]) == 1


def test_validate_narration_fail_open_on_api_error() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_narration

    provider = _MockProvider(fail=True)
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "Text.",
        "MISS",
        "dark_fantasy",
    )
    assert result["pass"] is True


def test_validate_narration_catches_genre_violation_rule_based() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_narration

    provider = _MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    gc = {"forbidden_terms": ["magic"], "forbidden_concepts": [], "genre_test": ""}
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "She cast a magic spell.",
        "MISS",
        "realistic",
        genre_constraints=gc,
    )
    assert result["pass"] is False
    assert any("magic" in v for v in result["violations"])


def test_validate_and_retry_actually_retries() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_and_retry

    call_count = [0]

    class RetryProvider:
        def create_message(  # type: ignore[override, no-untyped-def]
            self,
            model: str,
            system: str,
            messages: list,
            max_tokens: int,
            json_schema: dict | None = None,
            tools: list | None = None,
            temperature: float | None = None,
            top_p: float | None = None,
            top_k: int | None = None,
        ):
            call_count[0] += 1
            if json_schema and "pass" in json_schema.get("properties", {}):
                if call_count[0] <= 2:
                    return _MockResponse(json.dumps({"pass": False, "violations": ["bad"], "correction": "fix it"}))
                return _MockResponse(json.dumps({"pass": True, "violations": [], "correction": ""}))
            return _MockResponse("Rewritten narration.")

    game = _game()
    _, report = validate_and_retry(RetryProvider(), "Bad narration.", "prompt", "MISS", game, max_retries=2)
    assert report["retries"] >= 1
    assert len(report["checks"]) >= 2


def test_validate_architect_fixes_violations() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_architect

    provider = _MockProvider(
        json.dumps(
            {
                "pass": False,
                "violations": ["magic detected"],
                "fixed_conflict": "Political conspiracy",
                "fixed_antagonist": "Corrupt senator",
            }
        )
    )
    bp = {"central_conflict": "Magic war", "antagonist_force": "Evil wizard"}
    gc = {"forbidden_terms": ["magic"], "forbidden_concepts": [], "genre_test": ""}
    result = validate_architect(
        provider,  # type: ignore[arg-type]
        bp,
        "realistic",
        "serious",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Political conspiracy"
    assert result["antagonist_force"] == "Corrupt senator"


def test_validate_architect_fail_open_on_api_error() -> None:
    _stub()
    from straightjacket.engine.ai.validator import validate_architect

    provider = _MockProvider(fail=True)
    bp = {"central_conflict": "Original", "antagonist_force": "Original"}
    gc = {"forbidden_terms": ["x"], "forbidden_concepts": [], "genre_test": ""}
    result = validate_architect(
        provider,  # type: ignore[arg-type]
        bp,
        "genre",
        "tone",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Original"


# ── setup_common.py ──────────────────────────────────────────


def test_register_extracted_npcs_skips_player() -> None:
    _stub()
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = GameState(player_name="Hero")
    game.world.current_location = "Tavern"
    max_id = register_extracted_npcs(
        game,
        [
            {"name": "Mira", "description": "Scout", "disposition": "friendly"},
            {"name": "Hero", "description": "Player", "disposition": "neutral"},
        ],
    )
    assert len(game.npcs) == 1
    assert game.npcs[0].name == "Mira"
    assert max_id == 1


def test_register_extracted_npcs_skips_returning() -> None:
    _stub()
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = GameState(player_name="Hero")
    register_extracted_npcs(
        game,
        [
            {"name": "Kira", "description": "Scout", "disposition": "friendly"},
            {"name": "Borin", "description": "Smith", "disposition": "neutral"},
        ],
        skip_names={"kira"},
    )
    names = {n.name for n in game.npcs}
    assert "Kira" not in names
    assert "Borin" in names


def test_seed_opening_memories_matches_and_skips() -> None:
    _stub()
    from straightjacket.engine.game.setup_common import seed_opening_memories

    game = GameState(player_name="Hero")
    game.narrative.scene_count = 1
    game.npcs = [NpcData(id="npc_1", name="Captain Ashwood")]
    seed_opening_memories(
        game,
        [
            {"npc_name": "Ashwood", "event": "Nodded at player", "emotional_weight": "neutral"},
            {"npc_name": "Nobody", "event": "Should be skipped", "emotional_weight": "neutral"},
        ],
    )
    assert len(game.npcs[0].memory) == 1


def test_apply_world_setup_replace_vs_extend() -> None:
    _stub()
    from straightjacket.engine.game.setup_common import apply_world_setup

    game = GameState(player_name="Hero")
    game.world.clocks = [ClockData(name="Old")]
    apply_world_setup(
        game,
        {
            "clocks": [{"name": "New", "clock_type": "threat", "segments": 4, "filled": 1}],
            "location": "Market",
            "scene_context": "Busy.",
            "time_of_day": "midday",
        },
        clocks_mode="replace",
    )
    assert len(game.world.clocks) == 1
    assert game.world.clocks[0].name == "New"

    game.world.clocks = [ClockData(name="Old")]
    apply_world_setup(
        game,
        {
            "clocks": [{"name": "New2", "clock_type": "threat", "segments": 4, "filled": 0}],
        },
        clocks_mode="extend",
    )
    assert len(game.world.clocks) == 2


# ── prompt_blocks.py ─────────────────────────────────────────


def _load_prompts() -> None:
    from straightjacket.engine import prompt_loader

    prompt_loader._prompts = None
    prompt_loader._ensure_loaded()


def test_status_context_maps_resources() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import status_context_block

    result = status_context_block(_game())
    assert "<character_state>" in result


def test_narrative_direction_maps_result() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import narrative_direction_block

    result = narrative_direction_block(_game(), "MISS")
    assert "tempo:slow" in result


def test_narrative_direction_intensity_critical_on_crisis() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import narrative_direction_block

    game = _game()
    game.resources.health = 0
    game.crisis_mode = True
    assert "intensity:critical" in narrative_direction_block(game, "MISS")


def test_story_context_block_includes_conflict() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import story_context_block

    game = _game()
    game.narrative.story_blueprint = StoryBlueprint(
        central_conflict="Shadow rises",
        structure_type="3act",
        thematic_thread="Cost of survival",
        acts=[StoryAct(phase="setup", title="Gathering", goal="Find allies", scene_range=[1, 7], mood="mysterious")],
    )
    assert "Shadow rises" in story_context_block(game)


def test_story_context_block_epilogue_dismissed_open_ended() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import story_context_block

    game = _game()
    game.narrative.scene_count = 25
    game.campaign.epilogue_dismissed = True
    game.narrative.story_blueprint = StoryBlueprint(
        central_conflict="X",
        structure_type="3act",
        thematic_thread="Y",
        acts=[StoryAct(phase="climax", title="C", scene_range=[15, 20])],
        triggered_transitions=["act_0"],
        story_complete=True,
        possible_endings=[],
    )
    assert "open-ended play" in story_context_block(game)


def test_recent_events_block_includes_summaries() -> None:
    _stub()
    from straightjacket.engine.prompt_blocks import recent_events_block

    game = _game()
    game.narrative.session_log = [
        SceneLogEntry(scene=3, summary="Found a clue"),
        SceneLogEntry(scene=4, summary="Met an ally"),
        SceneLogEntry(scene=5, summary="Current"),
    ]
    result = recent_events_block(game)
    assert "Found a clue" in result


def test_campaign_history_block_includes_chapters() -> None:
    _stub()
    _load_prompts()
    from straightjacket.engine.prompt_blocks import campaign_history_block
    from straightjacket.engine.models_story import ChapterSummary

    game = _game()
    game.campaign.campaign_history = [ChapterSummary(chapter=1, title="The Beginning", summary="It all started here.")]
    result = campaign_history_block(game)
    assert "The Beginning" in result


# ── provider_base.py ─────────────────────────────────────────


def test_post_process_strips_think_tags() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    resp = AIResponse(content="<think>reasoning</think>The actual response.")
    assert "<think>" not in post_process_response(resp).content


def test_post_process_preserves_think_on_tool_use() -> None:
    from straightjacket.engine.ai.provider_base import AIResponse, post_process_response

    resp = AIResponse(content="<think>kept</think>text", stop_reason="tool_use")
    assert "<think>" in post_process_response(resp).content


def test_create_with_retry_retries_on_connection_error() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry

    call_count = [0]

    class FlakeyProvider:
        def create_message(self, **kwargs: object) -> _MockResponse:  # type: ignore[override]
            call_count[0] += 1
            if call_count[0] <= 1:
                raise ConnectionError("reset")
            return _MockResponse("OK")

    resp = create_with_retry(
        FlakeyProvider(),  # type: ignore[arg-type]  # type: ignore[arg-type]
        max_retries=2,
        model="m",
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
    )
    assert resp.content == "OK"
    assert call_count[0] == 2


def test_create_with_retry_raises_on_exhaustion() -> None:
    from straightjacket.engine.ai.provider_base import create_with_retry
    import pytest

    class AlwaysFail:
        def create_message(self, **kwargs: object) -> None:  # type: ignore[override]
            raise ConnectionError("permanent")

    with pytest.raises(ConnectionError):
        create_with_retry(
            AlwaysFail(),  # type: ignore[arg-type]  # type: ignore[arg-type]
            max_retries=1,
            model="m",
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
        )


# ── strings_loader.py ────────────────────────────────────────


def test_get_string_substitutes_variables() -> None:
    from straightjacket.strings_loader import reload_strings, get_string

    reload_strings()
    result = get_string("epilogue.chapter_msg", n=5)
    assert "5" in result


# ── director_runner.py ───────────────────────────────────────


def test_run_deferred_director_applies_guidance() -> None:
    _stub()
    _load_prompts()
    from straightjacket.engine.game.director_runner import run_deferred_director

    provider = _MockProvider(
        json.dumps(
            {
                "scene_summary": "Tense.",
                "narrator_guidance": "Build tension.",
                "npc_guidance": [],
                "pacing": "building",
                "npc_reflections": [],
                "arc_notes": "Progressing.",
                "act_transition": False,
            }
        )
    )
    game = _game()
    game.narrative.session_log.append(SceneLogEntry(scene=5, summary="Last"))
    run_deferred_director(
        provider,  # type: ignore[arg-type]
        game,
        {"narration": "Text.", "config": None},
    )
    assert game.narrative.director_guidance.pacing == "building"


def test_run_deferred_director_survives_api_error() -> None:
    _stub()
    from straightjacket.engine.game.director_runner import run_deferred_director

    provider = _MockProvider(fail=True)
    game = _game()
    run_deferred_director(
        provider,  # type: ignore[arg-type]
        game,
        {"narration": "text", "config": None},
    )


# ── brain.py ─────────────────────────────────────────────────


def test_revelation_check_returns_false_when_not_confirmed() -> None:
    _stub()
    from straightjacket.engine.ai.brain import call_revelation_check
    from straightjacket.engine.models_story import Revelation

    provider = _MockProvider(json.dumps({"revelation_confirmed": False, "reasoning": "Absent."}))
    rev = Revelation(id="rev_1", content="The shadow is sentient", dramatic_weight="high")
    assert (
        call_revelation_check(
            provider,  # type: ignore[arg-type]
            "The door opened.",
            rev,
        )
        is False
    )


def test_revelation_check_defaults_true_on_api_error() -> None:
    _stub()
    from straightjacket.engine.ai.brain import call_revelation_check
    from straightjacket.engine.models_story import Revelation

    provider = _MockProvider(fail=True)
    assert (
        call_revelation_check(
            provider,  # type: ignore[arg-type]
            "Text.",
            Revelation(id="r", content="X"),
        )
        is True
    )
