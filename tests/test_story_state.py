import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models_story import StoryAct, StoryBlueprint
from tests._helpers import make_blueprint, make_game_state


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
    return make_blueprint(central_conflict="x", acts=acts)


def test_there_is_no_current_act_without_a_blueprint(load_engine: None) -> None:
    from straightjacket.engine.story_state import get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = None
    with pytest.raises(ValueError, match="blueprint"):
        get_current_act(g)


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


def test_check_act_transition_waits_for_the_last_scene_of_the_act(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_act_transition

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 4
    check_act_transition(g)
    assert g.narrative.story_blueprint.triggered_transitions == []


def test_check_act_transition_marks_the_act_at_its_last_scene(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_act_transition, get_current_act

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 5
    check_act_transition(g)
    assert g.narrative.story_blueprint.triggered_transitions == ["act_0"]
    assert get_current_act(g).act_number == 2


def test_check_act_transition_is_idempotent(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_act_transition

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 5
    check_act_transition(g)
    check_act_transition(g)
    assert g.narrative.story_blueprint.triggered_transitions == ["act_0"]


def test_check_act_transition_backfills_skipped_acts(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_act_transition

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.scene_count = 10
    check_act_transition(g)
    assert g.narrative.story_blueprint.triggered_transitions == ["act_0", "act_1"]


def test_check_act_transition_ignores_the_final_act(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_act_transition

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5), (6, 10), (11, 15)])
    g.narrative.story_blueprint.triggered_transitions = ["act_0", "act_1"]
    g.narrative.scene_count = 20
    check_act_transition(g)
    assert g.narrative.story_blueprint.triggered_transitions == ["act_0", "act_1"]


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
    from straightjacket.engine.story_state import check_story_completion

    offset = gm().story_state.completion_overrun_scenes
    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 5)])
    g.narrative.scene_count = 5 + offset + 1
    check_story_completion(g)
    assert g.narrative.story_blueprint.story_complete is True


def test_the_narrators_story_arc_names_the_antagonist(load_engine: None) -> None:
    from straightjacket.engine.prompt_blocks import story_context_block

    g = make_game_state()
    g.narrative.story_blueprint = _bp_with_acts([(1, 10)])
    g.narrative.story_blueprint.antagonist_force = "The tide-priests"
    assert 'antagonist="The tide-priests"' in story_context_block(g)
