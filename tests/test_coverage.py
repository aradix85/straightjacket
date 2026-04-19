#!/usr/bin/env python3
"""Targeted tests for modules not covered by domain-specific test files.

Every test here exists because it catches a real bug or verifies a non-obvious behavior.
Coverage-padding tests (empty-input returns empty, pass-through returns same object) removed.
"""

import json

from straightjacket.engine.models import (
    ClockData,
    GameState,
    NpcData,
    SceneLogEntry,
)
from tests._helpers import make_game_state


def _game() -> GameState:
    g = GameState(
        player_name="Hero",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A dark world.",
        stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
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
    g.npcs = [NpcData(id="npc_1", name="Kira", disposition="friendly")]
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
        extra_body: dict | None = None,
    ) -> _MockResponse:
        self.calls.append({"system": system, "json_schema": json_schema})
        if self._fail:
            raise ConnectionError("mock fail")
        return _MockResponse(self._content)


# ── validator.py ─────────────────────────────────────────────


def test_validate_narration_returns_violations(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = _MockProvider(
        json.dumps({"pass": False, "violations": ["Silver lining on MISS"], "correction": "Make it worse."})
    )
    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "Bad narration.",
        ctx,
    )
    assert result["pass"] is False
    assert len(result["violations"]) == 1


def test_validate_narration_fail_open_on_api_error(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = _MockProvider(fail=True)
    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "Text.",
        ctx,
    )
    assert result["pass"] is True


def test_validate_narration_catches_genre_violation_rule_based(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration
    from tests.conftest import make_genre_constraints

    provider = _MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    gc = make_genre_constraints(forbidden_terms=["magic"])
    ctx = ValidationContext.build(make_game_state(), result_type="MISS", genre_constraints=gc)
    result = validate_narration(
        provider,  # type: ignore[arg-type]
        "She cast a magic spell.",
        ctx,
    )
    assert result["pass"] is False
    assert any("magic" in v for v in result["violations"])


def test_validate_and_retry_actually_retries(stub_all: None) -> None:
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
            extra_body: dict | None = None,
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


def test_validate_architect_fixes_violations(stub_all: None) -> None:
    from straightjacket.engine.ai.architect_validator import validate_architect
    from tests.conftest import make_genre_constraints

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
    gc = make_genre_constraints(forbidden_terms=["magic"])
    result = validate_architect(
        provider,  # type: ignore[arg-type]
        bp,
        "realistic",
        "serious",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Political conspiracy"
    assert result["antagonist_force"] == "Corrupt senator"


def test_validate_architect_fail_open_on_api_error(stub_all: None) -> None:
    from straightjacket.engine.ai.architect_validator import validate_architect
    from tests.conftest import make_genre_constraints

    provider = _MockProvider(fail=True)
    bp = {"central_conflict": "Original", "antagonist_force": "Original"}
    gc = make_genre_constraints(forbidden_terms=["x"])
    result = validate_architect(
        provider,  # type: ignore[arg-type]
        bp,
        "genre",
        "tone",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Original"


# ── setup_common.py ──────────────────────────────────────────


def test_register_extracted_npcs_skips_player(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = make_game_state(player_name="Hero")
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


def test_register_extracted_npcs_skips_returning(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import register_extracted_npcs

    game = make_game_state(player_name="Hero")
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


def test_seed_opening_memories_matches_and_skips(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import seed_opening_memories

    game = make_game_state(player_name="Hero")
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


def test_apply_world_setup_replace_vs_extend(stub_all: None) -> None:
    from straightjacket.engine.game.setup_common import apply_world_setup

    game = make_game_state(player_name="Hero")
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


def test_run_deferred_director_applies_guidance(stub_all: None) -> None:
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
    assert game.narrative.director_guidance.narrator_guidance == "Build tension."


def test_run_deferred_director_survives_api_error(stub_all: None) -> None:
    from straightjacket.engine.game.director_runner import run_deferred_director

    provider = _MockProvider(fail=True)
    game = _game()
    run_deferred_director(
        provider,  # type: ignore[arg-type]
        game,
        {"narration": "text", "config": None},
    )


# ── brain.py ─────────────────────────────────────────────────


def test_revelation_check_returns_false_when_not_confirmed(stub_all: None) -> None:
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


def test_revelation_check_defaults_true_on_api_error(stub_all: None) -> None:
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
