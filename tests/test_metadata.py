#!/usr/bin/env python3
"""Tests for ai/metadata.py: narrator metadata application.

Covers: apply_narrator_metadata pipeline, process_deceased_npcs guards,
lore NPC creation, death corroboration voting, slug reference resolution.
"""

from straightjacket.engine.models import GameState
from tests._helpers import make_game_state, make_memory, make_npc


def _game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.world.time_of_day = "evening"
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            disposition="friendly",
            status="active",
            last_location="Tavern",
            memory=[make_memory(scene=4, event="Talked to player", importance=3)],
        ),
        make_npc(id="npc_2", name="Borin", disposition="neutral", status="active", last_location="Tavern"),
    ]
    return game


# ── apply_narrator_metadata: scene context ───────────────────


# ── process_deceased_npcs ────────────────────────────────────


def test_deceased_marks_present_npc(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_1"})
    assert game.npcs[0].status == "deceased"


def test_deceased_rejects_absent_npc(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_2"})
    assert game.npcs[0].status == "active"


def test_deceased_allows_absent_npc_with_current_scene_memory(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    game.npcs[0].memory.append(make_memory(scene=5, event="Just arrived", importance=5))
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_2"})
    assert game.npcs[0].status == "deceased"


def test_deceased_skips_already_dead(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    game.npcs[0].status = "deceased"
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids={"npc_1"})
    assert game.npcs[0].status == "deceased"


def test_deceased_no_guard_without_present_ids(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "npc_1"}], scene_present_ids=None)
    assert game.npcs[0].status == "deceased"


def test_deceased_unknown_npc_ignored(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import process_deceased_npcs

    game = _game()
    process_deceased_npcs(game, [{"npc_id": "nobody"}], scene_present_ids=None)
    assert all(n.status == "active" for n in game.npcs)


# ── lore NPCs ────────────────────────────────────────────────


def test_lore_npc_created(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    _process_lore_npcs(game, [{"name": "Ancient King", "description": "Legendary ruler"}])
    lore = [n for n in game.npcs if n.status == "lore"]
    assert len(lore) == 1
    assert lore[0].name == "Ancient King"


def test_lore_npc_skips_existing(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    count_before = len(game.npcs)
    _process_lore_npcs(game, [{"name": "Kira", "description": "Already exists"}])
    assert len(game.npcs) == count_before


def test_lore_npc_skips_empty_name(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _process_lore_npcs

    game = _game()
    count_before = len(game.npcs)
    _process_lore_npcs(game, [{"name": "", "description": "No name"}])
    assert len(game.npcs) == count_before


# ── death corroboration ──────────────────────────────────────


def test_death_corroboration_triggers(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # npc_2 has cross-vote from npc_1 + self-vote → should die
    game.npcs[0].memory.append(
        make_memory(scene=5, event="Borin was killed", importance=9, emotional_weight="devastated", about_npc="npc_2")
    )
    game.npcs[1].memory.append(make_memory(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "deceased"


def test_death_corroboration_needs_cross_vote(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Only self-vote, no cross-vote → should NOT die
    game.npcs[1].memory.append(make_memory(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    game.npcs[1].memory.append(make_memory(scene=5, event="Still dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


def test_death_corroboration_ignores_reflections(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Cross-vote is a reflection (Director-generated) → should not count
    game.npcs[0].memory.append(
        make_memory(
            scene=5,
            event="Borin was killed",
            importance=9,
            emotional_weight="devastated",
            about_npc="npc_2",
            type="reflection",
        )
    )
    game.npcs[1].memory.append(make_memory(scene=5, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


def test_death_corroboration_ignores_old_scenes(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import _check_death_corroboration

    game = _game()
    # Memories from scene 3, not current scene 5 → should not count
    game.npcs[0].memory.append(
        make_memory(scene=3, event="Borin was killed", importance=9, emotional_weight="devastated", about_npc="npc_2")
    )
    game.npcs[1].memory.append(make_memory(scene=3, event="I am dying", importance=9, emotional_weight="devastated"))
    _check_death_corroboration(game)
    assert game.npcs[1].status == "active"


# ── slug reference resolution ────────────────────────────────


# ── full pipeline ────────────────────────────────────────────


def test_metadata_full_pipeline(stub_all: None) -> None:
    from straightjacket.engine.ai.metadata import apply_narrator_metadata

    game = _game()
    metadata = {
        "new_npcs": [],
        "npc_renames": [],
        "npc_details": [],
        "deceased_npcs": [],
        "lore_npcs": [{"name": "The Founder", "description": "Built the arena"}],
    }
    apply_narrator_metadata(game, metadata, scene_present_ids={"npc_1", "npc_2"})
    assert any(n.status == "lore" for n in game.npcs)
    founder = next(n for n in game.npcs if n.name == "The Founder")
    assert founder.status == "lore"
