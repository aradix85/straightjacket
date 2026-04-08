#!/usr/bin/env python3
"""Tests for typed data models: serialization, isolation, edge cases.

Run: python -m pytest tests/test_models.py -v
Or:  python tests/test_models.py
"""

import json

# Stubs are set up in conftest.py

from straightjacket.engine import engine_loader
from straightjacket.engine.models import (
    ChapterSummary,
    CampaignState,
    MemoryEntry,
    NpcData,
    NpcEvolution,
    ClockData,
    SceneLogEntry,
    RollResult,
    GameState,
    StoryBlueprint,
    StoryAct,
)


def _load_engine() -> None:
    engine_loader._eng = None
    engine_loader.eng()


# ── NpcData ───────────────────────────────────────────────────


def test_npcdata_roundtrip() -> None:
    npc = NpcData(
        id="npc_1", name="Kira", bond=3, memory=[MemoryEntry(event="test", type="observation")], aliases=["K"]
    )
    d = npc.to_dict()
    npc2 = NpcData.from_dict(d)
    assert npc2.name == "Kira"
    assert npc2.bond == 3
    assert len(npc2.memory) == 1
    assert isinstance(npc2.memory[0], MemoryEntry)
    assert npc2.aliases == ["K"]


def test_memoryentry_roundtrip() -> None:
    m = MemoryEntry(
        scene=3,
        event="fought",
        emotional_weight="angry",
        importance=5,
        type="observation",
        about_npc="npc_1",
        tone="defiant_rage",
        tone_key="angry",
    )
    d = m.to_dict()
    m2 = MemoryEntry.from_dict(d)
    assert m2.scene == 3
    assert m2.tone_key == "angry"
    assert m2.about_npc == "npc_1"


def test_clockdata_roundtrip() -> None:
    c = ClockData(name="Doom", segments=4, filled=2, clock_type="scheme", owner="Kira")
    d = c.to_dict()
    c2 = ClockData.from_dict(d)
    assert c2.name == "Doom"
    assert c2.filled == 2
    assert c2.owner == "Kira"


# ── SceneLogEntry ─────────────────────────────────────────────


def test_scenelogentry_roundtrip() -> None:
    e = SceneLogEntry(scene=3, summary="Test", result="STRONG_HIT", consequences=["health -2"])
    d = e.to_dict()
    e2 = SceneLogEntry.from_dict(d)
    assert e2.scene == 3
    assert e2.consequences == ["health -2"]


def test_chapter_summary_roundtrip() -> None:
    cs = ChapterSummary(
        chapter=1,
        title="First Blood",
        summary="It began.",
        unresolved_threads=["thread_a"],
        npc_evolutions=[NpcEvolution(name="Borin", projection="Hardened")],
        scenes=8,
    )
    d = cs.to_dict()
    restored = ChapterSummary.from_dict(d)
    assert restored.chapter == cs.chapter
    assert restored.title == cs.title
    assert restored.unresolved_threads == cs.unresolved_threads
    assert len(restored.npc_evolutions) == 1
    assert restored.npc_evolutions[0].name == "Borin"
    assert restored.scenes == cs.scenes


def test_campaign_state_from_dict_converts_chapter_dicts() -> None:
    """CampaignState.from_dict converts raw dicts in campaign_history to ChapterSummary."""
    data = {
        "campaign_history": [
            {
                "chapter": 1,
                "title": "Old Save",
                "summary": "From JSON",
                "unresolved_threads": ["thread"],
                "character_growth": "",
                "thematic_question": "",
                "post_story_location": "",
                "scenes": 10,
                "npc_evolutions": [{"name": "A", "projection": "B"}],
            },
        ],
        "chapter_number": 2,
        "epilogue_shown": False,
        "epilogue_dismissed": False,
        "epilogue_text": "",
    }
    cs = CampaignState.from_dict(data)
    ch = cs.campaign_history[0]
    assert isinstance(ch, ChapterSummary)
    assert ch.title == "Old Save"
    assert ch.unresolved_threads == ["thread"]
    assert ch.npc_evolutions[0].name == "A"


def test_campaign_state_roundtrip() -> None:
    cs = CampaignState(
        campaign_history=[
            ChapterSummary(chapter=1, title="A", summary="B"),
            ChapterSummary(chapter=2, title="C", summary="D", npc_evolutions=[NpcEvolution(name="X", projection="Y")]),
        ],
        chapter_number=3,
    )
    d = cs.to_dict()
    restored = CampaignState.from_dict(d)
    assert len(restored.campaign_history) == 2
    assert restored.campaign_history[1].npc_evolutions[0].name == "X"
    assert restored.chapter_number == 3


# ── GameState composite ──────────────────────────────────────


def test_gamestate_full_json_roundtrip() -> None:
    game = GameState(player_name="Hero", edge=3, heart=1, iron=1, shadow=1, wits=1)
    game.npcs.append(NpcData(id="npc_1", name="Ally", bond=2, memory=[MemoryEntry(event="met")]))
    game.world.clocks.append(ClockData(name="Threat"))
    game.narrative.session_log.append(SceneLogEntry(scene=1, summary="start"))
    j = json.dumps(game.to_dict())
    g2 = GameState.from_dict(json.loads(j))
    assert g2.player_name == "Hero"
    assert g2.npcs[0].memory[0].event == "met"
    assert g2.world.clocks[0].name == "Threat"


def test_gamestate_snapshot_restore() -> None:
    game = GameState(player_name="Test")
    game.resources.health = 3
    game.world.chaos_factor = 7
    game.npcs.append(NpcData(id="npc_1", name="Kira", bond=2))
    snap = game.snapshot()
    game.resources.health = 1
    game.world.chaos_factor = 9
    game.npcs[0].bond = 4
    game.restore(snap)
    assert game.resources.health == 3
    assert game.world.chaos_factor == 7
    assert game.npcs[0].bond == 2


# ── Mechanics (tested via models) ─────────────────────────────


def test_roll_action_cap() -> None:
    """Action score caps at 10."""
    from straightjacket.engine.mechanics import roll_action
    import random

    random.seed(42)
    for _ in range(50):
        r = roll_action("edge", 3, "face_danger")
        assert r.action_score <= 10


def test_compel_no_disposition_shift() -> None:
    _load_engine()
    """v0.9.86: compel STRONG_HIT grants bond+1 only, no disposition shift."""
    from straightjacket.engine.mechanics import apply_consequences
    from straightjacket.engine.models import BrainResult, RollResult

    game = GameState()
    npc = NpcData(id="npc_1", name="Test", disposition="neutral", bond=1, bond_max=4)
    game.npcs.append(npc)
    roll = RollResult(
        d1=5, d2=5, c1=2, c2=3, stat_name="heart", stat_value=2, action_score=10, result="STRONG_HIT", move="compel"
    )
    brain = BrainResult(target_npc="npc_1", effect="standard")
    apply_consequences(game, roll, brain)
    assert npc.bond == 2
    assert npc.disposition == "neutral"


def test_test_bond_disposition_shift() -> None:
    _load_engine()
    """v0.9.86: test_bond STRONG_HIT grants bond+1 AND disposition shift."""
    from straightjacket.engine.mechanics import apply_consequences
    from straightjacket.engine.models import BrainResult, RollResult

    game = GameState()
    npc = NpcData(id="npc_1", name="Test", disposition="neutral", bond=1, bond_max=4)
    game.npcs.append(npc)
    roll = RollResult(
        d1=5, d2=5, c1=2, c2=3, stat_name="heart", stat_value=2, action_score=10, result="STRONG_HIT", move="test_bond"
    )
    brain = BrainResult(target_npc="npc_1", effect="standard")
    apply_consequences(game, roll, brain)
    assert npc.bond == 2
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


def test_autonomous_clocks_skip_npc_owned() -> None:
    _load_engine()
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


def test_phase_trigger_dedup() -> None:
    _load_engine()
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


def test_social_move_unresolved_target_skips_bond() -> None:
    _load_engine()
    """Social move with no resolvable target skips bond/disposition effects."""
    from straightjacket.engine.mechanics import apply_consequences
    from straightjacket.engine.models import BrainResult

    game = GameState()
    roll = RollResult(
        d1=1,
        d2=1,
        c1=10,
        c2=10,
        stat_name="heart",
        stat_value=2,
        action_score=4,
        result="MISS",
        move="compel",
        match=False,
    )
    brain = BrainResult(target_npc="nonexistent_npc", position="risky", effect="standard")
    consequences, _ = apply_consequences(game, roll, brain)
    # No bond loss should appear — target doesn't exist
    assert not any("bond" in c for c in consequences)
    # But spirit loss still happens (social miss always costs spirit)
    assert any("spirit" in c for c in consequences)
