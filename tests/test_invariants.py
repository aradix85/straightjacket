#!/usr/bin/env python3
"""Tests for the Elvira invariant checker.

Feeds assert_game_state deliberately broken game states and verifies
it catches every violation. Also verifies it passes clean states.

Run: python -m pytest tests/test_invariants.py -v
"""

from straightjacket.engine.config_loader import _ConfigNode
from straightjacket.engine import engine_loader
from straightjacket.engine.models import ClockData, GameState, MemoryEntry, NpcData

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "elvira"))


def _load_engine():
    engine_loader._eng = None
    engine_loader.eng()


def _stub_engine():
    """Stub with known limits for predictable assertions."""
    engine_loader._eng = _ConfigNode({
        "resources": {"health_max": 5, "spirit_max": 5, "supply_max": 5},
        "momentum": {"floor": -6, "max": 10},
        "chaos": {"min": 3, "max": 9},
        "npc": {"max_memory_entries": 25, "max_observations": 15,
                "max_reflections": 8, "memory_recency_decay": 0.92},
        "bonds": {"start": 0, "max": 4},
    }, "engine")


def _clean_game() -> GameState:
    game = GameState(player_name="Hero")
    game.resources.health = 5
    game.resources.spirit = 5
    game.resources.supply = 5
    game.resources.momentum = 3
    game.resources.max_momentum = 10
    game.world.chaos_factor = 5
    game.narrative.scene_count = 3
    game.npcs = [
        NpcData(id="npc_1", name="Kira", status="active",
                disposition="friendly", bond=2, bond_max=4,
                memory=[MemoryEntry(scene=1, event="Met player",
                         type="observation", importance=3)]),
    ]
    game.world.clocks = [
        ClockData(name="Doom", clock_type="threat", segments=6, filled=2),
    ]
    from straightjacket.engine.models import SceneLogEntry
    game.narrative.session_log = [
        SceneLogEntry(scene=3, summary="Last scene"),
    ]
    return game


# ── Clean state passes ────────────────────────────────────────

def test_clean_state_no_violations():
    _load_engine()
    # Import from the package, not the bot — needs engine loaded
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    violations = assert_game_state(game, turn=1)
    assert violations == []


# ── Resource violations ───────────────────────────────────────

def test_catches_health_out_of_range():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.resources.health = 7
    violations = assert_game_state(game, turn=1)
    assert any("health" in v for v in violations)


def test_catches_negative_spirit():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.resources.spirit = -1
    violations = assert_game_state(game, turn=1)
    assert any("spirit" in v for v in violations)


def test_catches_momentum_exceeds_max():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.resources.momentum = 12
    game.resources.max_momentum = 10
    violations = assert_game_state(game, turn=1)
    assert any("momentum" in v for v in violations)


# ── Chaos violations ─────────────────────────────────────────

def test_catches_chaos_below_min():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.world.chaos_factor = 2
    violations = assert_game_state(game, turn=1)
    assert any("chaos" in v.lower() for v in violations)


def test_catches_chaos_above_max():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.world.chaos_factor = 10
    violations = assert_game_state(game, turn=1)
    assert any("chaos" in v.lower() for v in violations)


# ── Crisis consistency ────────────────────────────────────────

def test_catches_crisis_mode_when_both_positive():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.crisis_mode = True  # but health=5 spirit=5
    violations = assert_game_state(game, turn=1)
    assert any("crisis" in v.lower() for v in violations)


def test_catches_game_over_missing():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.resources.health = 0
    game.resources.spirit = 0
    game.game_over = False  # should be True
    game.crisis_mode = True
    violations = assert_game_state(game, turn=1)
    assert any("game_over" in v.lower() for v in violations)


# ── NPC violations ────────────────────────────────────────────

def test_catches_npc_empty_id():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.npcs[0].id = ""
    violations = assert_game_state(game, turn=1)
    assert any("empty id" in v for v in violations)


def test_catches_npc_invalid_disposition():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.npcs[0].disposition = "angry"  # not in canonical 5
    violations = assert_game_state(game, turn=1)
    assert any("disposition" in v for v in violations)


def test_catches_npc_bond_over_max():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.npcs[0].bond = 5
    game.npcs[0].bond_max = 4
    violations = assert_game_state(game, turn=1)
    assert any("bond" in v for v in violations)


def test_catches_npc_memory_missing_fields():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.npcs[0].memory = [MemoryEntry(scene=1, event="", type="", importance=0)]
    violations = assert_game_state(game, turn=1)
    assert any("event" in v for v in violations)
    assert any("type" in v for v in violations)
    assert any("importance" in v for v in violations)


def test_catches_alias_duplicates_name():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.npcs[0].aliases = ["Kira"]  # same as name
    violations = assert_game_state(game, turn=1)
    assert any("alias" in v.lower() and "duplicate" in v.lower() for v in violations)


# ── Clock violations ─────────────────────────────────────────

def test_catches_clock_overfilled():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.world.clocks[0].filled = 8  # segments is 6
    violations = assert_game_state(game, turn=1)
    assert any("filled" in v for v in violations)


def test_catches_fired_but_not_full():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.world.clocks[0].fired = True
    game.world.clocks[0].filled = 3  # not full yet
    violations = assert_game_state(game, turn=1)
    assert any("fired" in v.lower() for v in violations)


def test_catches_invalid_clock_type():
    _load_engine()
    from elvira_bot.invariants import assert_game_state
    game = _clean_game()
    game.world.clocks[0].clock_type = "timer"  # not valid
    violations = assert_game_state(game, turn=1)
    assert any("clock_type" in v for v in violations)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


# ── Narration quality check tests ─────────────────────────────

def test_quality_catches_leaked_result_type():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality("The warrior strikes. STRONG_HIT. The blade bites deep.")
    assert any("result type" in i for i in issues)


def test_quality_catches_leaked_stat_value():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality("You feel weakened. health = 3. The wound bleeds.")
    assert any("stat value" in i for i in issues)


def test_quality_catches_xml_tags():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality("The door creaks. <memory_updates>test</memory_updates>")
    assert any("XML" in i for i in issues)


def test_quality_catches_markdown():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality("She said **hello** to the stranger.")
    assert any("markdown bold" in i for i in issues)


def test_quality_passes_clean_narration():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality(
        "The wind howled through the broken windows. She stepped inside, "
        "her boots crunching on shattered glass.")
    assert issues == []


def test_quality_catches_bracket_annotations():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "elvira"))
    from elvira_bot.quality_checks import check_narration_quality
    issues = check_narration_quality("The blade struck true. [CLOCK CREATED: Shadow Rising 0/6]")
    assert any("bracket" in i for i in issues)
