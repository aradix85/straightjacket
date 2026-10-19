from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any

from ..logging_util import log
from ..models import CharacterListEntry, GameState, RandomEvent, ThreadEntry
from ..prompt_loader import get_prompt
from .clocks import spawn_emergent_clock
from .config import gm
from .keyed_scenes import add_keyed_scene, has_keyed_scene_from
from .mythic_data import load_mythic
from .npc.matching import find_npc
from .questions import answers
from .spawn_sources import RANDOM_EVENT_SOURCE_PREFIX

_pending_events: list[RandomEvent] = []


def drain_pending_events() -> list[RandomEvent]:
    events = list(_pending_events)
    _pending_events.clear()
    return events


def roll_event_focus() -> str:
    table = load_mythic()["event_focus"]
    roll = random.randint(1, gm().mythic_dice.event_focus_die)

    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            focus: str = entry["focus"]
            return focus

    raise ValueError(f"event_focus table has no entry covering roll={roll}")


def roll_meaning_table(table_name: str) -> tuple[str, str]:
    data = load_mythic()
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
    cfg = gm().random_events

    if focus in cfg.threat_eligible_focus_categories:
        open_dangers = [d for d in answers().dangers(game) if d.open]
        if open_dangers and random.random() < cfg.threat_target_probability:
            danger = random.choice(open_dangers)
            log(f"[RandomEvent] Threat-eligible focus '{focus}' → targeting danger '{danger.name}'")
            return danger.name, danger.id

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
    cfg = gm().random_events

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
    spawn_danger_from_random_event(game, event)
    spawn_clock_from_random_event(game, event)

    return event


def spawn_keyed_scene_from_random_event(game: GameState, event: RandomEvent) -> None:
    cfg = gm().random_events
    if event.focus not in cfg.keyed_scene_mapping:
        return
    if not event.target_id:
        return
    source = f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{event.target_id}"
    if has_keyed_scene_from(game.narrative, source):
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

    scene = add_keyed_scene(
        game.narrative,
        trigger_type=entry.trigger_type,
        trigger_value=trigger_value,
        priority=entry.priority,
        narrative_hint=entry.narrative_hint,
        source=source,
    )
    log(
        f"[RandomEvent] spawned keyed-scene '{scene.id}' from focus '{event.focus}' "
        f"target_id='{event.target_id}' (trigger {entry.trigger_type}={trigger_value!r}, "
        f"priority={entry.priority})"
    )


def spawn_danger_from_random_event(game: GameState, event: RandomEvent) -> None:
    if event.focus not in gm().random_events.danger_foci:
        return
    answers().add_danger(
        game,
        event.focus,
        f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{event.target_id or event.focus}",
        (_mythic_pair("block_mythic_pair_name", event), _mythic_pair("block_mythic_pair", event)),
    )


def spawn_clock_from_random_event(game: GameState, event: RandomEvent) -> None:
    cfg = gm().random_events
    if event.focus not in cfg.clock_creation_mapping:
        return

    spawn_emergent_clock(
        game,
        base_name=_mythic_pair("block_mythic_pair_name", event),
        clock_type=cfg.clock_creation_mapping[event.focus].clock_type,
        trigger_description=_mythic_pair("block_mythic_pair", event),
        source=f"{RANDOM_EVENT_SOURCE_PREFIX}{event.focus}:{event.target_id or event.focus}",
    )


def _mythic_pair(template: str, event: RandomEvent) -> str:
    return get_prompt(template, action=event.meaning_action, subject=event.meaning_subject)


def _add_weight(entries: Sequence[ThreadEntry] | Sequence[CharacterListEntry], entry_id: str, label: str) -> None:
    cap = gm().random_events.list_weight_max
    for entry in entries:
        if entry.id == entry_id and entry.active:
            if entry.weight < cap:
                entry.weight += 1
                log(f"[Lists] {label} '{entry.name}' weight → {entry.weight}")
            return


def add_thread_weight(game: GameState, thread_id: str) -> None:
    _add_weight(game.narrative.threads, thread_id, "Thread")


def add_character(game: GameState, character_id: str, name: str, entry_type: str, weight: int) -> None:
    game.narrative.characters_list.append(
        CharacterListEntry(id=character_id, name=name, entry_type=entry_type, weight=weight, active=True, ac_status="")
    )


def add_character_weight(game: GameState, character_id: str) -> None:
    _add_weight(game.narrative.characters_list, character_id, "Character")


def _consolidate(entries: Sequence[ThreadEntry] | Sequence[CharacterListEntry], label: str) -> None:
    cfg = gm().random_events
    active = [e for e in entries if e.active]
    if len(active) < cfg.consolidation_threshold:
        return
    for entry in active:
        entry.weight = (
            cfg.consolidation_weight_low
            if entry.weight >= cfg.consolidation_weight_high
            else cfg.consolidation_weight_default
        )
    log(f"[Lists] Consolidated {len(active)} {label}")


def consolidate_lists(game: GameState) -> None:
    _consolidate(game.narrative.threads, "threads")
    _consolidate(game.narrative.characters_list, "characters")
