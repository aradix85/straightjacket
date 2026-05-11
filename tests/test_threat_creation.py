from __future__ import annotations

import random as _random


from straightjacket.engine.mechanics.adventure_crafter import (
    PlotPointHit,
    TurningPoint,
    spawn_threats_for_turning_point,
)
from straightjacket.engine.mechanics.scene import check_scene
from straightjacket.engine.mechanics.random_events import (
    spawn_threat_from_random_event,
)
from straightjacket.engine.models import KeyedScene, RandomEvent
from tests._helpers import make_game_state, make_threat


def _re(focus: str, target_id: str = "", target: str = "") -> RandomEvent:
    return RandomEvent(
        focus=focus,
        focus_roll=50,
        target=target,
        target_id=target_id,
        meaning_action="Betray",
        meaning_subject="Faith",
        meaning_table="actions",
        source="test",
    )


def _tp(plot_point_names: list[str]) -> TurningPoint:
    plot_points = [
        PlotPointHit(theme="action", priority=1, roll=50, name=name, special_range=None) for name in plot_point_names
    ]
    return TurningPoint(
        plotline_id="pl_1",
        plotline_was_new=True,
        plot_points=plot_points,
        flips_to_conclusion=False,
    )


def test_random_event_threat_spawns_for_mapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative", target_id="")

    threat = spawn_threat_from_random_event(g, event)

    assert threat is not None
    assert threat.creation_source.startswith("random_event:pc_negative")
    assert threat.rank == "dangerous"
    assert threat.category == "emergent"
    assert threat.linked_vow_id is None
    assert threat.name == "Betray Faith"
    assert threat in g.threats


def test_random_event_threat_skips_unmapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_positive", target_id="npc_kira")

    result = spawn_threat_from_random_event(g, event)

    assert result is None
    assert g.threats == []


def test_random_event_threat_dedup_per_focus_target(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_negative", target_id="npc_kira")

    first = spawn_threat_from_random_event(g, event)
    second = spawn_threat_from_random_event(g, event)

    assert first is not None
    assert second is None
    assert len(g.threats) == 1


def test_random_event_threat_cap_respects_max_threats_per_chapter(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    for n in range(3):
        spawn_threat_from_random_event(g, _re("pc_negative", target_id=f"t_{n}"))

    assert len(g.threats) == 3

    blocked = spawn_threat_from_random_event(g, _re("pc_negative", target_id="t_extra"))
    assert blocked is None
    assert len(g.threats) == 3


def test_ac_threat_spawns_for_mapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy"])

    count = spawn_threats_for_turning_point(g, tp)

    assert count == 1
    assert len(g.threats) == 1
    threat = g.threats[0]
    assert threat.creation_source == "ac:A New Enemy"
    assert threat.rank == "dangerous"
    assert threat.category == "scheming_leader"
    assert threat.linked_vow_id is None
    assert threat.name != ""


def test_ac_threat_skips_unmapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Suspicion", "An Opposing Story"])

    count = spawn_threats_for_turning_point(g, tp)

    assert count == 0
    assert g.threats == []


def test_ac_threat_dedup_skips_same_plot_point_twice(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp1 = _tp(["Hunted"])
    tp2 = _tp(["Hunted"])

    spawn_threats_for_turning_point(g, tp1)
    spawn_threats_for_turning_point(g, tp2)

    assert len(g.threats) == 1


def test_ac_threat_cap_blocks_after_max(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy", "Hidden Threat", "Enemies", "Hunted", "A Problem Returns"])

    count = spawn_threats_for_turning_point(g, tp)

    assert count == 3
    assert len(g.threats) == 3


def test_ac_threat_uses_datasworn_cascade_on_delve(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="delve")
    _random.seed(42)
    tp = _tp(["A New Enemy"])

    spawn_threats_for_turning_point(g, tp)

    assert len(g.threats) == 1
    description = g.threats[0].description
    assert " — " in description, f"Delve cascade expected two steps in description, got {description!r}"


def test_emergent_threats_cap_is_shared_across_ac_and_random_event(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    for n in range(2):
        spawn_threat_from_random_event(g, _re("pc_negative", target_id=f"t_{n}"))

    assert len(g.threats) == 2

    tp = _tp(["A New Enemy", "Hidden Threat"])
    spawn_threats_for_turning_point(g, tp)

    assert len(g.threats) == 3


def test_setup_threat_does_not_count_against_emergent_cap(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.threats.append(make_threat(id="setup_threat_1", name="Setup", creation_source="setup"))
    g.threats.append(make_threat(id="setup_threat_2", name="Setup 2", creation_source="setup"))
    g.threats.append(make_threat(id="setup_threat_3", name="Setup 3", creation_source="setup"))

    threat = spawn_threat_from_random_event(g, _re("pc_negative", target_id="t_new"))

    assert threat is not None
    assert len(g.threats) == 4


def test_keyed_scene_threat_menace_fires_after_spawn(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    spawn_threat_from_random_event(g, _re("pc_negative", target_id="t_1"))
    assert len(g.threats) == 1
    threat = g.threats[0]

    g.narrative.keyed_scenes.append(
        KeyedScene(
            id="ks_test",
            trigger_type="threat_menace_phase",
            trigger_value=f"{threat.name}:1",
            priority=5,
            narrative_hint="The threat sharpens.",
            source="test",
        )
    )

    threat.advance_menace(2)
    assert threat.menace_filled_boxes >= 1

    setup = check_scene(g)
    assert setup.scene_type == "keyed", f"keyed scene did not fire; got {setup.scene_type}"
    assert "sharpens" in setup.narrative_hint.lower() or setup.narrative_hint != ""
