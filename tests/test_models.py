from straightjacket.engine.models import (
    NpcData,
    StoryBlueprint,
    StoryAct,
)
from tests._helpers import make_clock, make_game_state, make_memory, make_npc, make_progress_track


def test_roll_action_cap() -> None:
    from straightjacket.engine.mechanics import roll_action
    import random

    random.seed(42)
    for _ in range(50):
        r = roll_action("edge", 3, "adventure/face_danger")
        assert r.action_score <= 10


def test_compel_no_disposition_shift(load_engine: None) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    resolve_move_outcome(game, "adventure/compel", "STRONG_HIT", target_npc_id="npc_1")
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert conn.ticks > 0
    assert npc.disposition == "neutral"


def test_test_bond_disposition_shift(load_engine: None) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    resolve_move_outcome(game, "connection/test_your_relationship", "STRONG_HIT", target_npc_id="npc_1")
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert conn.ticks > 0
    assert npc.disposition == "friendly"


def test_npc_owned_threat_clock_ticks_in_agency() -> None:
    from straightjacket.engine.mechanics import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 5
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = make_clock(name="Villain Plan", clock_type="threat", segments=6, filled=3, owner="Villain")
    game.world.clocks.append(clock)
    actions, clock_events = check_npc_agency(game)
    assert clock.filled == 4
    assert len(actions) >= 1
    assert len(clock_events) == 1
    assert clock_events[0].clock == "Villain Plan"
    assert not clock_events[0].triggered


def test_npc_agency_clock_fires_on_full() -> None:
    from straightjacket.engine.mechanics import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 10
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = make_clock(name="Villain Plan", clock_type="threat", segments=4, filled=3, owner="Villain")
    game.world.clocks.append(clock)
    actions, clock_events = check_npc_agency(game)
    assert clock.filled == 4
    assert clock.fired
    assert len(clock_events) == 1
    assert clock_events[0].triggered
    assert any("CLOCK FILLED" in a for a in actions)


def test_npc_agency_empty_on_wrong_scene() -> None:
    from straightjacket.engine.mechanics import check_npc_agency

    game = make_game_state()
    game.narrative.scene_count = 3
    npc = make_npc(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    actions, clock_events = check_npc_agency(game)
    assert actions == []
    assert clock_events == []


def test_autonomous_clocks_skip_npc_owned(load_engine: None) -> None:
    from straightjacket.engine.mechanics import tick_autonomous_clocks
    import random

    random.seed(0)
    game = make_game_state()
    clock = make_clock(name="NPC Clock", clock_type="threat", segments=6, filled=2, owner="Villain")
    game.world.clocks.append(clock)
    for _ in range(20):
        tick_autonomous_clocks(game)
    assert clock.filled == 2


def test_npc_arc_field() -> None:
    npc = make_npc(id="npc_1", name="Test", arc="Beginning to trust the player")
    assert npc.arc == "Beginning to trust the player"
    d = npc.to_dict()
    assert d["arc"] == "Beginning to trust the player"
    restored = NpcData.from_dict(d)
    assert restored.arc == "Beginning to trust the player"


def test_story_blueprint_triggered_director_phases() -> None:
    bp = StoryBlueprint(
        central_conflict="test",
        antagonist_force="villain",
        thematic_thread="theme",
        structure_type="3act",
        revealed=[],
        triggered_transitions=[],
        story_complete=False,
    )
    assert bp.triggered_director_phases == []
    bp.triggered_director_phases.append("climax")
    d = bp.to_dict()
    assert d["triggered_director_phases"] == ["climax"]
    restored = StoryBlueprint.from_dict(d)
    assert restored.triggered_director_phases == ["climax"]


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
        StoryAct(phase="setup", title="Setup", scene_range=[1, 5]),
        StoryAct(phase="climax", title="Climax", scene_range=[6, 10]),
        StoryAct(phase="resolution", title="Resolution", scene_range=[11, 15]),
    ]
    game.narrative.story_blueprint = bp

    reason = should_call_director(game)
    assert reason == "phase:resolution"

    bp.triggered_director_phases.append("resolution")

    reason2 = should_call_director(game)
    assert reason2 != "phase:resolution"


def test_memory_guard_rejects_zero_overlap() -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = make_game_state()
    npc = make_npc(
        id="npc_1",
        name="Theo",
        status="active",
        memory=[make_memory(scene=1, event="Met the player", importance=5)],
    )
    game.npcs.append(npc)

    process_npc_details(game, [{"npc_id": "npc_1", "full_name": "Klaus Kinski"}])
    assert npc.name == "Theo"

    stub = next((n for n in game.npcs if n.name == "Klaus Kinski"), None)
    assert stub is not None
    assert stub.id != "npc_1"


def test_memory_guard_allows_no_memories() -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Der Fremde", status="active")
    game.npcs.append(npc)
    process_npc_details(game, [{"npc_id": "npc_1", "full_name": "Heinrich Blum"}])
    assert npc.name == "Heinrich Blum"


def test_social_move_unresolved_target_skips_bond(load_engine: None) -> None:
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = make_game_state()
    npc = make_npc(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)

    resolve_move_outcome(game, "adventure/compel", "STRONG_HIT", target_npc_id="nonexistent")
    assert npc.disposition == "neutral"


def test_progress_tracks_snapshot_restore() -> None:
    game = make_game_state()
    game.progress_tracks.append(make_progress_track(id="v1", name="Vow", track_type="vow", rank="dangerous", ticks=8))
    game.progress_tracks.append(
        make_progress_track(id="c1", name="Fight", track_type="combat", rank="formidable", ticks=0)
    )

    snap = game.snapshot()

    game.progress_tracks[0].mark_progress()
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
