"""Threat menace mechanics: advancement, autonomous ticks, resolution.

Threats have menace tracks that compete against linked vow progress.
Menace advances on misses, random events, and autonomous ticks.
When menace fills before the vow completes, Forsake Your Vow is forced.
"""

from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ThreatData, ThreatEvent


def find_threat_for_vow(game: GameState, vow_id: str) -> ThreatData | None:
    """Find the active threat linked to a vow track."""
    for t in game.threats:
        if t.linked_vow_id == vow_id and t.status == "active":
            return t
    return None


def advance_menace_on_miss(game: GameState, move: str) -> list[ThreatEvent]:
    """Advance menace on active threats after a MISS. Returns events for narrator prompt."""
    marks = eng().threats.menace_on_miss
    if marks <= 0:
        return []

    events: list[ThreatEvent] = []
    for threat in game.threats:
        if threat.status != "active":
            continue
        # Only advance threats linked to vows that are still active
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
            status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/10"
            log(f"[Threat] Menace advance on MISS: '{threat.name}' +{ticks} ticks → {status}")
    return events


def tick_autonomous_threats(game: GameState) -> list[ThreatEvent]:
    """Autonomously advance threat menace by chance each scene."""
    tick_chance = eng().threats.autonomous_tick_chance
    events: list[ThreatEvent] = []
    for threat in game.threats:
        if threat.status != "active":
            continue
        if threat.menace_full:
            continue
        if random.random() >= tick_chance:
            continue
        ticks = threat.advance_menace(1)
        if ticks > 0:
            events.append(
                ThreatEvent(
                    threat_id=threat.id,
                    threat_name=threat.name,
                    ticks_added=ticks,
                    menace_full=threat.menace_full,
                    source="autonomous",
                )
            )
            status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/10"
            log(f"[Threat] Autonomous menace: '{threat.name}' +{ticks} ticks → {status}")
    return events


def advance_threat_by_id(game: GameState, threat_id: str, marks: int = 1, source: str = "") -> ThreatEvent | None:
    """Advance a specific threat's menace. Used by random event integration."""
    threat = next((t for t in game.threats if t.id == threat_id and t.status == "active"), None)
    if not threat:
        return None
    ticks = threat.advance_menace(marks)
    if ticks <= 0:
        return None
    event = ThreatEvent(
        threat_id=threat.id,
        threat_name=threat.name,
        ticks_added=ticks,
        menace_full=threat.menace_full,
        source=source,
    )
    status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/10"
    log(f"[Threat] Menace advance ({source}): '{threat.name}' +{ticks} ticks → {status}")
    return event


def resolve_full_menace(game: GameState) -> list[ThreatEvent]:
    """Resolve all threats with full menace: Forsake Your Vow.

    For each active threat where menace is full:
    1. Fail the linked vow track (+ deactivate linked thread via complete_track)
    2. Mark threat as resolved
    3. Apply spirit damage
    4. Return events for narrator prompt injection

    Called once per turn after all menace advances.
    """
    from ..game.tracks import complete_track

    spirit_cost = eng().threats.forsake_spirit_cost
    events: list[ThreatEvent] = []

    for threat in game.threats:
        if threat.status != "active" or not threat.menace_full:
            continue
        vow = next((t for t in game.progress_tracks if t.id == threat.linked_vow_id and t.status == "active"), None)
        if not vow:
            # Vow already completed/failed — just resolve the threat
            threat.status = "resolved"
            log(f"[Threat] '{threat.name}' menace full but vow already gone — resolved")
            continue

        # Forsake Your Vow: fail the vow, resolve the threat, damage spirit
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
