from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, RandomEvent
from .fate import _load_mythic


_pending_events: list[RandomEvent] = []


def drain_pending_events() -> list[RandomEvent]:
    events = list(_pending_events)
    _pending_events.clear()
    return events


def roll_event_focus(roll: int | None = None) -> tuple[str, int]:
    data = _load_mythic()
    table = data["event_focus"]

    if roll is None:
        roll = random.randint(1, 100)

    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            return entry["focus"], roll

    raise ValueError(f"event_focus table has no entry covering roll={roll}; table must span 1..100")


def roll_meaning_table(table_name: str) -> tuple[str, str]:
    data = _load_mythic()
    tables = data["meaning_tables"]

    if table_name == "descriptions":
        words1 = tables["descriptions"]["adverbs"]
        words2 = tables["descriptions"]["adjectives"]
    elif table_name == "actions":
        words1 = tables["actions"]["verbs"]
        words2 = tables["actions"]["subjects"]
    else:
        raise KeyError(f"Unknown meaning table '{table_name}' (valid: 'actions', 'descriptions')")

    w1 = words1[random.randint(0, len(words1) - 1)]
    w2 = words2[random.randint(0, len(words2) - 1)]
    return w1, w2


def _select_from_weighted_list(entries: list) -> tuple[str, str]:
    if not entries:
        return "", ""

    active = [e for e in entries if e.active]
    if not active:
        return "", ""

    pool: list[tuple[str, str]] = []
    for entry in active:
        pool.extend([(entry.name, entry.id)] * entry.weight)

    if not pool:
        return "", ""

    return random.choice(pool)


def _select_target(focus: str, game: GameState) -> tuple[str, str]:
    cfg = eng().random_events

    if focus in cfg.threat_eligible_focus_categories:
        active_threats = [t for t in game.threats if t.status == "active" and not t.menace_full]
        if active_threats and random.random() < cfg.threat_target_probability:
            threat = random.choice(active_threats)
            log(f"[RandomEvent] Threat-eligible focus '{focus}' → targeting threat '{threat.name}'")
            return threat.name, threat.id

    if focus in cfg.npc_focus_categories:
        name, target_id = _select_from_weighted_list(game.narrative.characters_list)
        if not name:
            log(f"[RandomEvent] NPC focus '{focus}' but characters list empty, using current_context")
        return name, target_id

    if focus in cfg.thread_focus_categories:
        name, target_id = _select_from_weighted_list(game.narrative.threads)
        if not name:
            log(f"[RandomEvent] Thread focus '{focus}' but threads list empty, using current_context")
        return name, target_id

    return "", ""


def generate_random_event(game: GameState, source: str = "") -> RandomEvent:
    cfg = eng().random_events

    focus, focus_roll = roll_event_focus()

    target_name, target_id = _select_target(focus, game)

    table_name = "descriptions" if focus in cfg.description_focus_categories else "actions"
    word1, word2 = roll_meaning_table(table_name)

    event = RandomEvent(
        focus=focus,
        focus_roll=focus_roll,
        target=target_name,
        target_id=target_id,
        meaning_action=word1,
        meaning_subject=word2,
        meaning_table=table_name,
        source=source,
    )

    target_str = f" target='{target_name}'" if target_name else ""
    log(f"[RandomEvent] {focus}{target_str} → {word1} / {word2} (source={source})")
    _pending_events.append(event)
    return event


def add_thread_weight(game: GameState, thread_id: str) -> None:
    cap = eng().random_events.list_weight_max
    for t in game.narrative.threads:
        if t.id == thread_id and t.active:
            if t.weight < cap:
                t.weight += 1
                log(f"[Lists] Thread '{t.name}' weight → {t.weight}")
            return


def add_character_weight(game: GameState, character_id: str) -> None:
    cap = eng().random_events.list_weight_max
    for c in game.narrative.characters_list:
        if c.id == character_id and c.active:
            if c.weight < cap:
                c.weight += 1
                log(f"[Lists] Character '{c.name}' weight → {c.weight}")
            return


def consolidate_threads(game: GameState) -> None:
    cfg = eng().random_events
    threads = [t for t in game.narrative.threads if t.active]
    if len(threads) < cfg.consolidation_threshold:
        return

    for t in threads:
        t.weight = (
            cfg.consolidation_weight_low
            if t.weight >= cfg.consolidation_weight_high
            else cfg.consolidation_weight_default
        )

    log(f"[Lists] Consolidated {len(threads)} threads")


def consolidate_characters(game: GameState) -> None:
    cfg = eng().random_events
    chars = [c for c in game.narrative.characters_list if c.active]
    if len(chars) < cfg.consolidation_threshold:
        return

    for c in chars:
        c.weight = (
            cfg.consolidation_weight_low
            if c.weight >= cfg.consolidation_weight_high
            else cfg.consolidation_weight_default
        )

    log(f"[Lists] Consolidated {len(chars)} characters")


def deactivate_thread(game: GameState, thread_id: str) -> None:
    for t in game.narrative.threads:
        if t.id == thread_id:
            t.active = False
            log(f"[Lists] Thread '{t.name}' deactivated")
            return
