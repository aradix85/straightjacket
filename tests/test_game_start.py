from typing import Any

import pytest

from straightjacket.engine.models import GameState
from tests._creation import OPENING_TEXT, OpeningProvider, creation_data


def _provider() -> OpeningProvider:
    return OpeningProvider([], "Drift Station")


def _creation() -> dict[str, Any]:
    creation = creation_data(
        "starforged", stats=(3, 2, 2, 1, 1), player_name="Aria", background_vow="Find the lost archive"
    )
    creation["background_vow_rank"] = "epic"
    return creation


def test_start_new_game_happy_path(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    creation = _creation()
    game, narration = start_new_game(provider, creation)
    assert isinstance(game, GameState)
    assert game.player_name == "Aria"
    assert game.pronouns == "she/her"
    assert game.background_vow == "Find the lost archive"
    assert game.setting_id == "starforged"
    assert narration == OPENING_TEXT


def test_start_new_game_empty_background_vow_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    creation = _creation()
    creation["background_vow"] = ""
    with pytest.raises(ValueError, match="background_vow"):
        start_new_game(provider, creation)


def test_start_new_game_empty_player_name_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    creation = _creation()
    creation["player_name"] = ""
    with pytest.raises(ValueError, match="player_name"):
        start_new_game(provider, creation)


def test_start_new_game_invalid_stats_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    creation = _creation()
    creation["stats"] = {"edge": 1, "heart": 1, "iron": 1, "shadow": 1, "wits": 1}
    with pytest.raises(ValueError, match="must take"):
        start_new_game(provider, creation)


def test_start_new_game_seeds_background_vow_track(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    game, _ = start_new_game(provider, _creation())
    vow_tracks = [t for t in game.progress_tracks if t.id == "vow_background"]
    assert len(vow_tracks) == 1
    assert vow_tracks[0].rank == "epic"


def test_start_new_game_creates_opening_clock(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    game, _ = start_new_game(provider, _creation())
    assert len(game.world.clocks) >= 1
    assert any(c.name == "Find the lost archive" for c in game.world.clocks)


def test_start_new_game_seeds_thread_for_vow(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    game, _ = start_new_game(provider, _creation())
    vow_threads = [t for t in game.narrative.threads if t.id == "thread_background_vow"]
    assert len(vow_threads) == 1


def test_start_new_game_keeps_the_content_lines(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _provider()
    creation = _creation()
    creation["content_lines"] = "no spiders, no body horror"
    game, _ = start_new_game(provider, creation)
    assert game.preferences.content_lines == "no spiders, no body horror"


def test_the_ranks_run_from_troublesome_to_epic_in_every_rank_table(load_engine: None) -> None:
    from straightjacket.engine.ruleset.config import rules
    from straightjacket.engine.ruleset.progress import ranks

    assert ranks() == ["troublesome", "dangerous", "formidable", "extreme", "epic"]
    assert list(rules().legacy.ticks_by_rank) == ranks()
    assert list(rules().legacy.experience_by_rank) == ranks()


@pytest.mark.parametrize("setting_id", ["classic", "starforged", "sundered_isles"])
def test_a_created_game_plays_a_turn_in_every_playable_setting(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, setting_id: str
) -> None:
    from straightjacket.engine.game import process_turn
    from tests._creation import TurnProvider, brain_answer, create_game, force_result
    from tests.elvira.elvira_bot.invariants import assert_game_state

    game = create_game(
        setting_id,
        location="Abandoned Library",
        npcs=[("Mira", "An archivist.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Kael",
        background_vow="Keep the archive whole",
    )
    assert assert_game_state(game, turn=0) == []
    force_result(monkeypatch, "MISS")
    _narration, roll, _offer, _director = process_turn(
        TurnProvider(brain_answer()), game, "I slip into the vault", stream=None
    )

    assert roll is not None
    assert game.narrative.scene_count == 2
    assert [p.name for p in game.world.places] == ["Archive Vault"]
    assert assert_game_state(game, turn=1) == []
