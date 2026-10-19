from __future__ import annotations

import pytest

from straightjacket.engine.crafters.adventure_crafter import PlotPointHit, TurningPoint
from straightjacket.engine.crafters.turning_point_spawns import spawn_clocks_for_turning_point
from straightjacket.engine.gamemaster.clocks import resolve_clock_fill
from straightjacket.engine.gamemaster.random_events import spawn_clock_from_random_event
from straightjacket.engine.models import KeyedScene, RandomEvent
from tests._helpers import make_clock, make_game_state, make_keyed_scene, make_progress_track


def _re(focus: str, target_id: str = "", target: str = "") -> RandomEvent:
    return RandomEvent(
        focus=focus,
        target=target,
        target_id=target_id,
        meaning_action="Storm",
        meaning_subject="Approaches",
        source="test",
    )


def _tp(plot_point_names: list[str]) -> TurningPoint:
    return TurningPoint(
        plot_points=[PlotPointHit(theme="action", name=name, special_range=None) for name in plot_point_names],
        plotline="Plotline 1",
        opens_plotline=True,
        concludes_plotline=False,
    )


def test_random_event_clock_spawns_for_mapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative")

    spawn_clock_from_random_event(g, event)

    [clock] = g.world.clocks
    assert clock.clock_type == "threat"
    assert clock.segments == 6
    assert clock.creation_source.startswith("random_event:pc_negative")
    assert clock.owner_kind == "world"
    assert clock.owner_id is None
    assert clock.name == "Storm Approaches"


def test_random_event_clock_skips_unmapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_action")

    spawn_clock_from_random_event(g, event)

    assert g.world.clocks == []


def test_random_event_clock_progress_type_for_thread_moves(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("move_toward_thread", target_id="thread_1", target="The Pact")

    spawn_clock_from_random_event(g, event)

    [clock] = g.world.clocks
    assert clock.clock_type == "progress"


def test_random_event_clock_dedups_same_target(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative", target_id="threat_1")

    spawn_clock_from_random_event(g, event)
    spawn_clock_from_random_event(g, event)

    assert len(g.world.clocks) == 1


def test_ac_clock_spawns_for_mapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Time Limit"])

    spawn_clocks_for_turning_point(g, tp)

    [clock] = g.world.clocks
    assert clock.name == "Time Limit"
    assert clock.clock_type == "threat"
    assert clock.creation_source == "ac:Time Limit"
    assert clock.owner_kind == "world"


def test_ac_clock_skips_unmapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy"])

    spawn_clocks_for_turning_point(g, tp)

    assert g.world.clocks == []


def test_ac_clock_dedups_same_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Time Limit"])

    spawn_clocks_for_turning_point(g, tp)
    spawn_clocks_for_turning_point(g, tp)

    assert len(g.world.clocks) == 1


def test_emergent_clock_cap_shared_across_sources(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Time Limit", "A Needed Resource Runs Out", "Impending Doom"])
    spawn_clocks_for_turning_point(g, tp)
    assert len(g.world.clocks) == 3

    spawn_clock_from_random_event(g, _re("pc_negative", target_id="extra"))
    assert len(g.world.clocks) == 4

    spawn_clock_from_random_event(g, _re("pc_negative", target_id="overflow"))
    assert len(g.world.clocks) == 4


def test_spawned_clock_attaches_keyed_scenes(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    spawn_clock_from_random_event(g, _re("pc_negative"))

    assert any(isinstance(ks, KeyedScene) and ks.source.startswith("clock:") for ks in g.narrative.keyed_scenes)


def test_fill_handler_emits_tag_when_no_keyed_scene_attached(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    clock = make_clock(name="Storm", clock_type="threat", segments=4, filled=4)
    g.world.clocks.append(clock)

    fill = resolve_clock_fill(g, clock)

    assert fill is not None
    assert fill.clock_name == "Storm"
    assert fill.clock_type == "threat"
    assert "Storm" in fill.tag_text


def test_fill_handler_suppressed_when_keyed_scene_attached(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    clock = make_clock(name="Storm", clock_type="threat", segments=4, filled=4)
    g.world.clocks.append(clock)
    g.narrative.keyed_scenes.append(
        make_keyed_scene(
            id="ks_1",
            trigger_type="clock_fills",
            trigger_value="Storm:4",
            priority=5,
            narrative_hint="Storm lands",
            source="clock:Storm:4",
        )
    )

    fill = resolve_clock_fill(g, clock)

    assert fill is None


def test_fill_handler_progress_clock_completes_linked_track(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    track = make_progress_track(id="track_1", name="The Bridge", track_type="vow", rank="dangerous")
    track.status = "active"
    g.progress_tracks.append(track)
    clock = make_clock(name="The Bridge", clock_type="progress", segments=4, filled=4)
    g.world.clocks.append(clock)

    fill = resolve_clock_fill(g, clock)

    assert fill is not None
    assert track.status == "completed"


def test_fill_handler_unknown_clock_type_raises(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    clock = make_clock(name="Strange", clock_type="unmapped", segments=4, filled=4)

    with pytest.raises(KeyError, match="unmapped"):
        resolve_clock_fill(g, clock)
