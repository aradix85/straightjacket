#!/usr/bin/env python3
"""Tests for consequence sentence generation (step 4).

Verifies that mechanical consequences produce narrative sentences
from engine.yaml templates, and that those sentences appear in
the narrator prompt as <consequence> tags.
"""

import pytest

from straightjacket.engine.mechanics import (
    generate_consequence_sentences,
    pick_template,
    resolve_consequence_sentence,
)
from straightjacket.engine.models import (
    BrainResult,
    ClockEvent,
    GameState,
    NpcData,
    RollResult,
)
from straightjacket.engine.prompt_builders import build_action_prompt
from tests._helpers import make_game_state


def _game() -> GameState:
    game = make_game_state(player_name="Ash", setting_id="starforged", setting_genre="starforged")
    game.world.current_location = "The Docks"
    game.narrative.scene_count = 3
    return game


def _brain(target: str | None = None) -> BrainResult:
    return BrainResult(move="adventure/face_danger", stat="edge", player_intent="climb the wall", target_npc=target)


def _roll(result: str = "MISS") -> RollResult:
    return RollResult(
        d1=2,
        d2=3,
        c1=8,
        c2=9,
        stat_name="edge",
        stat_value=2,
        action_score=7,
        result=result,
        move="adventure/face_danger",
    )


# ── Template picking ──────────────────────────────────────────


def test_pick_template_returns_string() -> None:
    result = pick_template("health_light")
    assert isinstance(result, str) and len(result) > 0


def test_pick_template_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        pick_template("nonexistent_key")


# ── Single consequence resolution ─────────────────────────────


@pytest.mark.parametrize(
    "cons, player, npc, loc, must_contain",
    [
        ("health -1", "Ash", "", "The Docks", "Ash"),
        ("health -2", "Ash", "", "The Docks", "Ash"),
        ("spirit -1", "Ash", "", "", ""),
        ("supply -1", "Ash", "", "", ""),
        ("momentum -2", "Ash", "", "", ""),
        ("Kira bond -1", "Ash", "Kira", "", "Kira"),
        ("health +1", "Ash", "", "", ""),
        ("Kira bond +1", "Ash", "Kira", "", ""),
        ("supply -1, health -1", "Ash", "", "The Docks", ""),
    ],
)
def test_resolve_consequence_produces_sentence(cons: str, player: str, npc: str, loc: str, must_contain: str) -> None:
    sentence = resolve_consequence_sentence(cons, player, npc, loc)
    assert sentence != ""
    if must_contain:
        assert must_contain in sentence


def test_resolve_unknown_returns_empty() -> None:
    assert resolve_consequence_sentence("gibberish", "Ash", "", "") == ""


# ── Full sentence generation ──────────────────────────────────


def test_generate_sentences_from_consequences() -> None:
    sentences = generate_consequence_sentences(["health -2", "momentum -3"], [], _game(), _brain())
    assert len(sentences) == 2
    assert all(isinstance(s, str) and len(s) > 0 for s in sentences)


def test_generate_sentences_with_clock_events() -> None:
    clock_events = [ClockEvent(clock="Looming storm", trigger="The storm breaks", triggered=False)]
    assert len(generate_consequence_sentences([], clock_events, _game(), _brain())) >= 1


def test_generate_sentences_with_triggered_clock() -> None:
    clock_events = [ClockEvent(clock="Vault heist", trigger="The vault opens", triggered=True)]
    sentences = generate_consequence_sentences([], clock_events, _game(), _brain())
    assert any("Vault heist" in s or "vault" in s.lower() for s in sentences)


def test_generate_sentences_empty_returns_empty() -> None:
    assert generate_consequence_sentences([], [], _game(), _brain()) == []


def test_generate_sentences_with_npc_target() -> None:
    game = _game()
    game.npcs.append(NpcData(id="npc_1", name="Kira", disposition="distrustful"))
    sentences = generate_consequence_sentences(["Kira bond -1"], [], game, _brain(target="npc_1"))
    assert len(sentences) >= 1 and any("Kira" in s for s in sentences)


# ── Prompt integration ────────────────────────────────────────


def test_consequence_tags_in_prompt() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    sentences = ["The hit is bad. Ash feels something give.", "Whatever advantage Ash had, it's gone."]
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("MISS"),
        ["health -2", "momentum -3"],
        [],
        [],
        player_words="climb the wall",
        consequence_sentences=sentences,
    )
    assert "<consequence>" in prompt
    assert "The hit is bad" in prompt
    assert "Whatever advantage" in prompt


def test_no_consequence_tags_when_empty() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("STRONG_HIT"),
        [],
        [],
        [],
        player_words="climb the wall",
        consequence_sentences=[],
    )
    assert "<consequence>" not in prompt


def test_task_mentions_consequence_weaving() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    prompt = build_action_prompt(
        game,
        _brain(),
        _roll("MISS"),
        ["health -1"],
        [],
        [],
        player_words="climb",
        consequence_sentences=["Pain flares."],
    )
    assert "<consequence>" in prompt.lower()
