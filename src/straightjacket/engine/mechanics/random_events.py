"""Mythic GME 2e random events: event focus, meaning tables, pipeline.

Random events fire on fate doublets (step 3.3) and interrupt scenes (step 4.5).
All engine-deterministic. The pipeline assembles structured events from dice
rolls; the narrator weaves them into prose.

Data: data/mythic_gme_2e.json → event_focus, meaning_tables.
"""

from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, RandomEvent
from .fate import _load_mythic

# PENDING EVENTS — accumulator drained by turn pipeline after Brain call.
# Same pattern as provider_base._token_log.
_pending_events: list[RandomEvent] = []


def drain_pending_events() -> list[RandomEvent]:
    """Return and clear pending random events. Call after Brain phase."""
    events = list(_pending_events)
    _pending_events.clear()
    return events


def roll_event_focus(roll: int | None = None) -> tuple[str, int]:
    """Roll d100 on the Event Focus Table. Returns (focus_category, roll)."""
    data = _load_mythic()
    table = data["event_focus"]

    if roll is None:
        roll = random.randint(1, 100)

    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            return entry["focus"], roll

    raise ValueError(f"event_focus table has no entry covering roll={roll}; table must span 1..100")


def roll_meaning_table(table_name: str) -> tuple[str, str]:
    """Roll on a meaning table. Returns (word1, word2).

    Actions table: (verb, subject). For events and actions.
    Descriptions table: (adverb, adjective). For qualities and states.
    Caller passes the table name; the `else` branch below is the actions path,
    not a silent fallback — unknown table names still hit actions and are logged
    downstream via the random_event source.
    """
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
    """Select from a weighted list (threads or characters). Returns (name, id)."""
    if not entries:
        return "", ""

    active = [e for e in entries if e.active]
    if not active:
        return "", ""

    # Build weighted pool: each entry appears weight times.
    pool: list[tuple[str, str]] = []
    for entry in active:
        pool.extend([(entry.name, entry.id)] * entry.weight)

    if not pool:
        return "", ""

    return random.choice(pool)


def _select_target(focus: str, game: GameState) -> tuple[str, str]:
    """Select event target based on focus category. Returns (name, id).

    NPC-focus categories select from characters_list.
    Thread-focus categories select from threads list.
    Threat-eligible categories may target an active threat (probability from yaml).
    Empty list → falls back to current_context (no target).
    """
    cfg = eng().random_events
    # Threat targeting: eligible focus + active threats → configured probability
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
    """Generate a complete random event from the Mythic GME 2e pipeline.

    Four steps:
    1. Roll d100 on Event Focus Table → category.
    2. If category targets NPC/thread, select from weighted list.
    3. Roll meaning tables → word pair.
    4. Assemble RandomEvent.

    The narrator receives the structured event as a <random_event> tag.
    """
    cfg = eng().random_events

    # Step 1: focus
    focus, focus_roll = roll_event_focus()

    # Step 2: target
    target_name, target_id = _select_target(focus, game)

    # Step 3: meaning
    # Use actions for events/actions, descriptions for qualities
    table_name = "descriptions" if focus in cfg.description_focus_categories else "actions"
    word1, word2 = roll_meaning_table(table_name)

    # Step 4: assemble
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
    """Increase thread weight when invoked in a scene. Capped by yaml list_weight_max."""
    cap = eng().random_events.list_weight_max
    for t in game.narrative.threads:
        if t.id == thread_id and t.active:
            if t.weight < cap:
                t.weight += 1
                log(f"[Lists] Thread '{t.name}' weight → {t.weight}")
            return


def add_character_weight(game: GameState, character_id: str) -> None:
    """Increase character weight when invoked in a scene. Capped by yaml list_weight_max."""
    cap = eng().random_events.list_weight_max
    for c in game.narrative.characters_list:
        if c.id == character_id and c.active:
            if c.weight < cap:
                c.weight += 1
                log(f"[Lists] Character '{c.name}' weight → {c.weight}")
            return


def consolidate_threads(game: GameState) -> None:
    """Consolidate threads list when it reaches the configured threshold.

    Entries with weight >= consolidation_weight_high get weight_low on the new
    list; others get weight_default.
    """
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
    """Consolidate characters list when it reaches the configured threshold.

    Entries with weight >= consolidation_weight_high get weight_low on the new
    list; others get weight_default.
    """
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
    """Mark a thread as inactive (resolved/closed)."""
    for t in game.narrative.threads:
        if t.id == thread_id:
            t.active = False
            log(f"[Lists] Thread '{t.name}' deactivated")
            return
