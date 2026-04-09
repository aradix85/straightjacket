"""Turn recording: extracts game state into typed TurnRecord after each turn."""

from __future__ import annotations

from straightjacket.engine.ai.provider_base import drain_token_log
from straightjacket.engine.models import GameState, RollResult
from straightjacket.engine.story_state import get_current_act

from .models import (
    ClockSnapshot,
    EngineLogRecord,
    NpcSnapshot,
    RollRecord,
    StateSnapshot,
    StoryArcRecord,
    TurnRecord,
    ValidatorRecord,
)


def record_turn(
    game: GameState,
    turn: int,
    action: str,
    narration: str,
    roll: RollResult | None,
) -> TurnRecord:
    """Snapshot the current game state into a TurnRecord."""
    rec = TurnRecord(
        turn=turn,
        chapter=game.campaign.chapter_number,
        scene=game.narrative.scene_count,
        location=game.world.current_location,
        action=action,
        narration=narration,
        narration_excerpt=narration.replace("\n", " ")[:300],
    )

    if roll:
        rec.roll = RollRecord(
            stat=roll.stat_name,
            d1=roll.d1,
            d2=roll.d2,
            total=roll.action_score,
            c1=roll.c1,
            c2=roll.c2,
            result=roll.result,
            match=roll.match,
        )

    rec.state_after = _snapshot_state(game)
    rec.npcs = _snapshot_npcs(game)
    rec.clocks = _snapshot_clocks(game)
    rec.engine_log = _snapshot_engine_log(game)
    rec.validator = _snapshot_validator(game)
    rec.story_arc = _snapshot_story_arc(game)
    rec.director_guidance = _snapshot_director_guidance(game)
    rec.token_usage = drain_token_log()

    return rec


def _snapshot_state(game: GameState) -> StateSnapshot:
    res = game.resources
    return StateSnapshot(
        health=res.health,
        spirit=res.spirit,
        supply=res.supply,
        momentum=res.momentum,
        chaos=game.world.chaos_factor,
        scene=game.narrative.scene_count,
        location=game.world.current_location,
        time_of_day=game.world.time_of_day,
        scene_context=game.world.current_scene_context,
        active_threads=len([t for t in game.narrative.threads if t.active]),
        active_characters=len([c for c in game.narrative.characters_list if c.active]),
        active_vow_tracks=len(game.vow_tracks),
    )


def _snapshot_npcs(game: GameState) -> list[NpcSnapshot]:
    return [
        NpcSnapshot(
            id=n.id,
            name=n.name,
            status=n.status,
            disposition=n.disposition,
            bond=n.bond,
            agenda=n.agenda,
            instinct=n.instinct,
            arc=n.arc,
            memory_count=len(n.memory),
            last_memory=(n.memory[-1].event[:100] if n.memory else ""),
            last_location=n.last_location,
            aliases=list(n.aliases),
        )
        for n in game.npcs
        if n.status in ("active", "background")
    ]


def _snapshot_clocks(game: GameState) -> list[ClockSnapshot]:
    return [
        ClockSnapshot(
            name=c.name,
            clock_type=c.clock_type,
            filled=c.filled,
            segments=c.segments,
            owner=c.owner,
            fired=c.fired,
        )
        for c in game.world.clocks
    ]


def _snapshot_engine_log(game: GameState) -> EngineLogRecord | None:
    if not game.narrative.session_log:
        return None
    sl = game.narrative.session_log[-1]
    return EngineLogRecord(
        summary=sl.rich_summary or sl.summary,
        move=sl.move,
        chaos_interrupt=sl.chaos_interrupt,
        director_trigger=sl.director_trigger,
        consequences=list(sl.consequences),
        clock_events=[e.to_dict() for e in sl.clock_events],
        position=sl.position,
        effect=sl.effect,
        npc_activation=dict(sl.npc_activation),
    )


def _snapshot_validator(game: GameState) -> ValidatorRecord | None:
    if not game.narrative.session_log:
        return None
    val = game.narrative.session_log[-1].validator
    if not val:
        return None
    # Extract per-attempt violation counts from checks trail
    checks = val.get("checks", [])
    attempt_violations = [len(c.get("violations", [])) for c in checks]
    # Detect if best-of selection picked an earlier attempt
    picked = -1
    if not val.get("passed", True) and len(attempt_violations) >= 2:
        final_v = attempt_violations[-1]
        best_v = min(attempt_violations)
        if best_v < final_v:
            picked = attempt_violations.index(best_v)
    return ValidatorRecord(
        passed=val.get("passed", True),
        retries=val.get("retries", 0),
        violations=val.get("violations", []),
        attempt_violations=attempt_violations,
        picked_attempt=picked,
    )


def _snapshot_story_arc(game: GameState) -> StoryArcRecord | None:
    bp = game.narrative.story_blueprint
    if not bp or not bp.acts:
        return None
    act = get_current_act(game)
    return StoryArcRecord(
        phase=act.phase,
        title=act.title,
        goal=act.goal,
        mood=act.mood,
        story_complete=bp.story_complete,
    )


def _snapshot_director_guidance(game: GameState) -> dict:
    dg = game.narrative.director_guidance
    if not dg:
        return {}
    return {
        "narrator_guidance": dg.narrator_guidance,
        "pacing": dg.pacing,
        "arc_notes": dg.arc_notes,
    }
