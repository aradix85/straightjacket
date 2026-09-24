from __future__ import annotations

from tests._helpers import make_brain_result, make_game_state


def _swear(game: object, name: str) -> None:
    from straightjacket.engine.game.turn import _maybe_create_track

    brain = make_brain_result(move="quest/swear_an_iron_vow", stat="heart")
    brain.track_name = name
    brain.track_rank = "dangerous"
    _maybe_create_track(game, brain)


def test_swearing_an_active_vow_again_does_not_duplicate_it(load_engine: None) -> None:
    game = make_game_state(setting_id="starforged")
    _swear(game, "Find the relic")
    _swear(game, "Find the relic")
    assert [t.id for t in game.progress_tracks].count("vow_find_the_relic") == 1
    thread_ids = [t.id for t in game.narrative.threads]
    assert len(thread_ids) == len(set(thread_ids))


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
