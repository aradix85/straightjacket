#!/usr/bin/env python3
"""Tests for TurnSnapshot serialization and start_new_chapter NPC handling.

TurnSnapshot.to_dict()/from_dict() reconstructs BrainResult and RollResult
from dicts with try/except fallbacks. This tests the full round-trip and
edge cases (missing fields, corrupted data).

The chapter NPC tests verify the returning_npcs deepcopy pattern and
ID remapping that was bug-fixed in v0.26.0.

Run: python -m pytest tests/test_snapshot.py -v
"""

import json

from straightjacket.engine.models import (
    BrainResult,
    ClockData,
    GameState,
    MemoryEntry,
    NpcData,
    RollResult,
    TurnSnapshot,
)

# ── TurnSnapshot round-trip ──────────────────────────────────


def test_snapshot_basic_roundtrip() -> None:
    game = GameState(player_name="Test")
    game.resources.health = 3
    game.resources.momentum = 5
    game.world.current_location = "Cave"
    game.world.chaos_factor = 7
    game.npcs = [NpcData(id="npc_1", name="Kira", bond=2)]
    snap = game.snapshot()
    snap.player_input = "I search the cave"
    d = snap.to_dict()
    restored = TurnSnapshot.from_dict(d)
    assert restored.player_input == "I search the cave"
    assert restored.resources["health"] == 3
    assert restored.resources["momentum"] == 5
    assert restored.world["current_location"] == "Cave"
    assert len(restored.npcs) == 1
    assert restored.npcs[0]["name"] == "Kira"


def test_snapshot_with_brain_roundtrip() -> None:
    snap = TurnSnapshot()
    snap.brain = BrainResult(
        move="face_danger",
        stat="wits",
        position="desperate",
        effect="great",
        player_intent="Search carefully",
        target_npc="npc_1",
        dramatic_question="Will they find it?",
    )
    d = snap.to_dict()
    assert d["brain"]["move"] == "face_danger"
    assert d["brain"]["position"] == "desperate"
    restored = TurnSnapshot.from_dict(d)
    assert isinstance(restored.brain, BrainResult)
    assert restored.brain.move == "face_danger"
    assert restored.brain.stat == "wits"
    assert restored.brain.position == "desperate"
    assert restored.brain.target_npc == "npc_1"


def test_snapshot_with_roll_roundtrip() -> None:
    snap = TurnSnapshot()
    snap.roll = RollResult(
        d1=4,
        d2=3,
        c1=6,
        c2=8,
        stat_name="iron",
        stat_value=3,
        action_score=10,
        result="STRONG_HIT",
        move="strike",
        match=False,
    )
    d = snap.to_dict()
    assert d["roll"]["result"] == "STRONG_HIT"
    assert d["roll"]["move"] == "strike"
    restored = TurnSnapshot.from_dict(d)
    assert isinstance(restored.roll, RollResult)
    assert restored.roll.result == "STRONG_HIT"
    assert restored.roll.d1 == 4
    assert restored.roll.stat_name == "iron"
    assert restored.roll.match is False


def test_snapshot_corrupted_roll_recovers() -> None:
    """If roll dict has wrong keys, from_dict should set roll=None."""
    d = {
        "resources": {},
        "world": {},
        "narrative": {},
        "campaign": {},
        "npcs": [],
        "crisis_mode": False,
        "game_over": False,
        "player_input": "test",
        "roll": {"garbage": True},  # missing required fields
        "brain": None,
        "narration": None,
    }
    restored = TurnSnapshot.from_dict(d)
    assert restored.roll is None


def test_snapshot_json_full_roundtrip() -> None:
    """Full JSON serialization round-trip (as used by persistence)."""
    snap = TurnSnapshot(
        resources={"health": 4, "spirit": 3, "supply": 5, "momentum": 6, "max_momentum": 10},
        world={
            "current_location": "Forest",
            "chaos_factor": 5,
            "current_scene_context": "Dark",
            "time_of_day": "night",
            "location_history": ["Town"],
            "clocks": [],
        },
        narrative={"scene_count": 5, "director_guidance": {}, "scene_intensity_history": ["action"]},
        campaign={"epilogue_shown": False, "epilogue_dismissed": False},
        npcs=[{"id": "npc_1", "name": "Mira", "bond": 2}],
        crisis_mode=False,
        game_over=False,
        player_input="I hide behind the tree",
    )
    snap.brain = BrainResult(move="face_danger", stat="shadow", position="risky")
    snap.roll = RollResult(
        d1=5,
        d2=2,
        c1=3,
        c2=9,
        stat_name="shadow",
        stat_value=2,
        action_score=9,
        result="WEAK_HIT",
        move="face_danger",
        match=False,
    )
    snap.narration = "The branches concealed you."
    s = json.dumps(snap.to_dict(), ensure_ascii=False)
    d = json.loads(s)
    restored = TurnSnapshot.from_dict(d)
    assert isinstance(restored.brain, BrainResult)
    assert isinstance(restored.roll, RollResult)
    assert restored.brain.stat == "shadow"
    assert restored.roll.result == "WEAK_HIT"
    assert restored.narration == "The branches concealed you."
    assert restored.player_input == "I hide behind the tree"


# ── GameState snapshot/restore with TurnSnapshot ─────────────


def test_gamestate_snapshot_preserves_turn_context() -> None:
    """snapshot() creates TurnSnapshot; turn context is set afterward."""
    game = GameState(player_name="Hero")
    game.resources.health = 4
    game.resources.momentum = 5
    game.npcs = [NpcData(id="npc_1", name="Kira", bond=3)]
    game.world.clocks = [ClockData(name="Doom", filled=2)]
    snap = game.snapshot()
    snap.player_input = "I search"
    snap.brain = BrainResult(move="gather_information")
    # Mutate game state
    game.resources.health = 1
    game.npcs[0].bond = 0
    game.world.clocks[0].filled = 6
    # Restore
    game.restore(snap)
    assert game.resources.health == 4
    assert game.npcs[0].bond == 3
    assert game.world.clocks[0].filled == 2
    # Turn context survives on the snapshot object
    assert snap.player_input == "I search"
    assert snap.brain.move == "gather_information"


def test_gamestate_snapshot_last_turn_persists() -> None:
    """last_turn_snapshot survives to_dict/from_dict (save/load)."""
    game = GameState(player_name="Hero")
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = "I attack"
    game.last_turn_snapshot.brain = BrainResult(move="strike")
    game.last_turn_snapshot.roll = RollResult(
        d1=6,
        d2=6,
        c1=3,
        c2=4,
        stat_name="iron",
        stat_value=3,
        action_score=10,
        result="STRONG_HIT",
        move="strike",
        match=False,
    )
    d = game.to_dict()
    s = json.dumps(d, ensure_ascii=False)
    game2 = GameState.from_dict(json.loads(s))
    assert game2.last_turn_snapshot is not None
    assert game2.last_turn_snapshot.player_input == "I attack"
    assert isinstance(game2.last_turn_snapshot.brain, BrainResult)
    assert game2.last_turn_snapshot.brain.move == "strike"
    assert isinstance(game2.last_turn_snapshot.roll, RollResult)
    assert game2.last_turn_snapshot.roll.result == "STRONG_HIT"


# ── Chapter NPC deepcopy pattern ─────────────────────────────


def test_npc_id_remapping() -> None:
    """Simulates the chapter transition ID remap logic."""
    game = GameState(player_name="Hero")
    # Extractor created npc_1 and npc_2 for new chapter NPCs
    game.npcs = [
        NpcData(id="npc_1", name="New Guy"),
        NpcData(id="npc_2", name="New Gal"),
    ]
    # Returning NPCs from previous chapter (had old IDs)
    returning = [
        NpcData(id="npc_1", name="Kira", bond=3, memory=[MemoryEntry(scene=1, event="old memory", about_npc="npc_2")]),
        NpcData(
            id="npc_2", name="Borin", bond=1, memory=[MemoryEntry(scene=1, event="another memory", about_npc="npc_1")]
        ),
    ]
    # Simulate the merge: assign fresh IDs to returning NPCs
    new_npc_names = {n.name.lower().strip() for n in game.npcs}
    id_remap = {}
    next_id = max(int(n.id.split("_")[1]) for n in game.npcs if n.id.startswith("npc_")) + 1
    for old_npc in returning:
        if old_npc.name.lower().strip() in new_npc_names:
            continue
        old_id = old_npc.id
        fresh_id = f"npc_{next_id}"
        id_remap[old_id] = fresh_id
        old_npc.id = fresh_id
        game.npcs.append(old_npc)
        next_id += 1
    # Fix about_npc references
    for npc in game.npcs:
        for mem in npc.memory:
            if mem.about_npc and mem.about_npc in id_remap:
                mem.about_npc = id_remap[mem.about_npc]
    # Verify
    assert len(game.npcs) == 4
    kira = next(n for n in game.npcs if n.name == "Kira")
    borin = next(n for n in game.npcs if n.name == "Borin")
    assert kira.id == "npc_3"
    assert borin.id == "npc_4"
    # about_npc references should point to new IDs
    assert kira.memory[0].about_npc == "npc_4"  # was npc_2 → now npc_4 (Borin)
    assert borin.memory[0].about_npc == "npc_3"  # was npc_1 → now npc_3 (Kira)


# ── StoryBlueprint serialization ──────────────────────────────


def test_story_blueprint_roundtrip() -> None:
    """StoryBlueprint survives to_dict → from_dict."""
    from straightjacket.engine.models import StoryBlueprint

    bp = StoryBlueprint.from_dict(
        {
            "central_conflict": "The shadow threatens all",
            "antagonist_force": "Dark forces",
            "thematic_thread": "What is the cost of survival?",
            "structure_type": "3act",
            "acts": [
                {
                    "phase": "setup",
                    "title": "Gathering",
                    "goal": "Find allies",
                    "scene_range": [1, 7],
                    "mood": "mysterious",
                    "transition_trigger": "Allies gathered",
                },
                {
                    "phase": "confrontation",
                    "title": "Darkness",
                    "goal": "Face it",
                    "scene_range": [8, 14],
                    "mood": "tense",
                    "transition_trigger": "Shadow revealed",
                },
            ],
            "revelations": [
                {"id": "rev_1", "content": "The shadow is sentient", "earliest_scene": 5, "dramatic_weight": "high"},
            ],
            "possible_endings": [
                {"type": "triumph", "description": "Victory"},
                {"type": "tragedy", "description": "Defeat"},
            ],
            "revealed": ["rev_0"],
            "triggered_transitions": ["act_0"],
            "story_complete": False,
        }
    )
    d = bp.to_dict()
    bp2 = StoryBlueprint.from_dict(d)
    assert bp2.central_conflict == "The shadow threatens all"
    assert bp2.structure_type == "3act"
    assert len(bp2.acts) == 2
    assert bp2.acts[0].phase == "setup"
    assert bp2.acts[0].scene_range == [1, 7]
    assert bp2.acts[1].transition_trigger == "Shadow revealed"
    assert len(bp2.revelations) == 1
    assert bp2.revelations[0].id == "rev_1"
    assert bp2.revelations[0].dramatic_weight == "high"
    assert len(bp2.possible_endings) == 2
    assert bp2.possible_endings[0].type == "triumph"
    assert bp2.revealed == ["rev_0"]
    assert bp2.triggered_transitions == ["act_0"]
    assert bp2.story_complete is False


def test_gamestate_with_blueprint_roundtrip() -> None:
    """GameState with StoryBlueprint survives full save/load cycle."""
    from straightjacket.engine.models import StoryBlueprint

    game = GameState(player_name="Hero")
    game.narrative.story_blueprint = StoryBlueprint.from_dict(
        {
            "central_conflict": "Evil rises",
            "antagonist_force": "The corruption",
            "thematic_thread": "Cost of power",
            "structure_type": "kishotenketsu",
            "acts": [
                {
                    "phase": "ki_introduction",
                    "title": "Daily Life",
                    "goal": "Establish",
                    "scene_range": [1, 5],
                    "mood": "contemplative",
                    "transition_trigger": "Disruption",
                },
            ],
            "revelations": [
                {"id": "r1", "content": "Hidden truth", "earliest_scene": 3, "dramatic_weight": "critical"},
            ],
            "possible_endings": [{"type": "harmony", "description": "Peace"}],
            "revealed": [],
            "triggered_transitions": [],
            "story_complete": False,
        }
    )
    d = game.to_dict()
    s = json.dumps(d, ensure_ascii=False)
    game2 = GameState.from_dict(json.loads(s))
    bp = game2.narrative.story_blueprint
    assert bp is not None
    assert bp.central_conflict == "Evil rises"
    assert bp.structure_type == "kishotenketsu"
    assert len(bp.acts) == 1
    assert bp.acts[0].phase == "ki_introduction"
    assert bp.revelations[0].dramatic_weight == "critical"


# ── DirectorGuidance serialization ────────────────────────────
