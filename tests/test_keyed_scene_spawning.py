from __future__ import annotations

import random

import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.mechanics import evaluate_keyed_scenes
from straightjacket.engine.mechanics.adventure_crafter import (
    PlotPointHit,
    TurningPoint,
    spawn_keyed_scenes_for_turning_point,
)
from straightjacket.engine.mechanics.keyed_scenes import spawn_keyed_scenes_for_clock
from straightjacket.engine.mechanics.random_events import (
    generate_random_event,
    spawn_keyed_scene_from_random_event,
)
from straightjacket.engine.models import (
    ClockData,
    GameState,
    KeyedScene,
    NarrativeState,
    ProgressTrack,
)
from tests._helpers import (
    make_clock,
    make_game_state,
    make_npc,
    make_random_event,
    make_threat,
    make_world_state,
)


def _seed_game(**world_kwargs) -> GameState:
    return make_game_state(world=make_world_state(**world_kwargs))


def _bond_track(npc_id: str, filled_boxes: int) -> ProgressTrack:
    return ProgressTrack(
        id=f"connection_{npc_id}",
        name=f"Connection: {npc_id}",
        track_type="connection",
        rank="dangerous",
        max_ticks=40,
        ticks=filled_boxes * 4,
        status="active",
    )


def _seed_bond(
    game: GameState, npc_id: str, filled_boxes: int, *, name: str = "", disposition: str = "neutral"
) -> None:
    game.npcs.append(make_npc(id=npc_id, name=name or npc_id, disposition=disposition))
    game.progress_tracks.append(_bond_track(npc_id, filled_boxes))


def _ks_pattern(trigger_type: str, trigger_value: str, **kwargs) -> KeyedScene:
    kwargs.setdefault("id", "ks_test")
    kwargs.setdefault("priority", 5)
    kwargs.setdefault("narrative_hint", "test hint")
    return KeyedScene(trigger_type=trigger_type, trigger_value=trigger_value, **kwargs)


def test_bond_threshold_any_pattern_validates():
    KeyedScene(id="ks", trigger_type="bond_threshold", trigger_value="any:5", priority=1, narrative_hint="")


def test_bond_threshold_disposition_pattern_validates_for_each_disposition():
    for disp in eng().enums.dispositions:
        KeyedScene(
            id=f"ks_{disp}",
            trigger_type="bond_threshold",
            trigger_value=f"disposition_{disp}:4",
            priority=1,
            narrative_hint="",
        )


def test_bond_threshold_unknown_disposition_raises():
    with pytest.raises(ValueError, match="unknown disposition"):
        KeyedScene(
            id="ks_bad",
            trigger_type="bond_threshold",
            trigger_value="disposition_alien:4",
            priority=1,
            narrative_hint="",
        )


def test_bond_threshold_malformed_trigger_value_raises():
    with pytest.raises(ValueError, match="trigger_value must be"):
        KeyedScene(id="ks_bad", trigger_type="bond_threshold", trigger_value="malformed", priority=1, narrative_hint="")


def test_bond_threshold_non_integer_threshold_raises():
    with pytest.raises(ValueError, match="must be an integer"):
        KeyedScene(
            id="ks_bad", trigger_type="bond_threshold", trigger_value="any:not_a_number", priority=1, narrative_hint=""
        )


def test_threat_menace_phase_any_pattern_validates():
    KeyedScene(id="ks", trigger_type="threat_menace_phase", trigger_value="any:3", priority=1, narrative_hint="")


def test_clock_fills_any_pattern_validates():
    KeyedScene(id="ks", trigger_type="clock_fills", trigger_value="any:3", priority=1, narrative_hint="")


def test_bond_threshold_any_fires_when_some_npc_meets_threshold():
    game = _seed_game()
    _seed_bond(game, "npc_a", filled_boxes=2)
    _seed_bond(game, "npc_b", filled_boxes=6)
    scene = _ks_pattern("bond_threshold", "any:5", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired is scene
    assert fired.bound_entity_id == "npc_b"


def test_bond_threshold_any_does_not_fire_when_no_npc_meets_threshold():
    game = _seed_game()
    _seed_bond(game, "npc_a", filled_boxes=2)
    _seed_bond(game, "npc_b", filled_boxes=3)
    game.narrative.keyed_scenes.append(_ks_pattern("bond_threshold", "any:5", id="ks_a"))
    assert evaluate_keyed_scenes(game) is None


def test_bond_threshold_any_picks_highest_bond():
    game = _seed_game()
    _seed_bond(game, "npc_low", filled_boxes=5)
    _seed_bond(game, "npc_mid", filled_boxes=6)
    _seed_bond(game, "npc_high", filled_boxes=8)
    scene = _ks_pattern("bond_threshold", "any:5", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired.bound_entity_id == "npc_high"


def test_bond_threshold_any_excludes_already_bound_npcs():
    game = _seed_game()
    _seed_bond(game, "npc_a", filled_boxes=8)
    _seed_bond(game, "npc_b", filled_boxes=6)
    earlier_scene = _ks_pattern("bond_threshold", "any:5", id="ks_earlier", priority=10)
    earlier_scene.bound_entity_id = "npc_a"
    later_scene = _ks_pattern("bond_threshold", "any:5", id="ks_later", priority=1)
    game.narrative.keyed_scenes.extend([earlier_scene, later_scene])

    bond_track_for_a = next(t for t in game.progress_tracks if t.id == "connection_npc_a")
    bond_track_for_a.ticks = 0

    fired = evaluate_keyed_scenes(game)
    assert fired is later_scene
    assert fired.bound_entity_id == "npc_b"


def test_bond_threshold_disposition_filter_only_matches_npcs_with_that_disposition():
    game = _seed_game()
    _seed_bond(game, "friend", filled_boxes=8, disposition="friendly")
    _seed_bond(game, "neutral_one", filled_boxes=9, disposition="neutral")
    scene = _ks_pattern("bond_threshold", "disposition_friendly:5", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired is scene
    assert fired.bound_entity_id == "friend"


def test_bond_threshold_disposition_filter_does_not_fire_without_matching_disposition():
    game = _seed_game()
    _seed_bond(game, "neutral_one", filled_boxes=9, disposition="neutral")
    game.narrative.keyed_scenes.append(_ks_pattern("bond_threshold", "disposition_friendly:5", id="ks_a"))
    assert evaluate_keyed_scenes(game) is None


def test_bond_threshold_concrete_id_still_works():
    game = _seed_game()
    _seed_bond(game, "npc_kira", filled_boxes=7)
    scene = _ks_pattern("bond_threshold", "npc_kira:5", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired is scene
    assert fired.bound_entity_id == "npc_kira"


def test_threat_menace_phase_any_fires_when_some_threat_meets_threshold():
    game = _seed_game()
    weak = make_threat(id="t_weak", name="Weak Threat")
    strong = make_threat(id="t_strong", name="Strong Threat")
    strong.menace_ticks = 16
    weak.menace_ticks = 4
    game.threats.extend([weak, strong])
    scene = _ks_pattern("threat_menace_phase", "any:3", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired is scene
    assert fired.bound_entity_id == "t_strong"


def test_threat_menace_phase_any_picks_highest_menace():
    game = _seed_game()
    a = make_threat(id="t_a", name="A")
    a.menace_ticks = 12
    b = make_threat(id="t_b", name="B")
    b.menace_ticks = 20
    c = make_threat(id="t_c", name="C")
    c.menace_ticks = 16
    game.threats.extend([a, b, c])
    scene = _ks_pattern("threat_menace_phase", "any:3", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired.bound_entity_id == "t_b"


def test_clock_fills_any_fires_when_some_clock_meets_threshold():
    game = _seed_game()
    game.world.clocks.append(make_clock(name="Slow Clock", segments=6, filled=1))
    game.world.clocks.append(make_clock(name="Fast Clock", segments=6, filled=4))
    scene = _ks_pattern("clock_fills", "any:3", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired is scene
    assert fired.bound_entity_id == "clock:Fast Clock"


def test_clock_fills_any_picks_highest_filled():
    game = _seed_game()
    game.world.clocks.append(make_clock(name="A", segments=6, filled=3))
    game.world.clocks.append(make_clock(name="B", segments=6, filled=5))
    game.world.clocks.append(make_clock(name="C", segments=6, filled=4))
    scene = _ks_pattern("clock_fills", "any:3", id="ks_a")
    game.narrative.keyed_scenes.append(scene)
    fired = evaluate_keyed_scenes(game)
    assert fired.bound_entity_id == "clock:B"


def _turning_point_with_plot_points(*plot_point_names: str) -> TurningPoint:
    hits = [PlotPointHit(theme="action", priority=1, roll=50, name=n, special_range=None) for n in plot_point_names]
    return TurningPoint(
        plotline_id="pl_1",
        plotline_was_new=False,
        plot_points=hits,
        flips_to_conclusion=False,
    )


def test_ac_spawner_emits_keyed_scene_for_mapped_plot_point():
    narrative = NarrativeState()
    tp = _turning_point_with_plot_points("Betrayal!")
    spawned = spawn_keyed_scenes_for_turning_point(narrative, tp)
    assert spawned == 1
    assert len(narrative.keyed_scenes) == 1
    scene = narrative.keyed_scenes[0]
    assert scene.trigger_type == "bond_threshold"
    assert scene.trigger_value == "any:7"
    assert scene.source == "ac:Betrayal!"


def test_ac_spawner_skips_unmapped_plot_points():
    narrative = NarrativeState()
    tp = _turning_point_with_plot_points("A Common Social Gathering", "Dense Urban Setting")
    spawned = spawn_keyed_scenes_for_turning_point(narrative, tp)
    assert spawned == 0
    assert narrative.keyed_scenes == []


def test_ac_spawner_dedups_same_plot_point_within_chapter():
    narrative = NarrativeState()
    tp1 = _turning_point_with_plot_points("Betrayal!")
    tp2 = _turning_point_with_plot_points("Betrayal!")
    spawn_keyed_scenes_for_turning_point(narrative, tp1)
    spawn_keyed_scenes_for_turning_point(narrative, tp2)
    assert len(narrative.keyed_scenes) == 1


def test_ac_spawner_respects_max_keyed_scenes_per_chapter_cap():
    narrative = NarrativeState()
    cap = eng().adventure_crafter.max_keyed_scenes_per_chapter
    mappable_names = list(eng().adventure_crafter.keyed_scene_mapping.keys())
    assert len(mappable_names) > cap
    over_cap = mappable_names[: cap + 2]
    tp = _turning_point_with_plot_points(*over_cap)
    spawn_keyed_scenes_for_turning_point(narrative, tp)
    assert len(narrative.keyed_scenes) == cap


def test_ac_spawner_assigns_unique_ids():
    narrative = NarrativeState()
    tp = _turning_point_with_plot_points("Betrayal!", "Liar!", "Hidden Agenda")
    spawn_keyed_scenes_for_turning_point(narrative, tp)
    ids = {ks.id for ks in narrative.keyed_scenes}
    assert len(ids) == len(narrative.keyed_scenes)


def test_ac_spawner_skips_special_range_plot_points():
    narrative = NarrativeState()
    hit = PlotPointHit(theme="action", priority=1, roll=5, name="Conclusion", special_range="conclusion")
    tp = TurningPoint(plotline_id="pl_1", plotline_was_new=False, plot_points=[hit], flips_to_conclusion=False)
    spawn_keyed_scenes_for_turning_point(narrative, tp)
    assert narrative.keyed_scenes == []


def test_random_event_spawner_creates_concrete_bond_keyed_scene_for_npc_focus():
    game = _seed_game()
    _seed_bond(game, "npc_kira", filled_boxes=0, name="Kira")
    event = make_random_event(focus="npc_action", target="Kira", target_id="npc_kira")
    spawn_keyed_scene_from_random_event(game, event)
    assert len(game.narrative.keyed_scenes) == 1
    scene = game.narrative.keyed_scenes[0]
    assert scene.trigger_type == "bond_threshold"
    assert scene.trigger_value == "npc_kira:4"
    assert scene.source == "random_event:npc_action:npc_kira"


def test_random_event_spawner_creates_concrete_threat_keyed_scene_for_pc_negative():
    game = _seed_game()
    threat = make_threat(id="t_pirates", name="The Pirates")
    game.threats.append(threat)
    event = make_random_event(focus="pc_negative", target="The Pirates", target_id="t_pirates")
    spawn_keyed_scene_from_random_event(game, event)
    assert len(game.narrative.keyed_scenes) == 1
    scene = game.narrative.keyed_scenes[0]
    assert scene.trigger_type == "threat_menace_phase"
    assert scene.trigger_value == "The Pirates:3"


def test_random_event_spawner_skips_focus_without_mapping():
    game = _seed_game()
    event = make_random_event(focus="remote_event", target="", target_id="")
    spawn_keyed_scene_from_random_event(game, event)
    assert game.narrative.keyed_scenes == []


def test_random_event_spawner_skips_event_without_target_id():
    game = _seed_game()
    event = make_random_event(focus="npc_action", target="", target_id="")
    spawn_keyed_scene_from_random_event(game, event)
    assert game.narrative.keyed_scenes == []


def test_random_event_spawner_dedups_same_focus_target_pair():
    game = _seed_game()
    _seed_bond(game, "npc_kira", filled_boxes=0, name="Kira")
    event_one = make_random_event(focus="npc_action", target="Kira", target_id="npc_kira")
    event_two = make_random_event(focus="npc_action", target="Kira", target_id="npc_kira")
    spawn_keyed_scene_from_random_event(game, event_one)
    spawn_keyed_scene_from_random_event(game, event_two)
    assert len(game.narrative.keyed_scenes) == 1


def test_generate_random_event_invokes_spawner():
    from straightjacket.engine.models_story import CharacterListEntry

    game = _seed_game()
    _seed_bond(game, "npc_kira", filled_boxes=0, name="Kira")
    game.narrative.characters_list.append(
        CharacterListEntry(id="npc_kira", name="Kira", entry_type="character", weight=3, active=True)
    )
    random.seed(42)
    pre_count = len(game.narrative.keyed_scenes)
    generate_random_event(game)
    assert len(game.narrative.keyed_scenes) >= pre_count


def test_clock_spawner_emits_keyed_scenes_per_fraction_for_threat_clock():
    narrative = NarrativeState()
    clock = ClockData(
        name="The Storm Approaches",
        clock_type="threat",
        segments=6,
        filled=0,
        trigger_description="",
        owner="",
    )
    spawned = spawn_keyed_scenes_for_clock(narrative, clock)
    assert spawned == 2
    trigger_values = sorted(ks.trigger_value for ks in narrative.keyed_scenes)
    assert trigger_values == ["The Storm Approaches:3", "The Storm Approaches:6"]
    for ks in narrative.keyed_scenes:
        assert ks.trigger_type == "clock_fills"
        assert ks.source.startswith("clock:The Storm Approaches:")


def test_clock_spawner_progress_clock_only_emits_full():
    narrative = NarrativeState()
    clock = ClockData(
        name="The Bridge",
        clock_type="progress",
        segments=8,
        filled=0,
        trigger_description="",
        owner="",
    )
    spawned = spawn_keyed_scenes_for_clock(narrative, clock)
    assert spawned == 1
    assert narrative.keyed_scenes[0].trigger_value == "The Bridge:8"


def test_clock_spawner_renders_clock_name_into_narrative_hint():
    narrative = NarrativeState()
    clock = ClockData(
        name="De Hertog onthult zijn plan",
        clock_type="threat",
        segments=4,
        filled=0,
        trigger_description="",
        owner="",
    )
    spawn_keyed_scenes_for_clock(narrative, clock)
    for ks in narrative.keyed_scenes:
        assert "De Hertog onthult zijn plan" in ks.narrative_hint


def test_clock_spawner_dedups_same_clock_threshold_on_repeat_calls():
    narrative = NarrativeState()
    clock = ClockData(
        name="Repeat Clock",
        clock_type="threat",
        segments=6,
        filled=0,
        trigger_description="",
        owner="",
    )
    spawn_keyed_scenes_for_clock(narrative, clock)
    spawn_keyed_scenes_for_clock(narrative, clock)
    assert len(narrative.keyed_scenes) == 2


def test_ac_spawned_pattern_scene_fires_when_state_meets_pattern():
    game = _seed_game()
    _seed_bond(game, "npc_a", filled_boxes=8, name="Alice")
    tp = _turning_point_with_plot_points("Betrayal!")
    spawn_keyed_scenes_for_turning_point(game.narrative, tp)
    fired = evaluate_keyed_scenes(game)
    assert fired is not None
    assert fired.bound_entity_id == "npc_a"
    assert fired.source == "ac:Betrayal!"


def test_clock_spawned_scene_fires_when_clock_fills():
    game = _seed_game()
    clock = ClockData(
        name="Doom",
        clock_type="threat",
        segments=6,
        filled=6,
        trigger_description="",
        owner="",
    )
    game.world.clocks.append(clock)
    spawn_keyed_scenes_for_clock(game.narrative, clock)
    fired = evaluate_keyed_scenes(game)
    assert fired is not None
    assert fired.trigger_type == "clock_fills"
