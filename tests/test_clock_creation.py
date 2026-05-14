from __future__ import annotations

from straightjacket.engine.mechanics.adventure_crafter import (
    PlotPointHit,
    TurningPoint,
    spawn_clocks_for_turning_point,
)
from straightjacket.engine.mechanics.clock_consequences import resolve_clock_fill
from straightjacket.engine.mechanics.random_events import spawn_clock_from_random_event
from straightjacket.engine.models import KeyedScene, RandomEvent
from tests._helpers import make_clock, make_game_state, make_progress_track


def _re(focus: str, target_id: str = "", target: str = "") -> RandomEvent:
    return RandomEvent(
        focus=focus,
        focus_roll=50,
        target=target,
        target_id=target_id,
        meaning_action="Storm",
        meaning_subject="Approaches",
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


def test_random_event_clock_spawns_for_mapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative")

    clock = spawn_clock_from_random_event(g, event)

    assert clock is not None
    assert clock.clock_type == "threat"
    assert clock.segments == 6
    assert clock.creation_source.startswith("random_event:pc_negative")
    assert clock.owner_kind == "world"
    assert clock.owner_id is None
    assert clock.name == "Storm Approaches"
    assert clock in g.world.clocks


def test_random_event_clock_skips_unmapped_focus(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("npc_action")

    clock = spawn_clock_from_random_event(g, event)

    assert clock is None
    assert g.world.clocks == []


def test_random_event_clock_progress_type_for_thread_moves(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("move_toward_thread", target_id="thread_1", target="The Pact")

    clock = spawn_clock_from_random_event(g, event)

    assert clock is not None
    assert clock.clock_type == "progress"


def test_random_event_clock_dedups_same_target(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    event = _re("pc_negative", target_id="threat_1")

    first = spawn_clock_from_random_event(g, event)
    second = spawn_clock_from_random_event(g, event)

    assert first is not None
    assert second is None
    assert len(g.world.clocks) == 1


def test_ac_clock_spawns_for_mapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["Time Limit"])

    spawned = spawn_clocks_for_turning_point(g, tp)

    assert spawned == 1
    clock = g.world.clocks[0]
    assert clock.name == "Time Limit"
    assert clock.clock_type == "threat"
    assert clock.creation_source == "ac:Time Limit"
    assert clock.owner_kind == "world"


def test_ac_clock_skips_unmapped_plot_point(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    tp = _tp(["A New Enemy"])

    spawned = spawn_clocks_for_turning_point(g, tp)

    assert spawned == 0
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

    rejected = spawn_clock_from_random_event(g, _re("pc_negative", target_id="overflow"))
    assert rejected is None
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
        KeyedScene(
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
    assert fill.track_completed
    assert track.status == "completed"


def test_fill_handler_unknown_clock_type_returns_none(load_engine: None) -> None:
    g = make_game_state(player_name="Hero", setting_id="starforged")
    clock = make_clock(name="Strange", clock_type="unmapped", segments=4, filled=4)

    fill = resolve_clock_fill(g, clock)

    assert fill is None
