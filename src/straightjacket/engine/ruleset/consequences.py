from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.npc.matching import find_npc
from straightjacket.engine.ruleset.config import rules

if TYPE_CHECKING:
    from straightjacket.engine.models import BrainResult, ClockEvent, Consequence, GameState


def pick_template(key: str) -> str:
    return random.choice(eng().consequence_templates[key])


def _meter_event(meter: str, change: int) -> str | None:
    templates = eng().consequence_templates
    if change > 0:
        event = f"{meter}_gain"
    elif f"{meter}_heavy" in templates:
        event = f"{meter}_heavy" if -change >= rules().meters.heavy_loss_amount else f"{meter}_light"
    else:
        event = f"{meter}_any"
    return event if event in templates else None


_SENTENCE_EVENTS: dict[str, tuple[str, str | None, str | None]] = {
    "bond_progress": ("bond_gain", "name", None),
    "disposition_shift": ("disposition_shift", "name", None),
    "mark_impact": ("impact_mark", None, "impact"),
    "clear_impact": ("impact_clear", None, "impact"),
    "complication": ("complication_{kind}", None, None),
    "complication_clock": ("complication_clock", None, "name"),
    "complication_averted": ("complication_averted", None, "name"),
    "bond_sealed": ("bond_sealed", "name", None),
    "bond_tested": ("bond_tested", "name", None),
    "bond_cleared": ("bond_cleared", "name", None),
    "bond_request": ("bond_request", None, None),
    "obstacle": ("obstacle", None, None),
    "loyalty_test": ("loyalty_test", None, None),
    "milestone": ("milestone", None, None),
    "recommit": ("recommit", None, "track"),
}


def _sentence_event(c: Consequence) -> tuple[str, str, str] | None:
    values = c.values
    event: str | None
    if c.kind in {"track_gain", "track_loss"}:
        event = _meter_event(values["track"], values["n"] if c.kind == "track_gain" else -values["n"])
        return (event, "", "") if event else None
    if c.kind == "momentum_change":
        if values["n"] == 0:
            return None
        return ("momentum_gain" if values["n"] > 0 else "momentum_loss"), "", ""
    if c.kind not in _SENTENCE_EVENTS:
        return None
    event, subject, detail = _SENTENCE_EVENTS[c.kind]
    return event.format(**values), values[subject] if subject else "", values[detail] if detail else ""


def _target_name(game: GameState, brain: BrainResult) -> str:
    target = find_npc(game, brain.target_npc) if brain.target_npc else None
    return target.name if target else ""


def consequence_texts(consequences: list[Consequence], game: GameState, brain: BrainResult) -> list[str]:
    npc_name = _target_name(game, brain)
    location = game.world.current_location
    return [
        c.label if _sentence_event(c) is None else resolve_consequence_sentence(c, game.player_name, npc_name, location)
        for c in consequences
    ]


def generate_consequence_sentences(
    consequences: list[Consequence],
    clock_events: list[ClockEvent],
    game: GameState,
    brain: BrainResult,
) -> list[str]:
    player = game.player_name
    npc_name = _target_name(game, brain)
    location = game.world.current_location

    sentences: list[str] = []

    for c in consequences:
        sentence = resolve_consequence_sentence(c, player, npc_name, location)
        if sentence:
            sentences.append(sentence)

    for ev in clock_events:
        key = "clock_triggered" if ev.triggered else "clock_tick"
        tpl = pick_template(key)
        sentences.append(
            tpl.format(player=player, npc=npc_name, location=location, clock=ev.clock, trigger=ev.trigger, amount="")
        )

    return sentences


def resolve_consequence_sentence(c: Consequence, player: str, npc_name: str, location: str) -> str:
    event = _sentence_event(c)
    if event is None:
        return ""
    event_code, subject, detail = event
    fmt: dict[str, Any] = {
        "player": player,
        "npc": subject or npc_name,
        "location": location,
        "amount": "",
        "impact": detail,
        "danger": detail,
    }
    return pick_template(event_code).format(**fmt)
