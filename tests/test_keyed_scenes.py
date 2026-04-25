"""Tests for keyed scenes (step 4).

Keyed scenes are director-pre-defined narrative beats that override the
chaos check at scene start. Step 4 ships the dataclass, evaluator, scene
integration, prompt block, and consumption semantics. Spawning is deferred
to step 7 (Adventure Crafter); these tests seed narrative.keyed_scenes
directly to exercise the evaluator.
"""

from __future__ import annotations

import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.mechanics import evaluate_keyed_scenes
from straightjacket.engine.mechanics.scene import SceneSetup, check_scene
from straightjacket.engine.models import (
    GameState,
    KeyedScene,
    NarrativeState,
    ProgressTrack,
)
from straightjacket.engine.prompt_shared import _pacing_block
from tests._helpers import (
    make_clock,
    make_game_state,
    make_npc,
    make_threat,
    make_world_state,
)


# ── Fixtures ────────────────────────────────────────────────


def _seed_game(**world_kwargs) -> GameState:
    """Build a minimal GameState ready for keyed-scene evaluation."""
    return make_game_state(world=make_world_state(**world_kwargs))


def _ks(**kwargs) -> KeyedScene:
    """Build a KeyedScene with sensible defaults; override per test."""
    kwargs.setdefault("id", "ks_test")
    kwargs.setdefault("trigger_type", "scene_count")
    kwargs.setdefault("trigger_value", "1")
    kwargs.setdefault("priority", 1)
    kwargs.setdefault("narrative_hint", "test hint")
    return KeyedScene(**kwargs)


# ── KeyedScene construction validation ────────────────────


def test_keyed_scene_unknown_trigger_type_raises():
    """Unknown trigger_type raises on construction so a buggy spawner
    cannot install a dead scene that fails silently at evaluation."""
    with pytest.raises(ValueError, match="Unknown KeyedScene trigger_type"):
        KeyedScene(
            id="ks_bad",
            trigger_type="not_a_real_trigger",
            trigger_value="x",
            priority=1,
            narrative_hint="",
        )


def test_keyed_scene_each_registered_trigger_constructs():
    """Every trigger type registered in engine/keyed_scenes.yaml accepts
    construction with no error — yaml and dispatch table align."""
    for trigger_name in eng().keyed_scenes.triggers:
        _ks(id=f"ks_{trigger_name}", trigger_type=trigger_name, trigger_value="x:1")


# ── clock_fills trigger ─────────────────────────────────────


def test_clock_fills_fires_when_threshold_met():
    game = _seed_game()
    game.world.clocks.append(make_clock(name="The Reckoning", filled=4, segments=6))
    game.narrative.keyed_scenes.append(_ks(trigger_type="clock_fills", trigger_value="The Reckoning:4"))
    matched = evaluate_keyed_scenes(game)
    assert matched is not None
    assert matched.id == "ks_test"


def test_clock_fills_does_not_fire_below_threshold():
    game = _seed_game()
    game.world.clocks.append(make_clock(name="The Reckoning", filled=2, segments=6))
    game.narrative.keyed_scenes.append(_ks(trigger_type="clock_fills", trigger_value="The Reckoning:4"))
    assert evaluate_keyed_scenes(game) is None


def test_clock_fills_unknown_clock_name_does_not_fire():
    """Unknown clock name silently no-fires — clocks come and go (created,
    completed, removed) so this is normal-case absence, not a bug like
    bond_threshold's unknown-npc-id case."""
    game = _seed_game()
    game.world.clocks.append(make_clock(name="Other Clock", filled=10, segments=6))
    game.narrative.keyed_scenes.append(_ks(trigger_type="clock_fills", trigger_value="Missing Clock:1"))
    assert evaluate_keyed_scenes(game) is None


# ── threat_menace_phase trigger ────────────────────────────


def test_threat_menace_phase_fires_at_filled_boxes():
    game = _seed_game()
    threat = make_threat(name="The Cult", menace_ticks=20)  # 5 filled boxes
    game.threats.append(threat)
    game.narrative.keyed_scenes.append(_ks(trigger_type="threat_menace_phase", trigger_value="The Cult:5"))
    assert evaluate_keyed_scenes(game) is not None


def test_threat_menace_phase_below_threshold_does_not_fire():
    game = _seed_game()
    threat = make_threat(name="The Cult", menace_ticks=12)  # 3 filled boxes
    game.threats.append(threat)
    game.narrative.keyed_scenes.append(_ks(trigger_type="threat_menace_phase", trigger_value="The Cult:5"))
    assert evaluate_keyed_scenes(game) is None


# ── bond_threshold trigger ─────────────────────────────────


def test_bond_threshold_fires_when_connection_track_meets_filled_boxes():
    game = _seed_game()
    npc = make_npc(id="npc_1", name="Kira")
    game.npcs.append(npc)
    # Connection track with 6 filled boxes (24 ticks, 4 ticks/box)
    game.progress_tracks.append(
        ProgressTrack(
            id="connection_npc_1",
            name="Connection: Kira",
            track_type="connection",
            rank="dangerous",
            max_ticks=40,
            ticks=24,
            status="active",
        )
    )
    game.narrative.keyed_scenes.append(_ks(trigger_type="bond_threshold", trigger_value="npc_1:6"))
    assert evaluate_keyed_scenes(game) is not None


def test_bond_threshold_below_threshold_does_not_fire():
    game = _seed_game()
    npc = make_npc(id="npc_1", name="Kira")
    game.npcs.append(npc)
    game.progress_tracks.append(
        ProgressTrack(
            id="connection_npc_1",
            name="Connection: Kira",
            track_type="connection",
            rank="dangerous",
            max_ticks=40,
            ticks=8,  # 2 filled boxes
            status="active",
        )
    )
    game.narrative.keyed_scenes.append(_ks(trigger_type="bond_threshold", trigger_value="npc_1:6"))
    assert evaluate_keyed_scenes(game) is None


def test_bond_threshold_unknown_npc_raises():
    """Unknown npc_id in a bond_threshold trigger is a spawner bug — silent
    no-fire would hide it. Distinct from clock_fills where unknown-name is
    normal-case absence."""
    game = _seed_game()
    game.narrative.keyed_scenes.append(_ks(trigger_type="bond_threshold", trigger_value="npc_ghost:1"))
    with pytest.raises(KeyError, match="bond_threshold trigger references unknown npc_id"):
        evaluate_keyed_scenes(game)


# ── chaos_extreme trigger ──────────────────────────────────


def test_chaos_extreme_max_fires_at_chaos_max():
    game = _seed_game(chaos_factor=eng().chaos.max)
    game.narrative.keyed_scenes.append(_ks(trigger_type="chaos_extreme", trigger_value="max"))
    assert evaluate_keyed_scenes(game) is not None


def test_chaos_extreme_min_fires_at_chaos_min():
    game = _seed_game(chaos_factor=eng().chaos.min)
    game.narrative.keyed_scenes.append(_ks(trigger_type="chaos_extreme", trigger_value="min"))
    assert evaluate_keyed_scenes(game) is not None


def test_chaos_extreme_does_not_fire_in_middle():
    mid = (eng().chaos.min + eng().chaos.max) // 2
    game = _seed_game(chaos_factor=mid)
    game.narrative.keyed_scenes.append(_ks(trigger_type="chaos_extreme", trigger_value="max"))
    assert evaluate_keyed_scenes(game) is None


def test_chaos_extreme_invalid_value_raises():
    game = _seed_game(chaos_factor=5)
    game.narrative.keyed_scenes.append(_ks(trigger_type="chaos_extreme", trigger_value="middle"))
    with pytest.raises(ValueError, match="chaos_extreme trigger_value must be"):
        evaluate_keyed_scenes(game)


# ── scene_count trigger ────────────────────────────────────


def test_scene_count_fires_at_threshold():
    game = _seed_game()
    game.narrative.scene_count = 10
    game.narrative.keyed_scenes.append(_ks(trigger_type="scene_count", trigger_value="10"))
    assert evaluate_keyed_scenes(game) is not None


def test_scene_count_below_threshold_does_not_fire():
    game = _seed_game()
    game.narrative.scene_count = 5
    game.narrative.keyed_scenes.append(_ks(trigger_type="scene_count", trigger_value="10"))
    assert evaluate_keyed_scenes(game) is None


# ── Priority ordering ──────────────────────────────────────


def test_priority_ordering_higher_wins():
    """When two keyed scenes both match, the higher-priority one fires."""
    game = _seed_game()
    game.narrative.scene_count = 20
    game.narrative.keyed_scenes.append(_ks(id="ks_low", trigger_type="scene_count", trigger_value="10", priority=1))
    game.narrative.keyed_scenes.append(_ks(id="ks_high", trigger_type="scene_count", trigger_value="10", priority=5))
    matched = evaluate_keyed_scenes(game)
    assert matched is not None
    assert matched.id == "ks_high"


def test_priority_tie_resolves_by_insertion_order():
    """Stable sort on priority ties — earlier-spawned wins."""
    game = _seed_game()
    game.narrative.scene_count = 20
    game.narrative.keyed_scenes.append(_ks(id="ks_first", trigger_type="scene_count", trigger_value="10", priority=3))
    game.narrative.keyed_scenes.append(_ks(id="ks_second", trigger_type="scene_count", trigger_value="10", priority=3))
    matched = evaluate_keyed_scenes(game)
    assert matched is not None
    assert matched.id == "ks_first"


# ── Consumption via check_scene ────────────────────────────


def test_check_scene_consumes_matched_keyed_scene():
    """check_scene removes the matched keyed scene from narrative.keyed_scenes;
    on the next call with the same setup but the consumed scene gone, the
    chaos roll runs."""
    game = _seed_game(chaos_factor=5)
    game.narrative.scene_count = 10
    game.narrative.keyed_scenes.append(_ks(id="ks_consume", trigger_type="scene_count", trigger_value="10"))
    setup = check_scene(game, roll=10)  # roll=10 → expected if it ran
    assert setup.scene_type == "keyed"
    assert setup.narrative_hint == "test hint"
    assert all(k.id != "ks_consume" for k in game.narrative.keyed_scenes)


def test_check_scene_keyed_priority_overrides_interrupt():
    """A keyed scene wins even when the chaos roll would have produced an
    interrupt (low even roll vs high CF)."""
    game = _seed_game(chaos_factor=9)
    game.narrative.scene_count = 10
    game.narrative.keyed_scenes.append(_ks(trigger_type="scene_count", trigger_value="10"))
    setup = check_scene(game, roll=2)  # would be interrupt without keyed
    assert setup.scene_type == "keyed"


def test_check_scene_no_match_falls_through_to_chaos():
    game = _seed_game(chaos_factor=5)
    game.narrative.scene_count = 1
    game.narrative.keyed_scenes.append(
        _ks(trigger_type="scene_count", trigger_value="10")  # 1 < 10, no fire
    )
    setup = check_scene(game, roll=8)
    assert setup.scene_type == "expected"


def test_check_scene_no_keyed_scenes_uses_chaos():
    """Empty keyed_scenes list — normal play prior to step 7 — chaos runs."""
    game = _seed_game(chaos_factor=5)
    setup = check_scene(game, roll=8)
    assert setup.scene_type == "expected"


# ── Snapshot / restore ─────────────────────────────────────


def test_narrative_state_snapshot_restores_keyed_scenes():
    """Mid-turn consumption can shrink keyed_scenes; snapshot must capture
    the full list so undo restores fired scenes."""
    nar = NarrativeState()
    nar.keyed_scenes.append(_ks(id="ks_a"))
    nar.keyed_scenes.append(_ks(id="ks_b"))
    snap = nar.snapshot()
    # Simulate consumption mid-turn
    nar.keyed_scenes = [k for k in nar.keyed_scenes if k.id != "ks_a"]
    assert len(nar.keyed_scenes) == 1
    nar.restore(snap)
    assert sorted(k.id for k in nar.keyed_scenes) == ["ks_a", "ks_b"]


def test_keyed_scene_serialization_roundtrip():
    original = _ks(id="ks_rt", trigger_type="clock_fills", trigger_value="x:3", priority=7)
    restored = KeyedScene.from_dict(original.to_dict())
    assert restored.id == "ks_rt"
    assert restored.trigger_type == "clock_fills"
    assert restored.trigger_value == "x:3"
    assert restored.priority == 7
    assert restored.narrative_hint == "test hint"


# ── Prompt block ───────────────────────────────────────────


def test_pacing_block_emits_keyed_scene_tag():
    game = _seed_game()
    setup = SceneSetup(scene_type="keyed", narrative_hint="The cult moves at dawn.")
    block = _pacing_block(game, setup)
    assert "<keyed_scene>The cult moves at dawn.</keyed_scene>" in block


def test_pacing_block_keyed_scene_xml_escapes_hint():
    """Hints with XML-special chars must be escaped — narrator prompt is XML."""
    game = _seed_game()
    setup = SceneSetup(scene_type="keyed", narrative_hint="A & B < C")
    block = _pacing_block(game, setup)
    assert "<keyed_scene>" in block
    # The escaping helper handles &, <, > — just confirm the raw chars do not appear inside
    inner = block.split("<keyed_scene>")[1].split("</keyed_scene>")[0]
    assert "&" not in inner.replace("&amp;", "").replace("&lt;", "").replace("&gt;", "")


# ── SceneSetup defaults check (in-scope rule fix) ─────────


def test_scene_setup_requires_scene_type():
    """SceneSetup.scene_type has no domain-safe default; construction without
    it raises. Step 4 in-scope fix: was a Python default, now required."""
    with pytest.raises(TypeError):
        SceneSetup()  # type: ignore[call-arg]


def test_scene_setup_keyed_serialization_roundtrip():
    setup = SceneSetup(scene_type="keyed", narrative_hint="Beat hint")
    restored = SceneSetup.from_dict(setup.to_dict())
    assert restored.scene_type == "keyed"
    assert restored.narrative_hint == "Beat hint"
    assert restored.chaos_roll == 0
