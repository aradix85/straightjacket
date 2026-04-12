#!/usr/bin/env python3
"""Tests for typed data models: serialization, isolation, edge cases.

Run: python -m pytest tests/test_models.py -v
Or:  python tests/test_models.py
"""


# Stubs are set up in conftest.py

from straightjacket.engine.models import (
    MemoryEntry,
    NpcData,
    ClockData,
    GameState,
    ProgressTrack,
    StoryBlueprint,
    StoryAct,
)


# ── NpcData ───────────────────────────────────────────────────


def test_roll_action_cap() -> None:
    """Action score caps at 10."""
    from straightjacket.engine.mechanics import roll_action
    import random

    random.seed(42)
    for _ in range(50):
        r = roll_action("edge", 3, "adventure/face_danger")
        assert r.action_score <= 10


def test_compel_no_disposition_shift(load_engine: None) -> None:
    """compel STRONG_HIT marks connection progress, no disposition shift."""
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = GameState()
    npc = NpcData(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        ProgressTrack(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    resolve_move_outcome(game, "adventure/compel", "STRONG_HIT", target_npc_id="npc_1")
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert conn.ticks > 0  # bond progress marked
    assert npc.disposition == "neutral"


def test_test_bond_disposition_shift(load_engine: None) -> None:
    """test_your_relationship STRONG_HIT marks connection progress AND disposition shift."""
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = GameState()
    npc = NpcData(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    game.progress_tracks.append(
        ProgressTrack(id="connection_npc_1", name="Test", track_type="connection", rank="dangerous", ticks=0)
    )
    resolve_move_outcome(game, "connection/test_your_relationship", "STRONG_HIT", target_npc_id="npc_1")
    conn = next(t for t in game.progress_tracks if t.id == "connection_npc_1")
    assert conn.ticks > 0
    assert npc.disposition == "friendly"


def test_npc_owned_threat_clock_ticks_in_agency() -> None:
    """v0.9.86: check_npc_agency ticks NPC-owned threat clocks."""
    from straightjacket.engine.mechanics import check_npc_agency

    game = GameState()
    game.narrative.scene_count = 5
    npc = NpcData(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = ClockData(name="Villain Plan", clock_type="threat", segments=6, filled=3, owner="Villain")
    game.world.clocks.append(clock)
    actions, clock_events = check_npc_agency(game)
    assert clock.filled == 4
    assert len(actions) >= 1
    assert len(clock_events) == 1
    assert clock_events[0].clock == "Villain Plan"
    assert not clock_events[0].triggered


def test_npc_agency_clock_fires_on_full() -> None:
    """check_npc_agency returns triggered=True when clock fills completely."""
    from straightjacket.engine.mechanics import check_npc_agency

    game = GameState()
    game.narrative.scene_count = 10
    npc = NpcData(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    clock = ClockData(name="Villain Plan", clock_type="threat", segments=4, filled=3, owner="Villain")
    game.world.clocks.append(clock)
    actions, clock_events = check_npc_agency(game)
    assert clock.filled == 4
    assert clock.fired
    assert len(clock_events) == 1
    assert clock_events[0].triggered
    assert any("CLOCK FILLED" in a for a in actions)


def test_npc_agency_empty_on_wrong_scene() -> None:
    """check_npc_agency returns empty on non-5th scenes."""
    from straightjacket.engine.mechanics import check_npc_agency

    game = GameState()
    game.narrative.scene_count = 3
    npc = NpcData(id="npc_1", name="Villain", agenda="Take over", status="active")
    game.npcs.append(npc)
    actions, clock_events = check_npc_agency(game)
    assert actions == []
    assert clock_events == []


def test_autonomous_clocks_skip_npc_owned(load_engine: None) -> None:
    """Autonomous clock ticking skips NPC-owned clocks."""
    from straightjacket.engine.mechanics import tick_autonomous_clocks
    import random

    random.seed(0)
    game = GameState()
    clock = ClockData(name="NPC Clock", clock_type="threat", segments=6, filled=2, owner="Villain")
    game.world.clocks.append(clock)
    for _ in range(20):
        tick_autonomous_clocks(game)
    assert clock.filled == 2


def test_npc_arc_field() -> None:
    """NpcData has arc field, serialized in to_dict/from_dict."""
    npc = NpcData(id="npc_1", name="Test", arc="Beginning to trust the player")
    assert npc.arc == "Beginning to trust the player"
    d = npc.to_dict()
    assert d["arc"] == "Beginning to trust the player"
    restored = NpcData.from_dict(d)
    assert restored.arc == "Beginning to trust the player"


def test_story_blueprint_triggered_director_phases() -> None:
    """StoryBlueprint tracks triggered_director_phases for phase dedup."""
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
    """triggered_director_phases survives snapshot/restore cycle."""
    game = GameState()
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
    """should_call_director skips already-fired phase triggers."""
    from straightjacket.engine.director import should_call_director

    game = GameState()
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
    # At scene 12 with act_0 triggered, current act is resolution
    reason = should_call_director(game)
    assert reason == "phase:resolution"
    # Mark as fired
    bp.triggered_director_phases.append("resolution")
    # Second call: should NOT fire for resolution again
    reason2 = should_call_director(game)
    assert reason2 != "phase:resolution"


def test_memory_guard_rejects_zero_overlap() -> None:
    """process_npc_details rejects identity reveal when NPC has memories and zero word overlap."""
    from straightjacket.engine.npc.processing import process_npc_details

    game = GameState()
    npc = NpcData(
        id="npc_1",
        name="Theo",
        status="active",
        memory=[MemoryEntry(scene=1, event="Met the player", importance=5)],
    )
    game.npcs.append(npc)
    # Try to rename Theo to Klaus Kinski — zero word overlap, should be rejected
    process_npc_details(game, [{"npc_id": "npc_1", "full_name": "Klaus Kinski"}])
    assert npc.name == "Theo"  # unchanged
    # A stub should have been created for Klaus Kinski
    stub = next((n for n in game.npcs if n.name == "Klaus Kinski"), None)
    assert stub is not None
    assert stub.id != "npc_1"


def test_memory_guard_allows_no_memories() -> None:
    """process_npc_details allows identity reveal when NPC has no memories."""
    from straightjacket.engine.npc.processing import process_npc_details

    game = GameState()
    npc = NpcData(id="npc_1", name="Der Fremde", status="active")
    game.npcs.append(npc)
    process_npc_details(game, [{"npc_id": "npc_1", "full_name": "Heinrich Blum"}])
    assert npc.name == "Heinrich Blum"


def test_social_move_unresolved_target_skips_bond(load_engine: None) -> None:
    """Social move with unresolvable target_npc skips bond/disposition changes."""
    from straightjacket.engine.mechanics.move_outcome import resolve_move_outcome

    game = GameState()
    npc = NpcData(id="npc_1", name="Test", disposition="neutral")
    game.npcs.append(npc)
    # target_npc that doesn't match any NPC
    resolve_move_outcome(game, "adventure/compel", "STRONG_HIT", target_npc_id="nonexistent")
    assert npc.disposition == "neutral"  # unchanged
