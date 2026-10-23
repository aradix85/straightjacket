from __future__ import annotations

import random
from typing import Any

from ..engine_loader import eng
from ..gamemaster.npc.matching import find_npc
from ..models import BrainResult, ClockEvent, Consequence, GameState
from .config import rules


def pick_template(key: str) -> str:
    result: str = random.choice(eng().get_raw("consequence_templates")[key])
    return result


def _meter_event(meter: str, change: int) -> str | None:
    templates = eng().get_raw("consequence_templates")
    if change > 0:
        event = f"{meter}_gain"
    elif f"{meter}_heavy" in templates:
        event = f"{meter}_heavy" if -change >= rules().meters.heavy_loss_amount else f"{meter}_light"
    else:
        event = f"{meter}_any"
    return event if event in templates else None


def _sentence_event(c: Consequence) -> tuple[str, str, str] | None:
    values = c.values
    event: str | None
    if c.kind in ("track_gain", "track_loss"):
        event = _meter_event(values["track"], values["n"] if c.kind == "track_gain" else -values["n"])
        return (event, "", "") if event else None
    if c.kind == "momentum_change":
        if values["n"] == 0:
            return None
        return ("momentum_gain" if values["n"] > 0 else "momentum_loss"), "", ""
    if c.kind == "bond_progress":
        return "bond_gain", values["name"], ""
    if c.kind == "disposition_shift":
        return "disposition_shift", values["name"], ""
    if c.kind in ("mark_impact", "clear_impact"):
        return ("impact_mark" if c.kind == "mark_impact" else "impact_clear"), "", values["impact"]
    if c.kind == "complication":
        return f"complication_{values['kind']}", "", ""
    if c.kind in ("complication_clock", "complication_averted"):
        return c.kind, "", values["name"]
    if c.kind in ("bond_sealed", "bond_tested"):
        return c.kind, values["name"], ""
    if c.kind in ("bond_request", "obstacle", "loyalty_test"):
        return c.kind, "", ""
    if c.kind == "bond_cleared":
        return "bond_cleared", values["name"], ""
    if c.kind == "recommit":
        return "recommit", "", values["track"]
    return None


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
