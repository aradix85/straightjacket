from __future__ import annotations

import random as _random

import pytest

from straightjacket.engine.crafters.adventure_crafter import PlotPointHit, TurningPoint, spawn_dangers_for_turning_point
from straightjacket.engine.gamemaster.random_events import spawn_danger_from_random_event
from straightjacket.engine.gamemaster.scene import check_scene
from straightjacket.engine.models import KeyedScene, RandomEvent
from tests._helpers import make_game_state, make_threat


def _re(focus: str, target_id: str = "", target: str = "") -> RandomEvent:
    return RandomEvent(
        focus=focus,
        target=target,
        target_id=target_id,
        meaning_action="Betray",
        meaning_subject="Faith",
        source="test",
    )


def _tp(plot_point_names: list[str]) -> TurningPoint:
    return TurningPoint(
        plot_points=[PlotPointHit(theme="action", name=name, special_range=None) for name in plot_point_names],
        plotline="Plotline 1",
        opens_plotline=True,
        concludes_plotline=False,
    )


def test_random_event_threat_spawns_for_mapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative", target_id="")

    spawn_danger_from_random_event(g, event)

    [threat] = g.threats
    assert threat.creation_source.startswith("random_event:pc_negative")
    assert threat.rank == "dangerous"
    assert threat.category == "emergent"
    assert threat.linked_vow_id is None
    assert threat.name == "Betray Faith"


def test_random_event_threat_skips_unmapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_positive", target_id="npc_kira")

    spawn_danger_from_random_event(g, event)

    assert g.threats == []


def test_random_event_threat_dedup_per_focus_target(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_negative", target_id="npc_kira")

    spawn_danger_from_random_event(g, event)
    spawn_danger_from_random_event(g, event)

    assert len(g.threats) == 1


def test_random_event_threat_respects_the_threat_cap(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    for n in range(3):
        spawn_danger_from_random_event(g, _re("pc_negative", target_id=f"t_{n}"))

    assert len(g.threats) == 3

    spawn_danger_from_random_event(g, _re("pc_negative", target_id="t_extra"))
    assert len(g.threats) == 3


def test_ac_threat_spawns_for_mapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy"])

    spawn_dangers_for_turning_point(g, tp)

    [threat] = g.threats
    assert threat.creation_source == "ac:A New Enemy"
    assert threat.rank == "dangerous"
    assert threat.category == "scheming_leader"
    assert threat.linked_vow_id is None
    assert threat.name != ""


def test_ac_threat_skips_unmapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Suspicion", "An Opposing Story"])

    spawn_dangers_for_turning_point(g, tp)

    assert g.threats == []


def test_ac_threat_dedup_skips_same_plot_point_twice(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp1 = _tp(["Hunted"])
    tp2 = _tp(["Hunted"])

    spawn_dangers_for_turning_point(g, tp1)
    spawn_dangers_for_turning_point(g, tp2)

    assert len(g.threats) == 1


def test_ac_threat_cap_blocks_after_max(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy", "Hidden Threat", "Enemies", "Hunted", "A Problem Returns"])

    spawn_dangers_for_turning_point(g, tp)

    assert len(g.threats) == 3


def test_ac_threat_uses_datasworn_cascade_on_delve(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="delve")
    _random.seed(42)
    tp = _tp(["A New Enemy"])

    spawn_dangers_for_turning_point(g, tp)

    assert len(g.threats) == 1
    description = g.threats[0].description
    assert " — " in description, f"Delve cascade expected two steps in description, got {description!r}"


def test_a_delve_threat_takes_the_category_its_cascade_rolled(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests._helpers import fix_dice

    fix_dice(monkeypatch, 45, 1)
    g = make_game_state(player_name="Hero", setting_id="delve")
    spawn_dangers_for_turning_point(g, _tp(["A New Enemy"]))
    assert g.threats[0].category == "rampaging_creature"


def test_a_cascade_row_that_rolls_twice_gives_both_results(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests._helpers import fix_dice

    fix_dice(monkeypatch, 95, 5, 65, 1)
    g = make_game_state(player_name="Hero", setting_id="delve")
    spawn_dangers_for_turning_point(g, _tp(["A New Enemy"]))
    [threat] = g.threats
    assert threat.category == "burgeoning_conflict"
    assert "Roll twice" not in threat.name
    assert "Scheming Leader" in threat.description


def test_emergent_threats_cap_is_shared_across_ac_and_random_event(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    for n in range(2):
        spawn_danger_from_random_event(g, _re("pc_negative", target_id=f"t_{n}"))

    assert len(g.threats) == 2

    tp = _tp(["A New Enemy", "Hidden Threat"])
    spawn_dangers_for_turning_point(g, tp)

    assert len(g.threats) == 3


def test_setup_threat_does_not_count_against_emergent_cap(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    g.threats.append(make_threat(id="setup_threat_1", name="Setup", creation_source="setup"))
    g.threats.append(make_threat(id="setup_threat_2", name="Setup 2", creation_source="setup"))
    g.threats.append(make_threat(id="setup_threat_3", name="Setup 3", creation_source="setup"))

    spawn_danger_from_random_event(g, _re("pc_negative", target_id="t_new"))

    assert len(g.threats) == 4


def test_keyed_scene_threat_menace_fires_after_spawn(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    spawn_danger_from_random_event(g, _re("pc_negative", target_id="t_1"))
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
