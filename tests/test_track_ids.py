from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from straightjacket.engine.game import process_turn
from straightjacket.engine.ruleset.outcome_result import new_outcome
from straightjacket.engine.ruleset.progress import filled_boxes
from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy, complete_track, start_track
from tests._creation import TurnProvider, brain_answer, force_result, library_game
from tests._helpers import make_brain_result, make_game_state

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState


def _swear(game: GameState, name: str) -> None:
    brain = make_brain_result(move="quest/swear_an_iron_vow", stat="heart")
    brain.track_name = name
    brain.track_rank = "dangerous"
    start_track(game, brain, "MISS")


def _connect(game: GameState, target: str | None, result: str) -> None:
    brain = make_brain_result(move="connection/make_a_connection", stat="heart", target_npc=target)
    brain.track_name = "Kira"
    brain.track_rank = "dangerous"
    start_track(game, brain, result)


def test_a_connection_is_keyed_by_its_npc_and_made_only_on_a_hit(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _connect(game, "npc_1", "MISS")
    assert game.progress_tracks == []
    _connect(game, None, "STRONG_HIT")
    assert game.progress_tracks == []
    _connect(game, "npc_1", "WEAK_HIT")
    assert [(t.id, t.track_type) for t in game.progress_tracks] == [("connection_npc_1", "connection")]


def test_a_vow_is_sworn_whatever_the_roll(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _swear(game, "Find the relic")
    assert [t.id for t in game.progress_tracks] == ["vow_find_the_relic"]


def test_swearing_an_active_vow_again_does_not_duplicate_it(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _swear(game, "Find the relic")
    _swear(game, "Find the relic")
    assert [t.id for t in game.progress_tracks].count("vow_find_the_relic") == 1
    thread_ids = [t.id for t in game.narrative.threads]
    assert len(thread_ids) == len(set(thread_ids))


def test_a_track_id_holds_only_word_characters(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _swear(game, 'Avenge Kíra\'s "crew" </tracks>')
    track = game.progress_tracks[-1]
    assert track.id == "vow_avenge_kíra_s_crew_tracks"
    assert track.name == 'Avenge Kíra\'s "crew" </tracks>'


def test_completing_a_track_that_does_not_exist_raises(load_engine: None) -> None:
    with pytest.raises(KeyError):
        complete_track(make_game_state(setting_id="starforged"), "vow_missing", "completed")


def test_a_vow_sworn_again_after_completion_gets_unique_ids(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _swear(game, "Find the relic")
    game.progress_tracks[-1].status = "completed"
    _swear(game, "Find the relic")
    assert [t.id for t in game.progress_tracks if t.id.startswith("vow_find_the_relic")] == [
        "vow_find_the_relic",
        "vow_find_the_relic_2",
    ]
    thread_ids = [t.id for t in game.narrative.threads]
    assert len(thread_ids) == len(set(thread_ids))


def test_a_second_journey_named_by_its_own_name_takes_the_progress(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = library_game()
    force_result(monkeypatch, "STRONG_HIT")
    for name in ("To the ridge", "To the coast"):
        journey = brain_answer(
            move="adventure/undertake_a_journey", stat="wits", location_change=None, track_name=name, target_track=None
        )
        process_turn(TurnProvider(journey), game, f"I set out: {name}", stream=None)

    journeys = {t.name: t for t in game.progress_tracks if t.track_type == "journey"}
    assert set(journeys) == {"To the ridge", "To the coast"}
    assert filled_boxes(journeys["To the ridge"]) == filled_boxes(journeys["To the coast"]) > 0


def test_a_vow_without_a_rank_from_the_brain_fails_the_turn(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    force_result(monkeypatch, "STRONG_HIT")
    brain = brain_answer(
        move="quest/swear_an_iron_vow",
        stat="heart",
        location_change=None,
        track_name="Find the lost ledger",
        track_rank=None,
    )
    with pytest.raises(ValueError, match="named no track name or rank"):
        process_turn(TurnProvider(brain), library_game(), "I swear to find the lost ledger", stream=None)


def test_progress_on_a_new_track_without_a_name_from_the_brain_fails_the_turn(load_engine: None) -> None:
    brain = make_brain_result(move="exploration/undertake_an_expedition", stat="wits")
    brain.track_name = None
    outcome = new_outcome()
    outcome.progress_marks = 1
    with pytest.raises(ValueError, match="marks progress on a new track"):
        apply_progress_and_legacy(make_game_state(setting_id="starforged"), outcome, brain, None)
