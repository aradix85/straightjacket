from typing import Any

from straightjacket.engine.models import ProgressTrack, RandomEvent, RollResult, ThreadEntry, ThreatEvent
from tests._helpers import make_brain_result, make_game_state, make_threat


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
            id="thread_bell", name="Ring the bell", thread_type="vow", source="vow", linked_track_id="vow_bell"
        ),
        ThreadEntry(id="thread_kira", name="Find Kira", thread_type="vow", source="vow", linked_track_id="vow_kira"),
        ThreadEntry(id="thread_cult", name="Who cast the bell", thread_type="plot", source="ac"),
    ]
    game.threats = [make_threat(id="threat_tide", name="The tide cult", linked_vow_id="vow_bell")]
    return game


def _event(target_id: str) -> RandomEvent:
    return RandomEvent(
        focus="move_toward_a_thread",
        focus_roll=50,
        meaning_action="Pursue",
        meaning_subject="Truths",
        meaning_table="actions",
        source="scene",
        target_id=target_id,
    )


def _invoked(game: Any, brain: Any, roll: Any, events: list[Any], threat_events: list[Any]) -> list[str]:
    from straightjacket.engine.game.scene_finalization import invoked_threads

    return invoked_threads(game, brain, roll, events, threat_events)


def test_a_roll_on_a_vow_invokes_the_thread_of_that_vow(load_engine: None) -> None:
    brain = make_brain_result(move="quest/fulfill_your_vow", target_track="vow_kira")
    assert _invoked(_sworn_game(), brain, _roll(brain.move), [], []) == ["thread_kira"]


def test_a_move_that_touches_no_vow_invokes_no_thread(load_engine: None) -> None:
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    assert _invoked(_sworn_game(), brain, _roll(brain.move), [], []) == []


def test_a_turn_without_a_roll_invokes_no_thread_by_its_move(load_engine: None) -> None:
    brain = make_brain_result(move="quest/fulfill_your_vow", target_track="vow_kira", dialog_only=True)
    assert _invoked(_sworn_game(), brain, None, [], []) == []


def test_a_random_event_about_a_thread_invokes_it(load_engine: None) -> None:
    brain = make_brain_result(move="dialog")
    assert _invoked(_sworn_game(), brain, None, [_event("thread_cult")], []) == ["thread_cult"]


def test_a_threat_that_advances_in_the_scene_invokes_the_thread_of_its_vow(load_engine: None) -> None:
    brain = make_brain_result(move="adventure/face_danger", stat="wits")
    advanced = ThreatEvent(
        threat_id="threat_tide",
        threat_name="The tide cult",
        ticks_added=4,
        menace_full=False,
        source="miss",
        development="",
    )
    assert _invoked(_sworn_game(), brain, _roll(brain.move), [], [advanced]) == ["thread_bell"]
    assert _invoked(_sworn_game(), brain, None, [_event("threat_tide")], []) == ["thread_bell"]


def test_thread_weight_stops_at_the_list_maximum(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.random_events import add_thread_weight

    game = _sworn_game()
    for _ in range(eng().random_events.list_weight_max + 2):
        add_thread_weight(game, "thread_bell")
    assert (
        next(t for t in game.narrative.threads if t.id == "thread_bell").weight == eng().random_events.list_weight_max
    )
