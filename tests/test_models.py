import pytest

from straightjacket.engine.models import StoryAct, StoryBlueprint
from straightjacket.engine.ruleset.progress import mark_progress
from tests._helpers import (
    fix_dice,
    make_clock,
    make_game_state,
    make_memory,
    make_npc,
    make_npc_detail,
    make_progress_track,
)


def test_the_action_score_stops_at_its_cap(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ruleset.config import rules
    from straightjacket.engine.ruleset.rolls import roll_action

    fix_dice(monkeypatch, 6, 1, 1)
    assert roll_action("edge", 3, "adventure/face_danger", 0, 3).action_score == rules().dice.action_score_max


def test_compel_strong_hit_marks_no_bond_and_no_disposition_shift(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = make_game_state(setting_id="starforged")
    npc = make_npc(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    resolve_move_outcome(game, "adventure/compel", "STRONG_HIT", target_npc_id="npc_1", match=False)
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert conn.ticks == 0
    assert npc.disposition == "neutral"


def test_test_bond_disposition_shift(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome

    game = make_game_state(setting_id="starforged")
    npc = make_npc(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    outcome = resolve_move_outcome(
        game, "connection/test_your_relationship", "STRONG_HIT", target_npc_id="npc_1", match=False
    )
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert outcome.chained_move == "connection/develop_your_relationship"
    assert conn.ticks == 0
    assert npc.disposition == "friendly"


def test_npc_owned_threat_clock_ticks_in_agency() -> None:
    from straightjacket.engine.gamemaster.clocks import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 5
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = make_clock(
        name="Villain Plan", clock_type="threat", segments=6, filled=3, owner_kind="npc", owner_id="Villain"
    )
    game.world.clocks.append(clock)
    actions, clock_events, _ = check_npc_agency(game)
    assert clock.filled == 4
    assert len(actions) >= 1
    assert len(clock_events) == 1
    assert clock_events[0].clock == "Villain Plan"
    assert not clock_events[0].triggered


def test_npc_agency_clock_fires_on_full() -> None:
    from straightjacket.engine.gamemaster.clocks import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 10
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = make_clock(
        name="Villain Plan", clock_type="threat", segments=4, filled=3, owner_kind="npc", owner_id="Villain"
    )
    game.world.clocks.append(clock)
    _actions, clock_events, fill_results = check_npc_agency(game)
    assert clock.filled == 4
    assert clock.fired
    assert len(clock_events) == 1
    assert clock_events[0].triggered
    assert any(fr.clock_name == "Villain Plan" for fr in fill_results)


def test_npc_agency_empty_on_wrong_scene() -> None:
    from straightjacket.engine.gamemaster.clocks import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 3
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    actions, clock_events, _ = check_npc_agency(game)
    assert actions == []
    assert clock_events == []


def test_autonomous_clocks_skip_npc_owned(load_engine: None) -> None:
    import random

    from straightjacket.engine.gamemaster.clocks import tick_autonomous_clocks

    random.seed(0)
    game = make_game_state()
    clock = make_clock(
        name="NPC Clock", clock_type="threat", segments=6, filled=2, owner_kind="npc", owner_id="Villain"
    )
    game.world.clocks.append(clock)
    for _ in range(20):
        tick_autonomous_clocks(game)
    assert clock.filled == 2


def test_story_blueprint_triggered_director_phases_snapshot() -> None:
    game = make_game_state()
    bp = StoryBlueprint(
        central_conflict="c",
        antagonist_force="a",
        thematic_thread="t",
        structure_type="3act",
        revealed=[],
        triggered_transitions=[],
        story_complete=False,
    )
    bp.triggered_director_phases.append("resolution")
    game.narrative.story_blueprint = bp
    snap = game.narrative.snapshot()
    bp.triggered_director_phases.append("climax")
    game.narrative.restore(snap)
    assert game.narrative.story_blueprint.triggered_director_phases == ["resolution"]


def test_phase_trigger_dedup(load_engine: None) -> None:
    from straightjacket.engine.director import should_call_director

    game = make_game_state()
    game.narrative.scene_count = 12
    bp = StoryBlueprint(
        central_conflict="c",
        antagonist_force="a",
        thematic_thread="t",
        structure_type="3act",
        revealed=[],
        triggered_transitions=["act_0"],
        story_complete=False,
    )
    bp.acts = [
        StoryAct(phase="setup", title="Setup", goal="", scene_range=[1, 5], mood="", transition_trigger=""),
        StoryAct(phase="climax", title="Climax", goal="", scene_range=[6, 10], mood="", transition_trigger=""),
        StoryAct(phase="resolution", title="Resolution", goal="", scene_range=[11, 15], mood="", transition_trigger=""),
    ]
    game.narrative.story_blueprint = bp

    triggers = {"roll_result": "dialog", "chaos_used": False, "new_npcs_found": False, "revelation_used": False}
    assert should_call_director(game, **triggers) == "phase:resolution"
    assert bp.triggered_director_phases == ["resolution"]
    assert should_call_director(game, **triggers) != "phase:resolution"


def test_an_engine_rolled_name_is_not_replaced_by_one_without_overlap() -> None:
    from straightjacket.engine.gamemaster.npc.processing import process_npc_details

    game = make_game_state()
    npc = make_npc(
        id="npc_1",
        name="Theo",
        status="active",
        name_rolled=True,
        memory=[make_memory(scene=1, event="Met the player", importance=5)],
    )
    game.npcs.append(npc)

    process_npc_details(game, [make_npc_detail(npc_id="npc_1", full_name="Klaus Kinski")], world_addition="")
    assert npc.name == "Theo"

    stub = next((n for n in game.npcs if n.name == "Klaus Kinski"), None)
    assert stub is not None
    assert stub.id != "npc_1"


def test_memory_guard_allows_no_memories() -> None:
    from straightjacket.engine.gamemaster.npc.processing import process_npc_details

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Der Fremde", status="active")
    game.npcs.append(npc)
    process_npc_details(game, [make_npc_detail(npc_id="npc_1", full_name="Heinrich Blum")], world_addition="")
    assert npc.name == "Heinrich Blum"


def test_a_restore_brings_back_the_tracks_and_the_combat_position() -> None:
    game = make_game_state()
    game.progress_tracks.append(make_progress_track(id="v1", name="Vow", track_type="vow", rank="dangerous", ticks=8))
    game.progress_tracks.append(
        make_progress_track(id="c1", name="Fight", track_type="combat", rank="formidable", ticks=0)
    )

    game.world.combat_position = "in_control"
    snap = game.snapshot()

    game.world.combat_position = "bad_spot"
    mark_progress(game.progress_tracks[0])
    game.progress_tracks[1].status = "completed"
    game.progress_tracks.append(make_progress_track(id="v2", name="New Vow", track_type="vow"))

    assert game.progress_tracks[0].ticks == 16
    assert len(game.progress_tracks) == 3

    game.restore(snap)

    assert len(game.progress_tracks) == 2
    assert game.progress_tracks[0].ticks == 8
    assert game.progress_tracks[0].name == "Vow"
    assert game.progress_tracks[1].status == "active"
    assert game.progress_tracks[1].ticks == 0
    assert game.world.combat_position == "in_control"
