from typing import Any

import pytest

from straightjacket.engine.game import process_turn
from straightjacket.engine.gamemaster.keyed_scenes import add_keyed_scene
from straightjacket.engine.models import GameState
from tests._creation import TurnProvider, brain_answer, correction_answer, fixed_roll, force_result, library_game
from tests._helpers import make_act, make_blueprint, make_revelation, make_scene_setup

_SOURCE = "ac:The Plot Thickens"
_ACT = brain_answer(location_change=None)
_TALK = brain_answer(move="dialog", stat="none", dialog_only=True, player_intent="Talk to Mira", location_change=None)


def _game(*revelations: Any, scene: int) -> GameState:
    game = library_game()
    game.narrative.keyed_scenes = []
    game.narrative.story_blueprint = make_blueprint(
        acts=[
            make_act(phase="setup", scene_range=[1, 7]),
            make_act(phase="confrontation", scene_range=[8, 14]),
            make_act(phase="climax", scene_range=[15, 20]),
        ],
        revelations=list(revelations),
    )
    game.narrative.scene_count = scene - 1
    return game


def _revelation(rev_id: str, act_number: int, source: str = _SOURCE) -> Any:
    return make_revelation(id=rev_id, content=f"Truth {rev_id}", act_number=act_number, keyed_scene_source=source)


def _tag(rev_id: str) -> str:
    return f'<revelation weight="medium">Truth {rev_id}</revelation>'


def _revealed(game: GameState) -> list[str]:
    assert game.narrative.story_blueprint is not None
    return game.narrative.story_blueprint.revealed


def _add_trigger(game: GameState) -> None:
    add_keyed_scene(
        game.narrative,
        trigger_type="scene_count",
        trigger_value="1",
        priority=9,
        narrative_hint="What seemed straightforward shows a layer underneath.",
        source=_SOURCE,
    )


def _play_keyed(monkeypatch: pytest.MonkeyPatch, game: GameState, provider: TurnProvider, result: str) -> None:
    from straightjacket.engine.ruleset import make_move

    monkeypatch.setattr(make_move, "roll_action", fixed_roll(result))
    process_turn(provider, game, "I press on", stream=None)


def _play(monkeypatch: pytest.MonkeyPatch, game: GameState, provider: TurnProvider, result: str) -> Any:
    force_result(monkeypatch, result)
    return process_turn(provider, game, "I press on", stream=None)


def _director_reasons(monkeypatch: pytest.MonkeyPatch) -> list[tuple[bool, str | None]]:
    from straightjacket.engine.game import scene_finalization

    reasons: list[tuple[bool, str | None]] = []
    real = scene_finalization.should_call_director

    def _spy(game: GameState, **triggers: Any) -> str | None:
        reason = real(game, **triggers)
        reasons.append((triggers["revelation_landed"], reason))
        return reason

    monkeypatch.setattr(scene_finalization, "should_call_director", _spy)
    return reasons


def test_a_revelation_lands_on_its_keyed_scene_and_the_narrator_must_tell_it(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(_revelation("r1", 1), scene=3)
    _add_trigger(game)
    provider = TurnProvider(_ACT)

    _play_keyed(monkeypatch, game, provider, "STRONG_HIT")

    assert "<keyed_scene" in provider.prompts[-1]
    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.revelation is not None
    assert game.last_turn_snapshot.revelation.id == "r1"


def test_a_failure_holds_the_revelation_to_the_next_turn_that_does_not_fail(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(_revelation("r1", 1), scene=3)
    _add_trigger(game)
    provider = TurnProvider(_ACT)

    _play_keyed(monkeypatch, game, provider, "MISS")
    assert "<revelation" not in provider.prompts[-1]
    assert _revealed(game) == []

    _play(monkeypatch, game, provider, "WEAK_HIT")
    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]


@pytest.mark.parametrize("source", ["", _SOURCE])
def test_a_revelation_whose_trigger_does_not_fire_lands_at_the_end_of_its_act_and_calls_the_director(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    game = _game(_revelation("r1", 1, source), scene=5)
    if source:
        _add_trigger(game)
    provider = TurnProvider(_ACT)
    reasons = _director_reasons(monkeypatch)

    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert _revealed(game) == []
    assert reasons[-1][0] is False

    game.narrative.scene_count = 6
    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert game.narrative.scene_count == 7
    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]
    assert reasons[-1] == (True, "revelation")


def test_a_trigger_that_fires_before_its_act_lands_the_revelation_once_its_act_begins(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(_revelation("r2", 2), scene=6)
    provider = TurnProvider(_ACT)

    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert _revealed(game) == []

    game.narrative.scene_count = 7
    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert _tag("r2") in provider.prompts[-1]
    assert _revealed(game) == ["r2"]


def test_a_dialog_turn_lands_a_ready_revelation(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game(_revelation("r1", 1, ""), scene=7)
    provider = TurnProvider(_TALK)

    _play(monkeypatch, game, provider, "STRONG_HIT")

    assert game.narrative.session_log[-1].result == "dialog"
    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]


def test_ready_revelations_land_one_turn_at_a_time_the_oldest_first(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(_revelation("r1", 1, ""), _revelation("r2", 2), scene=8)
    provider = TurnProvider(_ACT)

    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert _tag("r1") in provider.prompts[-1]
    assert _tag("r2") not in provider.prompts[-1]

    _play(monkeypatch, game, provider, "STRONG_HIT")
    assert _tag("r2") in provider.prompts[-1]
    assert _revealed(game) == ["r1", "r2"]


def test_a_momentum_burn_that_turns_a_miss_into_a_hit_lands_the_revelation(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_momentum_burn

    game = _game(_revelation("r1", 1, ""), scene=7)
    provider = TurnProvider(_ACT)

    _narration, _roll, offer, _director = _play(monkeypatch, game, provider, "MISS")
    assert offer is not None
    assert _revealed(game) == []

    process_momentum_burn(provider, game, offer)
    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]


@pytest.mark.parametrize("source", ["input_misread", "state_error"])
def test_a_correction_tells_the_turns_revelation_again_and_marks_it_once(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import make_move
    from straightjacket.engine.ruleset.rolls import score_action_roll

    def _hit(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> Any:
        return score_action_roll(6, 1, 2, stat_name, stat_value, move, momentum, adds)

    monkeypatch.setattr(make_move, "roll_action", _hit)
    monkeypatch.setattr(turn, "check_scene", lambda _game: make_scene_setup(scene_type="expected"))
    game = _game(_revelation("r1", 1, ""), scene=7)
    provider = TurnProvider(_ACT)
    provider.correction = correction_answer(correction_source=source)
    process_turn(provider, game, "I press on", stream=None)

    process_correction(provider, game, "That is not what happened")

    assert _tag("r1") in provider.prompts[-1]
    assert _revealed(game) == ["r1"]
