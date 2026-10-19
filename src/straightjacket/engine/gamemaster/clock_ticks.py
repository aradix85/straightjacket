from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockEvent, ClockFillResult, GameState
from .clock_consequences import resolve_clock_fill
from .complications import is_complication
from .config import gm
from .npc.matching import normalize_for_match


def tick_threat_clock(
    game: GameState,
    ticks: int,
    clock_events: list[ClockEvent],
    fill_results: list[ClockFillResult],
) -> None:
    for clock in game.world.clocks:
        if clock.clock_type == "threat" and clock.filled < clock.segments:
            clock.filled = min(clock.segments, clock.filled + ticks)
            if clock.filled >= clock.segments:
                clock.fired = True
                clock.fired_at_scene = game.narrative.scene_count
                clock_events.append(
                    ClockEvent(
                        clock=clock.name,
                        trigger=clock.trigger_description,
                        autonomous=False,
                        triggered=True,
                    )
                )
                fill = resolve_clock_fill(game, clock)
                if fill is not None:
                    fill_results.append(fill)
            break


def check_npc_agency(game: GameState) -> tuple[list[str], list[ClockEvent], list[ClockFillResult]]:
    if game.narrative.scene_count % gm().pacing.npc_agency_interval != 0:
        return [], [], []
    _defaults = eng().ai_text.narrator_defaults
    actions: list[str] = []
    clock_events: list[ClockEvent] = []
    fill_results: list[ClockFillResult] = []
    for npc in game.npcs:
        if npc.status == "active" and npc.agenda:
            actions.append(_defaults["npc_agency_action_template"].format(npc_name=npc.name, agenda=npc.agenda))
            npc_norms = {normalize_for_match(npc.name)}
            npc_norms.update(normalize_for_match(a) for a in npc.aliases)
            for clock in game.world.clocks:
                if clock.clock_type not in gm().pacing.npc_agency_clock_types:
                    continue
                if clock.owner_kind != "npc" or clock.owner_id is None:
                    continue
                if normalize_for_match(clock.owner_id) not in npc_norms:
                    continue
                if clock.filled >= clock.segments:
                    continue
                clock.filled += 1
                triggered = clock.filled >= clock.segments
                if triggered:
                    clock.fired = True
                    clock.fired_at_scene = game.narrative.scene_count
                    fill = resolve_clock_fill(game, clock)
                    if fill is not None:
                        fill_results.append(fill)
                event = ClockEvent(
                    clock=clock.name,
                    trigger=clock.trigger_description,
                    autonomous=False,
                    triggered=triggered,
                )
                clock_events.append(event)
                status = "TRIGGERED" if triggered else f"{clock.filled}/{clock.segments}"
                log(f"[Clock] NPC agency tick: '{clock.name}' by '{npc.name}' → {status}")
    return actions, clock_events, fill_results


def tick_autonomous_clocks(game: GameState) -> list[ClockEvent]:
    tick_chance = gm().pacing.autonomous_clock_tick_chance
    complication_chance = gm().clocks.complication.tick_chance
    ticked: list[ClockEvent] = []
    for clock in game.world.clocks:
        if clock.clock_type != "threat":
            continue
        if clock.filled >= clock.segments:
            continue
        if clock.owner_kind != "world":
            continue
        if random.random() < (complication_chance if is_complication(clock) else tick_chance):
            clock.filled += 1
            triggered = clock.filled >= clock.segments
            if triggered:
                clock.fired = True
                clock.fired_at_scene = game.narrative.scene_count
                fill = resolve_clock_fill(game, clock)
                if fill is not None:
                    game.world.pending_clock_fills.append(fill)
            event = ClockEvent(
                clock=clock.name,
                trigger=clock.trigger_description,
                autonomous=True,
                triggered=triggered,
            )
            ticked.append(event)
            status = "TRIGGERED" if triggered else f"{clock.filled}/{clock.segments}"
            log(f"[Clock] Autonomous tick: '{clock.name}' → {status}")
    return ticked


def purge_old_fired_clocks(game: GameState) -> None:
    keep_scenes = gm().pacing.fired_clock_keep_scenes
    before = len(game.world.clocks)
    game.world.clocks = [
        c for c in game.world.clocks if not c.fired or (game.narrative.scene_count - c.fired_at_scene) <= keep_scenes
    ]
    purged = before - len(game.world.clocks)
    if purged:
        log(f"[Clock] Purged {purged} expired fired clock(s) at scene {game.narrative.scene_count}")
