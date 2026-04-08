#!/usr/bin/env python3
"""Tests for ai/metadata.py: narrator metadata application.

Covers: apply_narrator_metadata pipeline, process_deceased_npcs guards,
lore NPC creation, death corroboration voting, slug reference resolution.
"""

from straightjacket.engine import engine_loader, emotions_loader
from straightjacket.engine.config_loader import _ConfigNode
from straightjacket.engine.models import GameState, MemoryEntry, NpcData


def _stub():
    engine_loader._eng = _ConfigNode(
        {
            "bonds": {"start": 0, "max": 4},
            "npc": {
                "max_active": 12,
                "reflection_threshold": 30,
                "max_memory_entries": 25,
                "max_observations": 15,
                "max_reflections": 8,
                "memory_recency_decay": 0.92,
            },
            "disposition_shifts": {
                "hostile": "distrustful",
                "distrustful": "neutral",
                "neutral": "friendly",
                "friendly": "loyal",
            },
            "disposition_to_seed_emotion": {
                "hostile": "hostile",
                "distrustful": "suspicious",
                "neutral": "neutral",
                "friendly": "curious",
                "loyal": "trusting",
            },
            "move_categories": {
                "combat": ["clash"],
                "social": ["compel"],
                "endure": [],
                "recovery": [],
                "bond_on_weak_hit": [],
                "bond_on_strong_hit": [],
                "disposition_shift_on_strong_hit": [],
            },
            "death_emotions": ["betrayed", "devastated"],
        },
        "engine",
    )
    emotions_loader._data = {
        "importance": {"neutral": 2, "curious": 3, "betrayed": 9, "devastated": 9, "hostile": 5},
        "keyword_boosts": {7: ["death", "killed"]},
        "disposition_map": {
            "neutral": "neutral",
            "friendly": "friendly",
            "hostile": "hostile",
            "wary": "distrustful",
            "curious": "neutral",
        },
    }


def _game() -> GameState:
    game = GameState(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.world.time_of_day = "evening"
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Kira",
            disposition="friendly",
            bond=2,
            bond_max=4,
            status="active",
            last_location="Tavern",
            memory=[MemoryEntry(scene=4, event="Talked to player", importance=3)],
        ),
        NpcData(
            id="npc_2", name="Borin", disposition="neutral", bond=0, bond_max=4, status="active", last_location="Tavern"
        ),
    ]
    return game


# ── apply_narrator_metadata: scene context ───────────────────


def test_metadata_sets_scene_context():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"scene_context": "A tense standoff."})
    assert game.world.current_scene_context == "A tense standoff."


def test_metadata_ignores_empty_scene_context():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    game.world.current_scene_context = "Old context"
    apply_narrator_metadata(game, {"scene_context": "  "})
    assert game.world.current_scene_context == "Old context"


# ── apply_narrator_metadata: location update ─────────────────


def test_metadata_updates_location():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"location_update": "Market Square"})
    assert game.world.current_location == "Market Square"


def test_metadata_ignores_null_location():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"location_update": "null"})
    assert game.world.current_location == "Tavern"


def test_metadata_ignores_none_location():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"location_update": "none"})
    assert game.world.current_location == "Tavern"


# ── apply_narrator_metadata: time update ─────────────────────


def test_metadata_updates_time():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"time_update": "night"})
    assert game.world.time_of_day == "night"


def test_metadata_ignores_invalid_time():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"time_update": "banana"})
    assert game.world.time_of_day == "evening"


def test_metadata_normalizes_time_spaces():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    apply_narrator_metadata(game, {"time_update": "late evening"})
    assert game.world.time_of_day == "late_evening"


# ── process_deceased_npcs ────────────────────────────────────


def test_deceased_marks_present_npc():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_1"})
    assert game.npcs[0].status == "deceased"


def test_deceased_rejects_absent_npc():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_2"})
    assert game.npcs[0].status == "active"


def test_deceased_allows_absent_npc_with_current_scene_memory():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    game.npcs[0].memory.append(MemoryEntry(scene=5, event="Just arrived", importance=5))
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_2"})
    assert game.npcs[0].status == "deceased"


def test_deceased_skips_already_dead():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    game.npcs[0].status = "deceased"
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_1"})
    assert game.npcs[0].status == "deceased"


def test_deceased_no_guard_without_present_ids():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids=None)
    assert game.npcs[0].status == "deceased"


def test_deceased_unknown_npc_ignored():
    _stub()
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "nobody"}], scene_present_ids=None)
    assert all(n.status == "active" for n in game.npcs)


# ── lore NPCs ────────────────────────────────────────────────


def test_lore_npc_created():
    _stub()
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    _process_lore_npcs(game, [{"name": "Ancient King", "description": "Legendary ruler"}])
    lore = [n for n in game.npcs if n.status == "lore"]
    assert len(lore) == 1
    assert lore[0].name == "Ancient King"


def test_lore_npc_skips_existing():
    _stub()
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    count_before = len(game.npcs)
    _process_lore_npcs(game, [{"name": "Kira", "description": "Already exists"}])
    assert len(game.npcs) == count_before


def test_lore_npc_skips_empty_name():
    _stub()
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    count_before = len(game.npcs)
    _process_lore_npcs(game, [{"name": "", "description": "No name"}])
    assert len(game.npcs) == count_before


# ── death corroboration ──────────────────────────────────────


def test_death_corroboration_triggers():
    _stub()
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # npc_2 has cross-vote from npc_1 + self-vote → should die
    game.npcs[0].memory.append(
        MemoryEntry(scene=5, event="Borin was killed", importance=9, emotional_weight="devastated", about_npc="npc_2")
    )
    game.npcs[1].memory.append(MemoryEntry(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "deceased"


def test_death_corroboration_needs_cross_vote():
    _stub()
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Only self-vote, no cross-vote → should NOT die
    game.npcs[1].memory.append(MemoryEntry(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    game.npcs[1].memory.append(MemoryEntry(scene=5, event="Still dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


def test_death_corroboration_ignores_reflections():
    _stub()
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Cross-vote is a reflection (Director-generated) → should not count
    game.npcs[0].memory.append(
        MemoryEntry(
            scene=5,
            event="Borin was killed",
            importance=9,
            emotional_weight="devastated",
            about_npc="npc_2",
            type="reflection",
        )
    )
    game.npcs[1].memory.append(MemoryEntry(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


def test_death_corroboration_ignores_old_scenes():
    _stub()
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Memories from scene 3, not current scene 5 → should not count
    game.npcs[0].memory.append(
        MemoryEntry(scene=3, event="Borin was killed", importance=9, emotional_weight="devastated", about_npc="npc_2")
    )
    game.npcs[1].memory.append(MemoryEntry(scene=3, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


# ── slug reference resolution ────────────────────────────────


def test_resolve_slug_refs():
    _stub()
    from straightjacket.engine.ai.metadata import _resolve_slug_refs

    game = _game()
    fresh = [NpcData(id="npc_3", name="Moderator mit Headset")]
    game.npcs.append(fresh[0])
    mem_updates = [{"npc_id": "moderator_headset", "event": "Spoke loudly"}]
    _resolve_slug_refs(game, mem_updates, fresh)
    assert mem_updates[0]["npc_id"] == "npc_3"


def test_resolve_slug_refs_skips_known_ids():
    _stub()
    from straightjacket.engine.ai.metadata import _resolve_slug_refs

    game = _game()
    fresh = [NpcData(id="npc_3", name="Someone")]
    game.npcs.append(fresh[0])
    mem_updates = [{"npc_id": "npc_1", "event": "Already known"}]
    _resolve_slug_refs(game, mem_updates, fresh)
    assert mem_updates[0]["npc_id"] == "npc_1"  # unchanged


# ── full pipeline ────────────────────────────────────────────


def test_metadata_full_pipeline():
    _stub()
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    metadata = {
        "scene_context": "A fight broke out.",
        "location_update": "Arena",
        "time_update": "night",
        "memory_updates": [
            {"npc_id": "npc_1", "event": "Watched the fight", "emotional_weight": "curious"},
        ],
        "new_npcs": [],
        "npc_renames": [],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [{"name": "The Founder", "description": "Built the arena"}],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids={"npc_1", "npc_2"})
    assert game.world.current_scene_context == "A fight broke out."
    assert game.world.current_location == "Arena"
    assert game.world.time_of_day == "night"
    assert any(n.status == "lore" for n in game.npcs)
    # Memory was added to Kira
    kira = next(n for n in game.npcs if n.id == "npc_1")
    assert any("fight" in m.event for m in kira.memory)
