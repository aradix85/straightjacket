from typing import Any

import pytest

from straightjacket.engine.models import GameState
from tests._creation import TurnProvider, brain_answer, correction_answer, force_result, library_game
from tests._helpers import make_random_event, make_scene_setup

_SHOVE = brain_answer(stat="iron", target_npc="npc_1", player_intent="Shove past the guard", location_change=None)
_TALK = brain_answer(
    move="dialog", stat="none", dialog_only=True, target_npc="npc_1", player_intent="Talk to Mira", location_change=None
)
_MISREAD = correction_answer(corrected_input="I talk to Mira instead", narrator_guidance="Rewrite as peaceful dialog.")
_LOYAL = correction_answer(
    correction_source="state_error",
    state_ops=[
        {
            "op": "npc_edit",
            "npc_id": "npc_1",
            "split_name": None,
            "split_description": None,
            "merge_source_id": None,
            "fields": {"disposition": "loyal"},
            "value": None,
        }
    ],
)


def _provider(correction: dict[str, Any], *brains: dict[str, Any]) -> TurnProvider:
    provider = TurnProvider(*brains)
    provider.correction = correction
    return provider


def _played_game(provider: TurnProvider, monkeypatch: pytest.MonkeyPatch) -> GameState:
    from straightjacket.engine.game import process_turn

    game = library_game()
    force_result(monkeypatch, "MISS")
    _narration, _roll, _offer, _director = process_turn(provider, game, "I shove past the guard", stream=None)
    return game


def test_correction_input_misread_full_flow(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_MISREAD, _SHOVE, _TALK)
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    snap_health = game.last_turn_snapshot.resources["meters"]["health"]
    scene_before = game.narrative.scene_count
    history_len_before = len(game.narrative.narration_history)

    narration, _offer, _director_ctx = process_correction(provider, game, "I didn't want to attack")

    assert game.resources.meters["health"] == snap_health
    assert game.narrative.scene_count == scene_before
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.narration_history[-1].narration == narration
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.player_input == "I talk to Mira instead"


def test_correction_to_dialog_does_not_roll_even_with_a_stat(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_MISREAD, _SHOVE, {**_TALK, "stat": "heart", "dialog_only": False})
    game = _played_game(provider, monkeypatch)
    narration, _offer, _director_ctx = process_correction(
        provider, game, "That's not what I said, I was asking a question"
    )

    assert len(narration) > 10
    assert game.narrative.session_log[-1].result == "dialog"


def test_correction_state_error_full_flow(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    assert game.npcs[0].disposition == "friendly"
    history_len_before = len(game.narrative.narration_history)

    narration, _offer, _director_ctx = process_correction(provider, game, "Mira should be loyal")

    assert game.npcs[0].disposition == "loyal"
    assert len(narration) > 10
    assert len(game.narrative.narration_history) == history_len_before
    assert game.narrative.session_log[-1].summary.startswith("[corrected]")


def test_a_state_correction_retells_the_turn_with_its_own_scene_and_position(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    game.last_turn_snapshot.scene_setup = make_scene_setup(scene_type="keyed", narrative_hint="The bell tolls")
    game.narrative.session_log[-1].position = "desperate"
    game.narrative.session_log[-1].effect = "limited"

    process_correction(provider, game, "Mira should be loyal")

    retold = provider.prompts[-1]
    assert "<keyed_scene>The bell tolls</keyed_scene>" in retold
    assert '<position level="desperate" effect="limited"/>' in retold


def test_a_state_correction_does_not_tell_a_clock_that_filled_after_the_turn(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.models import ClockEvent

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    game.narrative.session_log[-1].clock_events.append(
        ClockEvent(clock="A storm gathers", trigger="The storm breaks", autonomous=True, triggered=True)
    )

    process_correction(provider, game, "Mira should be loyal")

    assert "A storm gathers" not in provider.prompts[-1]


def test_a_state_correction_extracts_with_the_turns_world_addition(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import finalization

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    assert game.last_turn_snapshot.brain is not None
    game.last_turn_snapshot.brain.world_addition = "A rope hangs from the gallery"
    seen: list[str] = []

    def capture(game: GameState, metadata: dict[str, Any], *, scene_present_ids: set[str], world_addition: str) -> None:
        seen.append(world_addition)

    monkeypatch.setattr(finalization, "apply_narrator_metadata", capture)
    process_correction(provider, game, "Mira should be loyal")

    assert seen == ["A rope hangs from the gallery"]


def test_a_state_correction_retells_what_the_turn_told_without_moving_npc_clocks_again(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn
    from tests._helpers import make_clock

    provider = _provider(_LOYAL, _SHOVE)
    game = library_game()
    game.npcs[0].agenda = "Hide the ledger from the wardens"
    scheme = make_clock(name="The ledger vanishes", clock_type="scheme", owner_kind="npc", owner_id="Mira")
    game.world.clocks.append(scheme)
    game.narrative.scene_count = 4
    force_result(monkeypatch, "MISS")
    process_turn(provider, game, "I shove past the guard", stream=None)
    assert game.last_turn_snapshot is not None
    [told] = game.last_turn_snapshot.npc_agency
    assert "Hide the ledger from the wardens" in told
    assert scheme.filled == 1

    process_correction(provider, game, "Mira should be loyal")

    assert scheme.filled == 1
    assert "Hide the ledger from the wardens" in provider.prompts[-1]


def test_a_state_correction_retells_the_turns_events_and_filled_clocks(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.models import ClockFillResult, ThreatEvent

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    snap = game.last_turn_snapshot
    assert snap is not None
    snap.random_events = [
        make_random_event(focus="npc_action", meaning_action="Betray", meaning_subject="Allies", source="chaos")
    ]
    snap.threat_events = [
        ThreatEvent(threat_id="t1", threat_name="The Iron Choir", menace_full=False, source="miss", development="")
    ]
    snap.clock_fill_results = [
        ClockFillResult(clock_name="The archive burns", clock_type="threat", tag_text="Smoke fills the stacks")
    ]

    process_correction(provider, game, "Mira should be loyal")

    retold = provider.prompts[-1]
    assert "Betray" in retold
    assert "The Iron Choir" in retold
    assert "Smoke fills the stacks" in retold


def test_a_snapshot_without_a_played_turn_is_refused(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_LOYAL, _SHOVE)
    game = _played_game(provider, monkeypatch)
    assert game.last_turn_snapshot is not None
    game.last_turn_snapshot.brain = None
    with pytest.raises(ValueError, match="no Brain result"):
        process_correction(provider, game, "Mira should be loyal")


def test_a_game_without_a_played_turn_has_nothing_to_correct(load_engine: None) -> None:
    from straightjacket.engine.correction import process_correction

    provider = _provider(_MISREAD, _SHOVE)
    with pytest.raises(ValueError, match="No turn to correct"):
        process_correction(provider, library_game(), "Fix something")
    assert provider.calls == []
