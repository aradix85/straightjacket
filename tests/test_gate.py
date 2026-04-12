#!/usr/bin/env python3
"""Tests for NPC information gating (step 6).

Verifies that gate levels are computed correctly and that the narrator
prompt contains only the information allowed by the gate.

Run: python -m pytest tests/test_gate.py -v
"""

import pytest

from straightjacket.engine.mechanics import compute_npc_gate, resolve_npc_stance
from straightjacket.engine.models import (
    BrainResult,
    GameState,
    MemoryEntry,
    NpcData,
    ProgressTrack,
    RollResult,
)
from straightjacket.engine.prompt_builders import build_action_prompt

# Use real engine.yaml
pytestmark = pytest.mark.usefixtures("load_engine")


def _npc(
    disposition: str = "neutral",
    memories: int = 0,
    first_scene: int = 1,
    gather_count: int = 0,
    secrets: list[str] | None = None,
) -> NpcData:
    mems = [
        MemoryEntry(scene=first_scene + i, event=f"Event {i}", emotional_weight="neutral", importance=3)
        for i in range(memories)
    ]
    return NpcData(
        id="npc_1",
        name="Kira",
        description="A wary trader with a scar across her left cheek",
        agenda="Protect her cargo",
        instinct="Counts exits before entering",
        arc="Growing more suspicious",
        disposition=disposition,
        memory=mems,
        secrets=secrets or ["Kira is smuggling forbidden tech"],
        gather_count=gather_count,
    )


def _game(npc: NpcData, scene: int = 5, bond: int = 0) -> GameState:
    game = GameState(player_name="Ash", setting_id="starforged", setting_genre="starforged")
    game.world.current_location = "The Docks"
    game.narrative.scene_count = scene
    game.npcs.append(npc)
    if bond > 0:
        game.progress_tracks.append(
            ProgressTrack(
                id=f"connection_{npc.id}",
                name=npc.name,
                track_type="connection",
                rank="dangerous",
                ticks=bond * 4,
            )
        )
    return game


# ── Gate computation ──────────────────────────────────────────


def test_gate_0_stranger() -> None:
    """No memories, no bond, no gathers → gate 0."""
    npc = _npc(memories=0)
    game = _game(npc, bond=0)
    gate = compute_npc_gate(game, npc, current_scene=1, stance="indifferent")
    assert gate == 0


def test_gate_1_brief_contact() -> None:
    """Known for 2 scenes, low bond → gate 1."""
    npc = _npc(memories=1, first_scene=1)
    game = _game(npc, bond=0)
    gate = compute_npc_gate(game, npc, current_scene=3, stance="polite")
    assert gate == 1


def test_gate_2_some_interaction() -> None:
    """Known for a few scenes + bond 2 or gather success → gate 2."""
    npc = _npc(memories=2, first_scene=1)
    game = _game(npc, bond=2)
    gate = compute_npc_gate(game, npc, current_scene=4, stance="engaged")
    assert gate == 2


def test_gate_3_trust_building() -> None:
    """Long acquaintance + mid bond, no gathers → gate 3."""
    npc = _npc(memories=5, first_scene=1, gather_count=0)
    game = _game(npc, bond=2)
    gate = compute_npc_gate(game, npc, current_scene=8, stance="open")
    assert gate == 3


def test_gate_4_fully_open() -> None:
    """High bond + many gathers + long history → gate 4."""
    npc = _npc(memories=8, first_scene=1, gather_count=2)
    game = _game(npc, bond=4)
    gate = compute_npc_gate(game, npc, current_scene=10, stance="unreserved")
    assert gate == 4


def test_gate_capped_by_hostile_stance() -> None:
    """Hostile stance caps gate at 1 regardless of bond/history."""
    npc = _npc(disposition="hostile", memories=8, first_scene=1, gather_count=3)
    game = _game(npc, bond=4)
    stance = resolve_npc_stance(game, npc, "combat")
    gate = compute_npc_gate(game, npc, current_scene=10, stance=stance.stance)
    assert gate <= 2


def test_gate_capped_by_evasive_stance() -> None:
    """Evasive stance caps gate at 1."""
    npc = _npc(disposition="distrustful", memories=5, first_scene=1, gather_count=2)
    game = _game(npc, bond=0)
    gate = compute_npc_gate(game, npc, current_scene=8, stance="evasive")
    assert gate <= 1


def test_gate_never_negative() -> None:
    npc = _npc(memories=0)
    game = _game(npc, bond=0)
    gate = compute_npc_gate(game, npc, current_scene=1, stance="stonewalling")
    assert gate == 0


def test_gate_never_above_4() -> None:
    npc = _npc(memories=20, first_scene=1, gather_count=10)
    game = _game(npc, bond=4)
    gate = compute_npc_gate(game, npc, current_scene=100, stance="unreserved")
    assert gate == 4


# ── Prompt filtering ──────────────────────────────────────────


def _build_prompt(npc: NpcData, scene: int = 5, bond: int = 0) -> str:
    game = _game(npc, scene, bond=bond)
    brain = BrainResult(
        move="adventure/face_danger", stat="edge", target_npc="npc_1", player_intent="approach carefully"
    )
    roll = RollResult(
        d1=3,
        d2=4,
        c1=6,
        c2=7,
        stat_name="edge",
        stat_value=2,
        action_score=9,
        result="WEAK_HIT",
        move="adventure/face_danger",
    )
    return build_action_prompt(
        game,
        brain,
        roll,
        ["momentum +1"],
        [],
        [],
        consequence_sentences=["The tide shifts."],
        player_words="approach carefully",
    )


def test_gate_0_shows_only_name_and_description() -> None:
    """Gate 0: no agenda, no memories, no secrets in prompt."""
    npc = _npc(memories=0)
    prompt = _build_prompt(npc, scene=1)
    assert "Kira" in prompt
    assert "wary trader" in prompt
    assert "Protect her cargo" not in prompt  # agenda hidden
    assert "smuggling" not in prompt  # secret hidden
    assert "Counts exits" not in prompt  # instinct hidden


def test_gate_2_shows_agenda_and_memories() -> None:
    """Gate 2: agenda visible, memories visible, no secrets."""
    npc = _npc(memories=3, first_scene=1)
    prompt = _build_prompt(npc, scene=5)
    assert "Protect her cargo" in prompt or "agenda:" in prompt
    assert "smuggling" not in prompt  # secrets still hidden


def test_gate_4_shows_secrets() -> None:
    """Gate 4: everything visible including secrets."""
    npc = _npc(memories=8, first_scene=1, gather_count=2)
    prompt = _build_prompt(npc, scene=10)
    assert "smuggling" in prompt


def test_gate_attribute_in_prompt() -> None:
    """Gate level should appear as attribute for debugging."""
    npc = _npc(memories=1, first_scene=1)
    prompt = _build_prompt(npc, scene=3)
    assert 'gate="' in prompt
