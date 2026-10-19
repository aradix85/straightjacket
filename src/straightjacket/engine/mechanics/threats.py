from __future__ import annotations

import random

from .tracks import forsake_vow
from ..datasworn.oracle_rolls import plain_text, roll_table
from ..datasworn.settings import load_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ThreatData, ThreatEvent
from .outcome_result import OutcomeResult
from .spawn_sources import EMERGENT_SOURCE_PREFIXES


def count_emergent_threats(game: GameState) -> int:
    return sum(1 for t in game.threats if t.creation_source.startswith(EMERGENT_SOURCE_PREFIXES))


def next_threat_id(game: GameState, prefix: str) -> str:
    n = 1
    while any(t.id == f"{prefix}{n}" for t in game.threats):
        n += 1
    return f"{prefix}{n}"


def _development(game: GameState, threat: ThreatData) -> str:
    pkg = load_package(game.setting_id)
    path = f"{eng().threats.category_oracle_collection}/{threat.category}"
    if not pkg.has_oracle(path):
        return ""
    return plain_text(roll_table(pkg, pkg.oracle_table(path)).text)


def _advance(game: GameState, threat: ThreatData, marks: int, source: str) -> ThreatEvent | None:
    ticks = threat.advance_menace(marks)
    if ticks <= 0:
        return None
    status = "FULL" if threat.menace_full else f"{threat.menace_filled_boxes}/{threat.menace_total_boxes}"
    log(f"[Threat] Menace advance ({source}): '{threat.name}' +{ticks} ticks → {status}")
    return ThreatEvent(
        threat_id=threat.id,
        threat_name=threat.name,
        menace_full=threat.menace_full,
        source=source,
        development=_development(game, threat),
    )


def advance_menace_on_miss(game: GameState) -> list[ThreatEvent]:
    marks = eng().threats.menace_on_miss
    events: list[ThreatEvent] = []
    for threat in game.threats:
        if threat.status != "active":
            continue
        vow = next((t for t in game.progress_tracks if t.id == threat.linked_vow_id and t.status == "active"), None)
        if not vow:
            continue
        event = _advance(game, threat, marks, "miss")
        if event is not None:
            events.append(event)
    return events


def tick_autonomous_threats(game: GameState) -> None:
    _cfg = eng().threats
    for threat in game.threats:
        if threat.status != "active" or threat.menace_full or random.random() >= _cfg.autonomous_tick_chance:
            continue
        event = _advance(game, threat, _cfg.autonomous_tick_marks, "autonomous")
        if event is not None:
            game.world.pending_threat_events.append(event)


def advance_threat_by_id(game: GameState, threat_id: str) -> None:
    threat = next((t for t in game.threats if t.id == threat_id and t.status == "active"), None)
    if not threat:
        return
    event = _advance(game, threat, eng().threats.menace_on_random_event, "random_event")
    if event is not None:
        game.world.pending_threat_events.append(event)


def take_pending_threat_events(game: GameState) -> list[ThreatEvent]:
    events = list(game.world.pending_threat_events)
    game.world.pending_threat_events.clear()
    return events


def resolve_full_menace(game: GameState, result: OutcomeResult) -> list[ThreatEvent]:
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

        threat.status = "resolved"
        forsake_vow(game, vow, result)
        events.append(
            ThreatEvent(
                threat_id=threat.id,
                threat_name=threat.name,
                menace_full=True,
                source="forsake_vow",
                development="",
            )
        )
        log(f"[Threat] FORSAKE YOUR VOW: '{threat.name}' menace full → vow '{vow.name}' failed")

    return events
