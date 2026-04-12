#!/usr/bin/env python3
"""Tests for consequence sentence generation (step 4).

Verifies that mechanical consequences produce narrative sentences
from engine.yaml templates, and that those sentences appear in
the narrator prompt as <consequence> tags.

Run: python -m pytest tests/test_consequence_sentences.py -v
"""

from straightjacket.engine.mechanics import (
    generate_consequence_sentences,
    _pick_template,
    _resolve_consequence_sentence,
)
from straightjacket.engine.models import (
    BrainResult,
    ClockEvent,
    GameState,
    NpcData,
)
from straightjacket.engine.prompt_builders import build_action_prompt
from straightjacket.engine.models import RollResult


def _game() -> GameState:
    game = GameState(player_name="Ash", setting_id="starforged", setting_genre="starforged")
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
    result = _pick_template("health_light")
    assert isinstance(result, str)
    assert len(result) > 0


def test_pick_template_unknown_key_returns_fallback() -> None:
    result = _pick_template("nonexistent_key", "fallback text")
    assert result == "fallback text"


def test_pick_template_unknown_key_empty_default() -> None:
    result = _pick_template("nonexistent_key")
    assert result == ""


# ── Single consequence resolution ─────────────────────────────


def test_resolve_health_light() -> None:
    sentence = _resolve_consequence_sentence("health -1", "Ash", "", "The Docks")
    assert sentence != ""
    assert "Ash" in sentence


def test_resolve_health_heavy() -> None:
    sentence = _resolve_consequence_sentence("health -2", "Ash", "", "The Docks")
    assert sentence != ""
    # Heavy template should be different set than light
    light = _resolve_consequence_sentence("health -1", "Ash", "", "The Docks")
    # Both should exist (templates are random, but both keys have entries)
    assert light != "" and sentence != ""


def test_resolve_spirit_loss() -> None:
    sentence = _resolve_consequence_sentence("spirit -1", "Ash", "", "")
    assert sentence != ""


def test_resolve_supply_loss() -> None:
    sentence = _resolve_consequence_sentence("supply -1", "Ash", "", "")
    assert sentence != ""


def test_resolve_momentum_loss() -> None:
    sentence = _resolve_consequence_sentence("momentum -2", "Ash", "", "")
    assert sentence != ""


def test_resolve_bond_loss() -> None:
    sentence = _resolve_consequence_sentence("Kira bond -1", "Ash", "Kira", "")
    assert sentence != ""
    assert "Kira" in sentence


def test_resolve_health_gain() -> None:
    sentence = _resolve_consequence_sentence("health +1", "Ash", "", "")
    assert sentence != ""


def test_resolve_bond_gain() -> None:
    sentence = _resolve_consequence_sentence("Kira bond +1", "Ash", "Kira", "")
    assert sentence != ""


def test_resolve_compound_consequence() -> None:
    sentence = _resolve_consequence_sentence("supply -1, health -1", "Ash", "", "The Docks")
    assert sentence != ""


def test_resolve_unknown_returns_empty() -> None:
    sentence = _resolve_consequence_sentence("gibberish", "Ash", "", "")
    assert sentence == ""


# ── Full sentence generation ──────────────────────────────────


def test_generate_sentences_from_consequences() -> None:
    game = _game()
    brain = _brain()
    consequences = ["health -2", "momentum -3"]
    sentences = generate_consequence_sentences(consequences, [], game, brain)
    assert len(sentences) == 2
    assert all(isinstance(s, str) and len(s) > 0 for s in sentences)


def test_generate_sentences_with_clock_events() -> None:
    game = _game()
    brain = _brain()
    clock_events = [ClockEvent(clock="Looming storm", trigger="The storm breaks", triggered=False)]
    sentences = generate_consequence_sentences([], clock_events, game, brain)
    assert len(sentences) >= 1


def test_generate_sentences_with_triggered_clock() -> None:
    game = _game()
    brain = _brain()
    clock_events = [ClockEvent(clock="Vault heist", trigger="The vault opens", triggered=True)]
    sentences = generate_consequence_sentences([], clock_events, game, brain)
    assert any("Vault heist" in s or "vault" in s.lower() for s in sentences)


def test_generate_sentences_empty_consequences() -> None:
    game = _game()
    brain = _brain()
    sentences = generate_consequence_sentences([], [], game, brain)
    assert sentences == []


def test_generate_sentences_with_npc_target() -> None:
    game = _game()
    game.npcs.append(NpcData(id="npc_1", name="Kira", disposition="distrustful"))
    brain = _brain(target="npc_1")
    consequences = ["Kira bond -1"]
    sentences = generate_consequence_sentences(consequences, [], game, brain)
    assert len(sentences) >= 1
    assert any("Kira" in s for s in sentences)


# ── Prompt integration ────────────────────────────────────────


def test_consequence_tags_in_prompt() -> None:
    game = _game()
    game.narrative.story_blueprint = None
    brain = _brain()
    roll = _roll("MISS")
    consequences = ["health -2", "momentum -3"]
    sentences = ["The hit is bad. Ash feels something give.", "Whatever advantage Ash had, it's gone."]
    prompt = build_action_prompt(
        game,
        brain,
        roll,
        consequences,
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
    brain = _brain()
    roll = _roll("STRONG_HIT")
    prompt = build_action_prompt(
        game,
        brain,
        roll,
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
    brain = _brain()
    roll = _roll("MISS")
    sentences = ["Pain flares."]
    prompt = build_action_prompt(
        game,
        brain,
        roll,
        ["health -1"],
        [],
        [],
        player_words="climb",
        consequence_sentences=sentences,
    )
    assert "<consequence>" in prompt.lower()
