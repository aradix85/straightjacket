from __future__ import annotations

import random

from .tracks import complete_track
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ThreatEvent
from .spawn_sources import EMERGENT_SOURCE_PREFIXES


def count_emergent_threats(game: GameState) -> int:
    return sum(1 for t in game.threats if t.creation_source.startswith(EMERGENT_SOURCE_PREFIXES))


def next_threat_id(game: GameState, prefix: str) -> str:
    n = 1
    while any(t.id == f"{prefix}{n}" for t in game.threats):
        n += 1
    return f"{prefix}{n}"


def advance_menace_on_miss(game: GameState) -> list[ThreatEvent]:
    marks = eng().threats.menace_on_miss
    events: list[ThreatEvent] = []
    for threat in game.threats:
        if threat.status != "active":
            continue
        vow = next((t for t in game.progress_tracks if t.id == threat.linked_vow_id and t.status == "active"), None)
        if not vow:
            continue
        ticks = threat.advance_menace(marks)
        if ticks > 0:
            events.append(
                ThreatEvent(
                    threat_id=threat.id,
                    threat_name=threat.name,
                    ticks_added=ticks,
                    menace_full=threat.menace_full,
                    source="miss",
                )
            )
            status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/{threat.menace_total_boxes}"
            log(f"[Threat] Menace advance on MISS: '{threat.name}' +{ticks} ticks → {status}")
    return events


def tick_autonomous_threats(game: GameState) -> None:
    _cfg = eng().threats
    tick_chance = _cfg.autonomous_tick_chance
    marks = _cfg.autonomous_tick_marks
    for threat in game.threats:
        if threat.status != "active":
            continue
        if threat.menace_full:
            continue
        if random.random() >= tick_chance:
            continue
        ticks = threat.advance_menace(marks)
        status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/{threat.menace_total_boxes}"
        log(f"[Threat] Autonomous menace: '{threat.name}' +{ticks} ticks → {status}")


def advance_threat_by_id(game: GameState, threat_id: str) -> None:
    threat = next((t for t in game.threats if t.id == threat_id and t.status == "active"), None)
    if not threat:
        return
    ticks = threat.advance_menace(eng().threats.menace_on_random_event)
    if ticks <= 0:
        return
    status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/{threat.menace_total_boxes}"
    log(f"[Threat] Menace advance (random event): '{threat.name}' +{ticks} ticks → {status}")


def resolve_full_menace(game: GameState) -> list[ThreatEvent]:
    spirit_cost = eng().threats.forsake_spirit_cost
    events: list[ThreatEvent] = []

    for threat in game.threats:
        if threat.status != "active" or not threat.menace_full:
            continue
        if threat.linked_vow_id is None:
            threat.status = "resolved"
            log(f"[Threat] '{threat.name}' menace full, no linked vow — resolved")
            continue
        vow = next((t for t in game.progress_tracks if t.id == threat.linked_vow_id and t.status == "active"), None)
        if not vow:
            threat.status = "resolved"
            log(f"[Threat] '{threat.name}' menace full but vow already gone — resolved")
            continue

        complete_track(game, vow.id, "failed")
        threat.status = "resolved"
        game.resources.damage("spirit", spirit_cost)
        events.append(
            ThreatEvent(
                threat_id=threat.id,
                threat_name=threat.name,
                ticks_added=0,
                menace_full=True,
                source="forsake_vow",
            )
        )
        log(f"[Threat] FORSAKE YOUR VOW: '{threat.name}' menace full → vow '{vow.name}' failed, spirit -{spirit_cost}")

    return events
