from __future__ import annotations

from typing import Any
import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, GameState, KeyedScene, RandomEvent, ThreatData
from .fate import _load_mythic
from .clocks import count_emergent_clocks, unique_clock_name
from .keyed_scenes import spawn_keyed_scenes_for_clock
from ..npc import find_npc
from .spawn_sources import RANDOM_EVENT_SOURCE_PREFIX
from .threats import count_emergent_threats, next_threat_id


_pending_events: list[RandomEvent] = []


def drain_pending_events() -> list[RandomEvent]:
    events = list(_pending_events)
    _pending_events.clear()
    return events


def roll_event_focus() -> str:
    table = _load_mythic()["event_focus"]
    roll = random.randint(1, eng().dice.event_focus_die)

    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            focus: str = entry["focus"]
            return focus

    raise ValueError(f"event_focus table has no entry covering roll={roll}")


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


def _select_from_weighted_list(entries: list[Any]) -> tuple[str, str]:
    active = [e for e in entries if e.active]
    if not active:
        return "", ""

    pool: list[tuple[str, str]] = []
    for entry in active:
        pool.extend([(entry.name, entry.id)] * entry.weight)

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


def generate_random_event(game: GameState, source: str) -> RandomEvent:
    cfg = eng().random_events

    focus = roll_event_focus()

    target_name, target_id = _select_target(focus, game)

    table_name = "descriptions" if focus in cfg.description_focus_categories else "actions"
    word1, word2 = roll_meaning_table(table_name)

    event = RandomEvent(
        focus=focus,
        target=target_name,
        target_id=target_id,
        meaning_action=word1,
        meaning_subject=word2,
        source=source,
    )

    target_str = f" target='{target_name}'" if target_name else ""
    log(f"[RandomEvent] {focus}{target_str} → {word1} / {word2} (source={source})")
    _pending_events.append(event)

    spawn_keyed_scene_from_random_event(game, event)
    spawn_threat_from_random_event(game, event)
    spawn_clock_from_random_event(game, event)

    return event


def _re_already_spawned_for_target(game: GameState, focus: str, target_id: str) -> bool:
    target = f"{RANDOM_EVENT_SOURCE_PREFIX}{focus}:{target_id}"
    return any(ks.source == target for ks in game.narrative.keyed_scenes)


def _re_next_keyed_scene_id(game: GameState) -> str:
    n = 1
    while any(ks.id == f"ks_re_{n}" for ks in game.narrative.keyed_scenes):
        n += 1
    return f"ks_re_{n}"


def spawn_keyed_scene_from_random_event(game: GameState, event: RandomEvent) -> None:
    cfg = eng().random_events
    if event.focus not in cfg.keyed_scene_mapping:
        return
    if not event.target_id:
        return
    if _re_already_spawned_for_target(game, event.focus, event.target_id):
        return

    entry = cfg.keyed_scene_mapping[event.focus]
    if entry.trigger_type == "bond_threshold":
        if find_npc(game, event.target_id) is None:
            log(
                f"[RandomEvent] focus '{event.focus}' targets '{event.target_id}', a character without an NPC "
                "record; a bond keyed-scene needs an NPC, so none is spawned"
            )
            return
        pool = event.target_id
    elif entry.trigger_type == "threat_menace_phase":
        pool = event.target
    else:
        raise ValueError(
            f"random_events.keyed_scene_mapping for focus {event.focus!r} uses unsupported "
            f"trigger_type {entry.trigger_type!r}"
        )
    trigger_value = f"{pool}:{entry.threshold}"

    scene_id = _re_next_keyed_scene_id(game)
    scene = KeyedScene(
        id=scene_id,
        trigger_type=entry.trigger_type,
        trigger_value=trigger_value,
        priority=entry.priority,
        narrative_hint=entry.narrative_hint,
        source=f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{event.target_id}",
    )
    game.narrative.keyed_scenes.append(scene)
    log(
        f"[RandomEvent] spawned keyed-scene '{scene_id}' from focus '{event.focus}' "
        f"target_id='{event.target_id}' (trigger {entry.trigger_type}={trigger_value!r}, "
        f"priority={entry.priority})"
    )


def _re_threat_already_spawned(game: GameState, focus: str, target_id: str) -> bool:
    target = f"{RANDOM_EVENT_SOURCE_PREFIX}{focus}:{target_id}"
    return any(t.creation_source == target for t in game.threats)


def spawn_threat_from_random_event(game: GameState, event: RandomEvent) -> None:
    cfg = eng().random_events
    if event.focus not in cfg.threat_creation_mapping:
        return

    dedup_key = event.target_id or event.focus
    if _re_threat_already_spawned(game, event.focus, dedup_key):
        return

    max_threats = eng().adventure_crafter.max_threats_per_chapter
    if count_emergent_threats(game) >= max_threats:
        log(f"[Threat] emergent threat cap {max_threats} reached, skipping focus '{event.focus}'")
        return

    entry = cfg.threat_creation_mapping[event.focus]
    name = _name_from_mythic_pair(event.meaning_action, event.meaning_subject)
    description = f"{event.meaning_action} / {event.meaning_subject}"
    threat_id = next_threat_id(game, "threat_re_")
    creation_source = f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{dedup_key}"

    threat = ThreatData.new(
        id=threat_id,
        name=name,
        category=entry.category,
        linked_vow_id=None,
        rank=entry.rank,
        description=description,
        creation_source=creation_source,
    )
    game.threats.append(threat)
    log(
        f"[Threat] spawned '{name}' (id={threat_id}, rank={entry.rank}, category={entry.category}) "
        f"from random-event focus '{event.focus}'"
    )


def _re_clock_already_spawned(game: GameState, focus: str, dedup_key: str) -> bool:
    target = f"{RANDOM_EVENT_SOURCE_PREFIX}{focus}:{dedup_key}"
    return any(c.creation_source == target for c in game.world.clocks)


def spawn_clock_from_random_event(game: GameState, event: RandomEvent) -> None:
    cfg = eng().random_events
    if event.focus not in cfg.clock_creation_mapping:
        return

    dedup_key = event.target_id or event.focus
    if _re_clock_already_spawned(game, event.focus, dedup_key):
        return

    clocks_cfg = eng().clocks
    if count_emergent_clocks(game) >= clocks_cfg.max_clocks_per_chapter:
        log(f"[Clock] emergent clock cap {clocks_cfg.max_clocks_per_chapter} reached, skipping focus '{event.focus}'")
        return

    entry = cfg.clock_creation_mapping[event.focus]
    base_name = _name_from_mythic_pair(event.meaning_action, event.meaning_subject)
    clock_name = unique_clock_name(game, base_name)
    creation_source = f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{dedup_key}"

    clock = ClockData(
        name=clock_name,
        clock_type=entry.clock_type,
        segments=clocks_cfg.default_segments,
        trigger_description=f"{event.meaning_action} / {event.meaning_subject}",
        owner_kind=clocks_cfg.default_owner_kind,
        creation_source=creation_source,
    )
    game.world.clocks.append(clock)
    spawn_keyed_scenes_for_clock(game.narrative, clock)
    log(
        f"[Clock] spawned '{clock_name}' (type={entry.clock_type}, segments={clocks_cfg.default_segments}) "
        f"from random-event focus '{event.focus}'"
    )


def _name_from_mythic_pair(action: str, subject: str) -> str:
    return f"{action} {subject}"


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
