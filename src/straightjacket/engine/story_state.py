#!/usr/bin/env python3
"""Story state queries: act tracking, revelations, story completion."""

from __future__ import annotations

from .engine_loader import eng
from .models import CurrentAct, GameState, Revelation


def _default_scene_range() -> list[int]:
    """Fallback scene range from engine.yaml when an act has no explicit range."""
    return list(eng().scene_range_default)


def get_current_act(game: GameState) -> CurrentAct:
    """Determine which act the story is in based on transition triggers and scene count."""
    bp = game.narrative.story_blueprint
    if not bp or not bp.acts:
        return CurrentAct(phase="setup", title="?", goal="?", mood="mysterious")

    if bp.story_complete and game.campaign.epilogue_dismissed:
        last = bp.acts[-1]
        return CurrentAct(
            phase="aftermath",
            title="Aftermath",
            goal="Open-ended play",
            mood=last.mood,
            act_number=len(bp.acts),
            total_acts=len(bp.acts),
            progress="late",
        )

    acts = bp.acts
    scene = game.narrative.scene_count
    triggered = set(bp.triggered_transitions)

    current = acts[0]
    act_number = 1

    for i, act in enumerate(acts[:-1]):
        sr = act.scene_range or _default_scene_range()
        act_id = f"act_{i}"

        if act_id in triggered or scene > sr[1]:
            if i + 1 < len(acts):
                current = acts[i + 1]
                act_number = i + 2
        else:
            current = act
            act_number = i + 1
            break

    sr = current.scene_range or _default_scene_range()
    act_len = max(sr[1] - sr[0] + 1, 1)
    scenes_in = scene - sr[0] + 1
    if scenes_in <= act_len * 0.3:
        progress = "early"
    elif scenes_in <= act_len * 0.7:
        progress = "mid"
    else:
        progress = "late"

    approaching_end = act_number == len(acts) and progress in ("mid", "late")

    return CurrentAct(
        phase=current.phase,
        title=current.title,
        goal=current.goal,
        scene_range=list(current.scene_range),
        mood=current.mood,
        transition_trigger=current.transition_trigger,
        act_number=act_number,
        total_acts=len(acts),
        progress=progress,
        approaching_end=approaching_end,
    )


def get_pending_revelations(game: GameState) -> list[Revelation]:
    """Get revelations that are ready to be introduced but haven't been yet."""
    bp = game.narrative.story_blueprint
    if not bp or not bp.revelations:
        return []
    revealed = set(bp.revealed)
    return [
        rev for rev in bp.revelations if rev.id not in revealed and game.narrative.scene_count >= rev.earliest_scene
    ]


def mark_revelation_used(game: GameState, rev_id: str) -> None:
    """Mark a revelation as revealed."""
    bp = game.narrative.story_blueprint
    if bp and rev_id not in bp.revealed:
        bp.revealed.append(rev_id)
