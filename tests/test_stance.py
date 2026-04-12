#!/usr/bin/env python3
"""Tests for NPC stance resolution (step 5).

Verifies that the stance matrix lookup produces correct stance labels
and behavioral constraints for different (disposition, bond, move_category)
combinations, and that stances appear in narrator prompts.

Run: python -m pytest tests/test_stance.py -v
"""

import pytest

from straightjacket.engine.mechanics import resolve_npc_stance
from straightjacket.engine.models import (
    BrainResult,
    GameState,
    NpcData,
    ProgressTrack,
    RollResult,
)
from straightjacket.engine.prompt_builders import build_action_prompt, build_dialog_prompt

# Use real engine.yaml for stance matrix tests
pytestmark = pytest.mark.usefixtures("load_engine")


def _npc(disposition: str = "neutral") -> NpcData:
    from straightjacket.engine.models import MemoryEntry

    return NpcData(
        id="npc_1",
        name="Kira",
        description="A wary trader",
        agenda="Protect her cargo",
        instinct="Counts exits before entering",
        disposition=disposition,
        memory=[MemoryEntry(scene=1, event="Kira appeared at the docks", emotional_weight="neutral", importance=3)],
    )


def _game(npc: NpcData | None = None, bond: int = 0) -> GameState:
    game = GameState(player_name="Ash", setting_id="starforged", setting_genre="starforged")
    game.world.current_location = "The Docks"
    game.narrative.scene_count = 3
    if npc:
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


# ── Stance resolver ───────────────────────────────────────────


def test_hostile_low_combat() -> None:
    npc = _npc("hostile")
    game = _game(npc, bond=0)
    stance = resolve_npc_stance(game, npc, "combat")
    assert stance.stance == "aggressive"
    assert "quarter" in stance.constraint.lower() or "hesitation" in stance.constraint.lower()


def test_distrustful_low_gather() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    stance = resolve_npc_stance(game, npc, "gather_information")
    assert stance.stance == "evasive"
    assert "silence" in stance.constraint.lower()


def test_friendly_mid_social() -> None:
    npc = _npc("friendly")
    game = _game(npc, bond=2)
    stance = resolve_npc_stance(game, npc, "social")
    assert stance.stance == "confiding"


def test_loyal_high_other() -> None:
    npc = _npc("loyal")
    game = _game(npc, bond=4)
    stance = resolve_npc_stance(game, npc, "other")
    assert stance.stance == "ride_or_die"


def test_neutral_low_other() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=0)
    stance = resolve_npc_stance(game, npc, "other")
    assert stance.stance == "indifferent"


def test_bond_range_mid() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=2)
    stance = resolve_npc_stance(game, npc, "social")
    assert stance.stance == "engaged"


def test_bond_range_high() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=4)
    stance = resolve_npc_stance(game, npc, "social")
    assert stance.stance == "open"


def test_unknown_move_category_defaults_to_other() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=1)
    stance = resolve_npc_stance(game, npc, "unknown_category")
    assert stance.stance == resolve_npc_stance(game, npc, "other").stance


def test_stance_has_npc_metadata() -> None:
    npc = _npc("friendly")
    game = _game(npc, bond=3)
    stance = resolve_npc_stance(game, npc, "social")
    assert stance.npc_id == "npc_1"
    assert stance.npc_name == "Kira"


def test_stance_constraint_not_empty() -> None:
    """Every matrix entry should have a non-empty constraint."""
    for disp in ("hostile", "distrustful", "neutral", "friendly", "loyal"):
        for bond in (0, 2, 4):
            for cat in ("combat", "social", "gather_information", "other"):
                npc = _npc(disp)
                game = _game(npc, bond=bond)
                stance = resolve_npc_stance(game, npc, cat)
                assert stance.constraint, f"Empty constraint for {disp}/{bond}/{cat}"
                assert stance.stance, f"Empty stance for {disp}/{bond}/{cat}"


# ── Prompt integration ────────────────────────────────────────


def test_stance_in_target_npc_block() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    brain = BrainResult(
        move="adventure/gather_information", stat="wits", target_npc="npc_1", player_intent="ask about the cargo"
    )
    roll = RollResult(
        d1=3,
        d2=4,
        c1=6,
        c2=7,
        stat_name="wits",
        stat_value=2,
        action_score=9,
        result="WEAK_HIT",
        move="adventure/gather_information",
    )
    prompt = build_action_prompt(
        game,
        brain,
        roll,
        ["momentum +1"],
        [],
        [],
        consequence_sentences=["The tide shifts."],
        player_words="I ask about the cargo",
    )
    assert 'stance="evasive"' in prompt
    assert "constraint=" in prompt
    # Raw disposition/bond should NOT appear in target_npc tag
    assert 'disposition="distrustful"' not in prompt
    assert 'bond="1/4"' not in prompt


def test_stance_in_activated_npc_block() -> None:
    npc1 = NpcData(id="npc_1", name="Kira", disposition="friendly", agenda="Trade", instinct="Cautious")
    npc2 = NpcData(id="npc_2", name="Rowan", disposition="hostile", agenda="Fight", instinct="Reckless")
    game = _game()
    game.npcs = [npc1, npc2]
    game.progress_tracks.append(
        ProgressTrack(id="connection_npc_1", name="Kira", track_type="connection", rank="dangerous", ticks=8)
    )
    brain = BrainResult(move="adventure/face_danger", stat="edge", target_npc="npc_1", player_intent="dodge")
    roll = RollResult(
        d1=4,
        d2=5,
        c1=3,
        c2=4,
        stat_name="edge",
        stat_value=2,
        action_score=10,
        result="STRONG_HIT",
        move="adventure/face_danger",
    )
    prompt = build_action_prompt(
        game,
        brain,
        roll,
        [],
        [],
        [],
        consequence_sentences=["The tide shifts."],
        player_words="dodge",
        activated_npcs=[npc1, npc2],
    )
    # Rowan (activated, not target) should have stance, not raw disposition
    assert "stance=" in prompt
    assert 'disposition="hostile"' not in prompt


def test_dialog_prompt_uses_social_stance() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    brain = BrainResult(move="dialog", dialog_only=True, target_npc="npc_1", player_intent="ask a question")
    prompt = build_dialog_prompt(
        game,
        brain,
        player_words="What happened last night?",
        activated_npcs=[npc],
    )
    assert 'stance="guarded"' in prompt
