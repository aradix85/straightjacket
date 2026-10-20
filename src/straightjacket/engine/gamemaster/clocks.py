from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, ClockEvent, ClockFillResult, GameState, NarrativeState
from .config import gm
from .keyed_scenes import add_keyed_scene, has_keyed_scene_from
from .npc.matching import normalize_for_match
from .questions import answers
from .spawn_sources import CLOCK_KEYED_SOURCE_PREFIX, COMPLICATION_SOURCE_PREFIX, EMERGENT_SOURCE_PREFIXES, SETUP_SOURCE


def _unique_clock_name(game: GameState, base_name: str) -> str:
    existing = {c.name for c in game.world.clocks}
    if base_name not in existing:
        return base_name
    template = gm().clocks.duplicate_name_template
    n = 2
    while template.format(name=base_name, n=n) in existing:
        n += 1
    return template.format(name=base_name, n=n)


def _emergent_cap_reached(game: GameState) -> bool:
    emergent = sum(
        1 for c in game.world.clocks if not c.fired and c.creation_source.startswith(EMERGENT_SOURCE_PREFIXES)
    )
    return emergent >= gm().clocks.max_open_emergent


def spawn_keyed_scenes_for_clock(narrative: NarrativeState, clock: ClockData) -> None:
    entry = gm().clock_keyed_scenes.by_clock_type[clock.clock_type]
    for fraction in entry.fractions:
        threshold = max(1, round(clock.segments * fraction))
        source = f"{CLOCK_KEYED_SOURCE_PREFIX}{clock.name}:{threshold}"
        if has_keyed_scene_from(narrative, source):
            continue
        scene = add_keyed_scene(
            narrative,
            trigger_type="clock_fills",
            trigger_value=f"{clock.name}:{threshold}",
            priority=entry.priority,
            narrative_hint=entry.narrative_hint_template.format(clock_name=clock.name),
            source=source,
        )
        log(
            f"[Clock] spawned keyed-scene '{scene.id}' for clock '{clock.name}' "
            f"(type={clock.clock_type}, fraction={fraction}, threshold={threshold}, priority={entry.priority})"
        )


def new_clock(
    *, name: str, clock_type: str, segments: int, filled: int, trigger_description: str, creation_source: str
) -> ClockData:
    return ClockData(
        name=name,
        clock_type=clock_type,
        segments=segments,
        trigger_description=trigger_description,
        owner_kind=gm().clocks.default_owner_kind,
        creation_source=creation_source,
        filled=filled,
        owner_id=None,
        fired=False,
        fired_at_scene=0,
    )


def spawn_emergent_clock(
    game: GameState, *, base_name: str, clock_type: str, trigger_description: str, source: str
) -> ClockData | None:
    if any(c.creation_source == source for c in game.world.clocks):
        return None
    cfg = gm().clocks
    if _emergent_cap_reached(game):
        log(f"[Clock] emergent clock cap {cfg.max_open_emergent} reached, no clock from '{source}'")
        return None
    clock = new_clock(
        name=_unique_clock_name(game, base_name),
        clock_type=clock_type,
        segments=cfg.default_segments,
        filled=0,
        trigger_description=trigger_description,
        creation_source=source,
    )
    game.world.clocks.append(clock)
    spawn_keyed_scenes_for_clock(game.narrative, clock)
    log(f"[Clock] spawned '{clock.name}' (type={clock_type}, segments={clock.segments}) from '{source}'")
    return clock


def start_opening_clock(game: GameState) -> None:
    opening = gm().opening
    clock = new_clock(
        name=game.background_vow,
        clock_type="threat",
        segments=opening.clock_segments,
        filled=opening.clock_filled,
        trigger_description=opening.clock_trigger_template.format(player=game.player_name),
        creation_source=SETUP_SOURCE,
    )
    game.world.clocks.append(clock)
    spawn_keyed_scenes_for_clock(game.narrative, clock)
    log(f"[Clock] opening clock '{clock.name}' at {clock.filled}/{clock.segments}")


def is_complication(clock: ClockData) -> bool:
    return clock.creation_source.startswith(COMPLICATION_SOURCE_PREFIX)


def open_complications(game: GameState) -> list[ClockData]:
    return [c for c in game.world.clocks if is_complication(c) and not c.fired]


def spawn_complication_clock(game: GameState, kind: str, danger: str) -> ClockData | None:
    cfg = gm().clocks
    if len(open_complications(game)) >= cfg.complication.max_open:
        log(f"[Complication] {cfg.complication.max_open} complication clock(s) already open, no clock for '{danger}'")
        return None
    if _emergent_cap_reached(game):
        log(f"[Complication] emergent clock cap {cfg.max_open_emergent} reached, no clock for '{danger}'")
        return None
    clock = new_clock(
        name=_unique_clock_name(game, danger),
        clock_type="threat",
        segments=cfg.complication.segments,
        filled=0,
        trigger_description=danger,
        creation_source=f"{COMPLICATION_SOURCE_PREFIX}{kind}:{game.narrative.scene_count}",
    )
    game.world.clocks.append(clock)
    log(f"[Complication] clock '{clock.name}' started from {kind} ({clock.segments} segments)")
    return clock


def avert_complication(game: GameState, name: str) -> None:
    clock = next((c for c in open_complications(game) if c.name == name), None)
    if clock is None:
        raise ValueError(f"No open complication clock named {name!r}")
    game.world.clocks.remove(clock)
    log(f"[Complication] clock '{name}' averted at {clock.filled}/{clock.segments}")


def resolve_clock_fill(game: GameState, clock: ClockData) -> ClockFillResult | None:
    keyed_prefix = f"{CLOCK_KEYED_SOURCE_PREFIX}{clock.name}:"
    if any(ks.source.startswith(keyed_prefix) for ks in game.narrative.keyed_scenes):
        log(f"[ClockFill] '{clock.name}' has attached keyed-scene, default suppressed")
        return None
    tag_text = gm().clocks.fill_consequences[clock.clock_type].tag_template.format(clock_name=clock.name)
    answers().clock_filled(game, clock)
    log(f"[ClockFill] '{clock.name}' (type={clock.clock_type}) fired → tag emitted")
    return ClockFillResult(clock_name=clock.name, clock_type=clock.clock_type, tag_text=tag_text)


def _advance_clock(
    game: GameState, clock: ClockData, ticks: int, autonomous: bool
) -> tuple[ClockEvent, ClockFillResult | None]:
    clock.filled = min(clock.segments, clock.filled + ticks)
    triggered = clock.filled >= clock.segments
    fill: ClockFillResult | None = None
    if triggered:
        clock.fired = True
        clock.fired_at_scene = game.narrative.scene_count
        fill = resolve_clock_fill(game, clock)
    event = ClockEvent(clock=clock.name, trigger=clock.trigger_description, autonomous=autonomous, triggered=triggered)
    return event, fill


def tick_threat_clock(
    game: GameState,
    ticks: int,
    clock_events: list[ClockEvent],
    fill_results: list[ClockFillResult],
) -> None:
    clock = next((c for c in game.world.clocks if c.clock_type == "threat" and c.filled < c.segments), None)
    if clock is None:
        return
    event, fill = _advance_clock(game, clock, ticks, autonomous=False)
    if event.triggered:
        clock_events.append(event)
    if fill is not None:
        fill_results.append(fill)


def check_npc_agency(game: GameState) -> tuple[list[str], list[ClockEvent], list[ClockFillResult]]:
    if game.narrative.scene_count % gm().pacing.npc_agency_interval != 0:
        return [], [], []
    _defaults = eng().ai_text.narrator_defaults
    actions: list[str] = []
    clock_events: list[ClockEvent] = []
    fill_results: list[ClockFillResult] = []
    for npc in game.npcs:
        if npc.status != "active" or not npc.agenda:
            continue
        actions.append(_defaults["npc_agency_action_template"].format(npc_name=npc.name, agenda=npc.agenda))
        npc_norms = {normalize_for_match(npc.name)} | {normalize_for_match(a) for a in npc.aliases}
        for clock in game.world.clocks:
            if clock.clock_type not in gm().pacing.npc_agency_clock_types:
                continue
            if clock.owner_kind != "npc" or clock.owner_id is None:
                continue
            if normalize_for_match(clock.owner_id) not in npc_norms or clock.filled >= clock.segments:
                continue
            event, fill = _advance_clock(game, clock, 1, autonomous=False)
            clock_events.append(event)
            if fill is not None:
                fill_results.append(fill)
            status = "TRIGGERED" if event.triggered else f"{clock.filled}/{clock.segments}"
            log(f"[Clock] NPC agency tick: '{clock.name}' by '{npc.name}' → {status}")
    return actions, clock_events, fill_results


def tick_autonomous_clocks(game: GameState) -> list[ClockEvent]:
    tick_chance = gm().pacing.autonomous_clock_tick_chance
    complication_chance = gm().clocks.complication.tick_chance
    ticked: list[ClockEvent] = []
    for clock in game.world.clocks:
        if clock.clock_type != "threat" or clock.filled >= clock.segments or clock.owner_kind != "world":
            continue
        if random.random() < (complication_chance if is_complication(clock) else tick_chance):
            event, fill = _advance_clock(game, clock, 1, autonomous=True)
            if fill is not None:
                game.world.pending_clock_fills.append(fill)
            ticked.append(event)
            status = "TRIGGERED" if event.triggered else f"{clock.filled}/{clock.segments}"
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
