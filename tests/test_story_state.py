from straightjacket.engine.models_story import Revelation, StoryAct, StoryBlueprint
from tests._helpers import make_game_state


def _bp_with_acts(scene_ranges: list[tuple[int, int]]) -> StoryBlueprint:
    acts = [
        StoryAct(
            phase=f"phase_{i}",
            title=f"Act {i + 1}",
            goal=f"goal_{i}",
            scene_range=list(r),
            mood="tense",
            transition_trigger=f"trigger_{i}",
        )
        for i, r in enumerate(scene_ranges)
    ]
    return StoryBlueprint(central_conflict="x", acts=acts)


def test_get_current_act_no_blueprint(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = None
    act = get_current_act(g)
    assert act.phase == "setup"
    assert act.title == "?"


def test_get_current_act_empty_acts(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint(acts=[])
    act = get_current_act(g)
    assert act.phase == "setup"


def test_get_current_act_first_act_when_in_range(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 3
    act = get_current_act(g)
    assert act.act_number == 1
    assert act.title == "Act 1"


def test_get_current_act_advances_when_triggered(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.story_blueprint.triggered_transitions = ["act_0"]
    g.narrative.scene_count = 6
    act = get_current_act(g)
    assert act.act_number == 2


def test_get_current_act_advances_when_scene_past_range(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 12
    act = get_current_act(g)
    assert act.act_number >= 2


def test_get_current_act_progress_early(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 10)])
    g.narrative.scene_count = 1
    act = get_current_act(g)
    assert act.progress == "early"


def test_get_current_act_progress_late(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 10)])
    g.narrative.scene_count = 9
    act = get_current_act(g)
    assert act.progress == "late"


def test_get_current_act_aftermath_when_complete_and_dismissed(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10)])
    g.narrative.story_blueprint.story_complete = True
    g.campaign.epilogue_dismissed = True
    g.narrative.scene_count = 12
    act = get_current_act(g)
    assert act.phase == "aftermath"
    assert act.title == "Aftermath"


def test_get_current_act_approaching_end_on_final_act(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10)])
    g.narrative.story_blueprint.triggered_transitions = ["act_0"]
    g.narrative.scene_count = 9
    act = get_current_act(g)
    assert act.approaching_end is True


def test_get_pending_revelations_no_blueprint(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_pending_revelations

    g = make_game_state()
    g.narrative.story_blueprint = None
    assert get_pending_revelations(g) == []


def test_get_pending_revelations_no_revelations(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_pending_revelations

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint(acts=[])
    assert get_pending_revelations(g) == []


def test_get_pending_revelations_excludes_used(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_pending_revelations

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint(
        revelations=[
            Revelation(id="r1", content="A", earliest_scene=1),
            Revelation(id="r2", content="B", earliest_scene=1),
        ],
        revealed=["r1"],
    )
    g.narrative.scene_count = 5
    pending = get_pending_revelations(g)
    assert len(pending) == 1
    assert pending[0].id == "r2"


def test_get_pending_revelations_excludes_too_early(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_pending_revelations

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint(
        revelations=[Revelation(id="r1", content="A", earliest_scene=10)],
    )
    g.narrative.scene_count = 5
    assert get_pending_revelations(g) == []


def test_mark_revelation_used_appends(load_engine: None) -> None:
    from straightjacket.engine.story_state import mark_revelation_used

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint()
    mark_revelation_used(g, "r1")
    assert "r1" in g.narrative.story_blueprint.revealed


def test_mark_revelation_used_dedup(load_engine: None) -> None:
    from straightjacket.engine.story_state import mark_revelation_used

    g = make_game_state()
    g.narrative.story_blueprint = StoryBlueprint(revealed=["r1"])
    mark_revelation_used(g, "r1")
    assert g.narrative.story_blueprint.revealed.count("r1") == 1


def test_mark_revelation_used_no_blueprint_noop(load_engine: None) -> None:
    from straightjacket.engine.story_state import mark_revelation_used

    g = make_game_state()
    g.narrative.story_blueprint = None
    mark_revelation_used(g, "r1")


def test_check_story_completion_no_blueprint_noop(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_story_completion

    g = make_game_state()
    g.narrative.story_blueprint = None
    check_story_completion(g)


def test_check_story_completion_already_complete_noop(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_story_completion

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10)])
    g.narrative.story_blueprint.story_complete = True
    g.narrative.scene_count = 100
    check_story_completion(g)
    assert g.narrative.story_blueprint.story_complete is True


def test_check_story_completion_completes_when_final_act_entered(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_story_completion

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.story_blueprint.triggered_transitions = ["act_0", "act_1"]
    g.narrative.scene_count = 15
    check_story_completion(g)
    assert g.narrative.story_blueprint.story_complete is True


def test_check_story_completion_backfills_transitions(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_story_completion

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 15
    check_story_completion(g)
    assert "act_0" in g.narrative.story_blueprint.triggered_transitions
    assert "act_1" in g.narrative.story_blueprint.triggered_transitions
    assert g.narrative.story_blueprint.story_complete is True


def test_check_story_completion_fallback_far_past_end(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.story_state import check_story_completion

    offset = eng().story_state.crisis_scene_offset
    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5)])
    g.narrative.scene_count = 5 + offset + 1
    check_story_completion(g)
    assert g.narrative.story_blueprint.story_complete is True
