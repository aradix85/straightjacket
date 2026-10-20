from typing import Any

import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import GameState, Resources, RollResult, labels_of
from tests._helpers import make_brain_result, make_clock, make_game_state

WEAK_HIT_MOVES = ["adventure/gather_information", "adventure/compel"]


def _game(setting: str = "starforged") -> GameState:
    game = make_game_state()
    game.resources = Resources(meters={"health": 5, "spirit": 5, "supply": 5, "momentum": 2}, next_move_bonus=0)
    game.setting_id = setting
    return game


def _roll(result: str) -> RollResult:
    return RollResult(3, 4, 5, "wits", 2, 5, result, "adventure/face_danger", match=False)


def _complication(name: str = "A beacon calls the raiders", filled: int = 0) -> Any:
    return make_clock(name=name, segments=4, filled=filled, creation_source="complication:gather_information:3")


@pytest.mark.parametrize("move", WEAK_HIT_MOVES)
def test_a_weak_hit_of_these_moves_starts_a_small_complication_clock(load_engine: None, move: str) -> None:
    from straightjacket.engine.gamemaster.clocks import open_complications
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = _game()
    outcome = resolve_move_outcome(game, move, "WEAK_HIT", target_npc_id=None, match=False)
    [clock] = open_complications(game)
    assert (clock.clock_type, clock.owner_kind, clock.segments, clock.filled) == ("threat", "world", 4, 0)
    assert clock.name
    assert "](" not in clock.name
    assert clock.trigger_description == clock.name
    assert f"complication_clock {clock.name}" in labels_of(outcome.consequences)


@pytest.mark.parametrize("move", WEAK_HIT_MOVES)
def test_a_strong_hit_starts_no_complication(load_engine: None, move: str) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = _game()
    resolve_move_outcome(game, move, "STRONG_HIT", target_npc_id=None, match=False)
    assert game.world.clocks == []


def test_without_a_story_complication_table_a_meaning_pair_names_the_danger(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.gamemaster.clocks import open_complications
    from straightjacket.engine.ruleset import move_effects
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    monkeypatch.setattr(move_effects, "roll_meaning_table", lambda table: ("Oppose", "Plans"))
    game = _game("classic")
    resolve_move_outcome(game, "adventure/gather_information", "WEAK_HIT", target_npc_id=None, match=False)
    assert [c.name for c in open_complications(game)] == ["Oppose Plans"]


def test_the_emergent_clock_cap_leaves_the_complication_without_a_clock(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = _game()
    cap = gm().clocks.max_clocks_per_chapter
    game.world.clocks = [make_clock(name=f"Event {i}", creation_source=f"random_event:x:{i}") for i in range(cap)]
    outcome = resolve_move_outcome(game, "adventure/gather_information", "WEAK_HIT", target_npc_id=None, match=False)
    assert len(game.world.clocks) == cap
    assert "complication gather_information" in labels_of(outcome.consequences)
    assert not any(c.startswith("complication_clock") for c in labels_of(outcome.consequences))


def test_while_a_complication_clock_runs_a_new_complication_is_told_without_one(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = _game()
    game.world.clocks = [_complication(filled=1)]
    outcome = resolve_move_outcome(game, "adventure/compel", "WEAK_HIT", target_npc_id=None, match=False)
    assert [c.name for c in game.world.clocks] == ["A beacon calls the raiders"]
    assert "complication compel" in labels_of(outcome.consequences)
    assert not any(c.startswith("complication_clock") for c in labels_of(outcome.consequences))


def test_a_complication_clock_fills_every_scene_and_strikes_when_full(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.clocks import tick_autonomous_clocks

    game = _game()
    game.world.clocks = [_complication()]
    for scene in range(1, 4):
        tick_autonomous_clocks(game)
        assert game.world.clocks[0].filled == scene
        assert game.world.pending_clock_fills == []
    [event] = tick_autonomous_clocks(game)
    assert event.triggered
    assert game.world.clocks[0].fired
    assert [f.clock_name for f in game.world.pending_clock_fills] == ["A beacon calls the raiders"]


@pytest.mark.parametrize(("result", "averted"), [("STRONG_HIT", True), ("WEAK_HIT", True), ("MISS", False)])
def test_a_hit_aimed_at_a_complication_heads_it_off(load_engine: None, result: str, averted: bool) -> None:
    from straightjacket.engine.game.action_resolution import _maybe_avert_complication
    from straightjacket.engine.models import Consequence

    game = _game()
    game.world.clocks = [_complication(filled=2)]
    brain = make_brain_result(move="adventure/face_danger", stat="wits", target_clock="A beacon calls the raiders")
    consequences: list[Consequence] = []
    _maybe_avert_complication(game, brain, _roll(result), consequences)
    assert (game.world.clocks == []) is averted
    assert (labels_of(consequences) == ["complication_averted A beacon calls the raiders"]) is averted


def test_a_fired_or_unknown_complication_cannot_be_headed_off(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.clocks import avert_complication

    game = _game()
    fired = _complication(filled=4)
    fired.fired = True
    game.world.clocks = [fired]
    with pytest.raises(ValueError, match="A beacon calls the raiders"):
        avert_complication(game, "A beacon calls the raiders")
    with pytest.raises(ValueError, match="Something else"):
        avert_complication(game, "Something else")
    assert game.world.clocks == [fired]


def test_the_brain_sees_open_complications_and_may_aim_at_one(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from tests._creation import BrainAnswers

    game = _game()
    fired = _complication(name="Old danger", filled=4)
    fired.fired = True
    game.world.clocks = [_complication(filled=1), fired]
    provider = BrainAnswers("adventure/face_danger", target_clock="A beacon calls the raiders")
    result = call_brain(provider, game, "I smash the beacon.")
    assert "<dangers>\n  A beacon calls the raiders 1/4\n</dangers>" in provider.user_messages[0]
    assert "Old danger" not in provider.user_messages[0]
    assert provider.schemas[0]["properties"]["target_clock"]["anyOf"][0]["enum"] == ["A beacon calls the raiders"]
    assert result.target_clock == "A beacon calls the raiders"


@pytest.mark.parametrize("verb", ["complication_clock", "complication_averted"])
def test_a_danger_with_commas_is_told_whole(verb: str) -> None:
    from straightjacket.engine.models import consequence
    from straightjacket.engine.ruleset.consequences import resolve_consequence_sentence
    from straightjacket.engine.ruleset.impacts import get_impacts

    danger = "Weather, terrain, or a creature blocks the way"
    sentence = resolve_consequence_sentence(consequence(verb, name=danger), "Ash", "", "", get_impacts("starforged"))
    assert danger in sentence
    assert "{" not in sentence
