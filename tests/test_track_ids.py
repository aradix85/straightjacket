from __future__ import annotations

from pathlib import Path

import pytest

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


def test_a_save_with_duplicate_thread_ids_loads_again(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from straightjacket.engine.models import ThreadEntry
    from straightjacket.engine.persistence import load_game, save_game

    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path / "users")
    game = make_game_state(setting_id="starforged")
    game.narrative.threads = [
        ThreadEntry(id="thread_x", name="X", thread_type="vow", source="vow"),
        ThreadEntry(id="thread_x", name="X", thread_type="vow", source="vow"),
    ]
    save_game(game, "tester", [], "slot")
    loaded, _ = load_game("tester", "slot")
    assert loaded is not None
    assert [t.id for t in loaded.narrative.threads] == ["thread_x", "thread_x_2"]
