from typing import Any

from straightjacket.engine.models import ProgressTrack, RollResult, ThreadEntry
from tests._helpers import make_brain_result, make_game_state


def _roll(move: str) -> RollResult:
    return RollResult(
        d1=0,
        c1=4,
        c2=9,
        stat_name="",
        stat_value=0,
        action_score=3,
        result="MISS",
        move=move,
        match=False,
    )


def _sworn_game() -> Any:
    game = make_game_state(setting_id="starforged")
    game.progress_tracks = [
        ProgressTrack.new(id="vow_bell", name="Ring the bell", track_type="vow", rank="dangerous"),
        ProgressTrack.new(id="vow_kira", name="Find Kira", track_type="vow", rank="formidable"),
    ]
    game.narrative.threads = [
        ThreadEntry(
            id="thread_bell",
            name="Ring the bell",
            thread_type="vow",
            weight=1,
            source="vow",
            linked_track_id="vow_bell",
        ),
        ThreadEntry(
            id="thread_kira", name="Find Kira", thread_type="vow", weight=1, source="vow", linked_track_id="vow_kira"
        ),
    ]
    return game


def _weights(game: Any) -> dict[str, int]:
    return {t.id: t.weight for t in game.narrative.threads}


def test_a_roll_on_a_vow_adds_weight_to_the_thread_of_that_vow(load_engine: None) -> None:
    from straightjacket.engine.game.scene_finalization import _update_scene_lists

    game = _sworn_game()
    brain = make_brain_result(move="quest/fulfill_your_vow", target_track="vow_kira")
    _update_scene_lists(game, brain, _roll(brain.move), {"new_npcs": []}, set())
    assert _weights(game) == {"thread_bell": 1, "thread_kira": 2}


def test_a_move_that_touches_no_vow_adds_no_thread_weight(load_engine: None) -> None:
    from straightjacket.engine.game.scene_finalization import _update_scene_lists

    game = _sworn_game()
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    _update_scene_lists(game, brain, _roll(brain.move), {"new_npcs": []}, set())
    assert _weights(game) == {"thread_bell": 1, "thread_kira": 1}


def test_a_turn_without_a_roll_adds_no_thread_weight(load_engine: None) -> None:
    from straightjacket.engine.game.scene_finalization import _update_scene_lists

    game = _sworn_game()
    brain = make_brain_result(move="quest/fulfill_your_vow", target_track="vow_kira", dialog_only=True)
    _update_scene_lists(game, brain, None, {"new_npcs": []}, set())
    assert _weights(game) == {"thread_bell": 1, "thread_kira": 1}


def test_thread_weight_stops_at_the_list_maximum(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game.scene_finalization import _update_scene_lists

    game = _sworn_game()
    brain = make_brain_result(move="quest/fulfill_your_vow", target_track="vow_bell")
    for _ in range(eng().random_events.list_weight_max + 2):
        _update_scene_lists(game, brain, _roll(brain.move), {"new_npcs": []}, set())
    assert _weights(game)["thread_bell"] == eng().random_events.list_weight_max
