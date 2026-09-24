from __future__ import annotations

from typing import Any

from straightjacket.engine.models import GameState, ProgressTrack

from .coverage import TARGETS


def check_expectations(spec: dict[str, Any]) -> None:
    unknown = [target for target in spec["expect"] if target not in TARGETS]
    if unknown:
        raise ValueError(f"Unknown coverage targets in scenario: {unknown}")


def _set_resources(game: GameState, resources: dict[str, Any]) -> list[str]:
    notes = []
    for name, value in resources.items():
        amount = game.resources.max_momentum if value == "max" else int(value)
        setattr(game.resources, name, amount)
        notes.append(f"{name} {amount}")
    return notes


def _near_story_end(game: GameState) -> str:
    blueprint = game.narrative.story_blueprint
    if blueprint is None or len(blueprint.acts) < 2:
        return "no blueprint with two or more acts, so the story end is not prepared"
    final_end = blueprint.acts[-1].scene_range[1]
    entered = {f"act_{index}" for index in range(len(blueprint.acts) - 1)}
    blueprint.triggered_transitions = sorted(set(blueprint.triggered_transitions) | entered)
    game.narrative.scene_count = final_end - 1
    return f"final act entered, scene {final_end - 1} of {final_end}"


def _start_combat(game: GameState) -> str:
    track = ProgressTrack.new(id="combat_elvira_scenario", name="Scenario fight", track_type="combat", rank="dangerous")
    game.progress_tracks.append(track)
    game.world.combat_position = "in_control"
    return "combat track opened, position in control"


def _nearly_full_clock(game: GameState) -> str:
    open_clocks = [clock for clock in game.world.clocks if not clock.fired]
    if not open_clocks:
        return "no open clock, so the clock is not prepared"
    clock = open_clocks[0]
    clock.filled = clock.segments - 1
    return f"clock '{clock.name}' at {clock.filled} of {clock.segments}"


def prepare_scenario(game: GameState, spec: dict[str, Any]) -> list[str]:
    check_expectations(spec)
    notes: list[str] = []
    if "resources" in spec:
        notes += _set_resources(game, spec["resources"])
    if "story_end" in spec:
        notes.append(_near_story_end(game))
    if "combat" in spec:
        notes.append(_start_combat(game))
    if "clock_nearly_full" in spec:
        notes.append(_nearly_full_clock(game))
    return notes
