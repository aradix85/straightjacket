from __future__ import annotations

from tests._helpers import make_brain_result, make_game_state


def _swear(game: object, name: str) -> None:
    from straightjacket.engine.mechanics import start_track

    brain = make_brain_result(move="quest/swear_an_iron_vow", stat="heart")
    brain.track_name = name
    brain.track_rank = "dangerous"
    start_track(game, brain, "MISS")


def _connect(game: object, target: str | None, result: str) -> None:
    from straightjacket.engine.mechanics import start_track

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
    import pytest

    from straightjacket.engine.mechanics.tracks import complete_track

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
