"""Dice rolls, mechanical consequences, clocks, momentum burn, consequence sentences."""

from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, ClockEvent, GameState, RollResult
from ..npc import find_npc, normalize_for_match

from .impacts import impact_label


# DICE


def roll_action(stat_name: str, stat_value: int, move: str) -> RollResult:
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    c1, c2 = random.randint(1, 10), random.randint(1, 10)
    score = min(d1 + d2 + stat_value, 10)
    if score > c1 and score > c2:
        result = "STRONG_HIT"
    elif score > c1 or score > c2:
        result = "WEAK_HIT"
    else:
        result = "MISS"
    return RollResult(d1, d2, c1, c2, stat_name, stat_value, score, result, move, match=(c1 == c2))


def roll_progress(track_name: str, filled_boxes: int, move: str) -> RollResult:
    """Progress roll: filled_boxes (0–10) vs 2d10 challenge dice. No action dice."""
    c1, c2 = random.randint(1, 10), random.randint(1, 10)
    score = min(filled_boxes, 10)
    if score > c1 and score > c2:
        result = "STRONG_HIT"
    elif score > c1 or score > c2:
        result = "WEAK_HIT"
    else:
        result = "MISS"
    return RollResult(
        d1=0,
        d2=0,
        c1=c1,
        c2=c2,
        stat_name=track_name,
        stat_value=filled_boxes,
        action_score=score,
        result=result,
        move=move,
        match=(c1 == c2),
    )


# CLOCKS


def tick_threat_clock(game: GameState, ticks: int, clock_events: list[ClockEvent]) -> None:
    """Advance the first unfilled threat clock by ticks. Fire if full."""
    for clock in game.world.clocks:
        if clock.clock_type == "threat" and clock.filled < clock.segments:
            clock.filled = min(clock.segments, clock.filled + ticks)
            if clock.filled >= clock.segments:
                clock.fired = True
                clock.fired_at_scene = game.narrative.scene_count
                clock_events.append(
                    ClockEvent(
                        clock=clock.name,
                        trigger=clock.trigger_description,
                        autonomous=False,
                        triggered=True,
                    )
                )
            break


def can_burn_momentum(game: GameState, roll: RollResult) -> str | None:
    """Check if momentum burn can upgrade the result. Returns new result or None."""
    mom = game.resources.momentum
    if mom <= 0:
        return None
    if roll.result == "MISS" and mom > roll.c1 and mom > roll.c2:
        return "STRONG_HIT"
    if roll.result == "MISS" and (mom > roll.c1 or mom > roll.c2):
        return "WEAK_HIT"
    if roll.result == "WEAK_HIT" and mom > roll.c1 and mom > roll.c2:
        return "STRONG_HIT"
    return None


def check_npc_agency(game: GameState) -> tuple[list[str], list[ClockEvent]]:
    """Advance NPC-owned clocks at configured interval. Returns (actions, clock_events)."""
    if game.narrative.scene_count % eng().pacing.npc_agency_interval != 0:
        return [], []
    _defaults = eng().ai_text.narrator_defaults
    actions: list[str] = []
    clock_events: list[ClockEvent] = []
    for npc in game.npcs:
        if npc.status == "active" and npc.agenda:
            actions.append(_defaults["npc_agency_action_template"].format(npc_name=npc.name, agenda=npc.agenda))
            npc_norms = {normalize_for_match(npc.name)}
            npc_norms.update(normalize_for_match(a) for a in npc.aliases)
            for clock in game.world.clocks:
                if (
                    clock.clock_type in ("scheme", "threat")
                    and clock.owner not in ("", "world")
                    and normalize_for_match(clock.owner) in npc_norms
                    and clock.filled < clock.segments
                ):
                    clock.filled += 1
                    triggered = clock.filled >= clock.segments
                    if triggered:
                        clock.fired = True
                        clock.fired_at_scene = game.narrative.scene_count
                        actions.append(
                            _defaults["clock_filled_template"].format(
                                clock_name=clock.name, trigger=clock.trigger_description
                            )
                        )
                    event = ClockEvent(
                        clock=clock.name,
                        trigger=clock.trigger_description,
                        autonomous=False,
                        triggered=triggered,
                    )
                    clock_events.append(event)
                    status = "TRIGGERED" if triggered else f"{clock.filled}/{clock.segments}"
                    log(f"[Clock] NPC agency tick: '{clock.name}' by '{npc.name}' → {status}")
    return actions, clock_events


def tick_autonomous_clocks(game: GameState) -> list[ClockEvent]:
    """Autonomously advance threat clocks by chance each scene."""
    tick_chance = eng().pacing.autonomous_clock_tick_chance
    ticked: list[ClockEvent] = []
    for clock in game.world.clocks:
        if clock.clock_type != "threat":
            continue
        if clock.filled >= clock.segments:
            continue
        if clock.owner not in ("", "world"):
            continue
        if random.random() < tick_chance:
            clock.filled = min(clock.segments, clock.filled + 1)
            triggered = clock.filled >= clock.segments
            if triggered:
                clock.fired = True
                clock.fired_at_scene = game.narrative.scene_count
            event = ClockEvent(
                clock=clock.name,
                trigger=clock.trigger_description,
                autonomous=True,
                triggered=triggered,
            )
            ticked.append(event)
            status = "TRIGGERED" if triggered else f"{clock.filled}/{clock.segments}"
            log(f"[Clock] Autonomous tick: '{clock.name}' → {status}")
    return ticked


def purge_old_fired_clocks(game: GameState, keep_scenes: int | None = None) -> None:
    """Remove fired clocks that triggered more than keep_scenes scenes ago."""
    if keep_scenes is None:
        keep_scenes = eng().pacing.fired_clock_keep_scenes
    before = len(game.world.clocks)
    game.world.clocks = [
        c for c in game.world.clocks if not c.fired or (game.narrative.scene_count - c.fired_at_scene) <= keep_scenes
    ]
    purged = before - len(game.world.clocks)
    if purged:
        log(f"[Clock] Purged {purged} expired fired clock(s) at scene {game.narrative.scene_count}")


def pick_template(key: str) -> str:
    """Pick a random template string from engine.yaml consequence_templates.

    Strict: raises KeyError if the key is missing from yaml. Every template key
    the engine ever references must be present under `consequence_templates`.
    """
    templates = eng().get_raw("consequence_templates")
    options = templates[key]
    if isinstance(options, str):
        return options
    return random.choice(options)


def generate_consequence_sentences(
    consequences: list[str],
    clock_events: list[ClockEvent],
    game: GameState,
    brain: BrainResult,
) -> list[str]:
    """Generate narrative sentences for mechanical consequences.

    Each mechanical consequence (e.g. "health -2") gets a concrete sentence
    from engine.yaml templates. The narrator receives these as <consequence>
    tags and must weave them into prose.
    """
    target = find_npc(game, brain.target_npc) if brain.target_npc else None
    player = game.player_name
    npc_name = target.name if target else ""
    location = game.world.current_location or ""

    sentences: list[str] = []

    for cons in consequences:
        sentence = resolve_consequence_sentence(cons, player, npc_name, location)
        if sentence:
            sentences.append(sentence)

    for event in clock_events:
        tpl = pick_template("clock_triggered" if event.triggered else "clock_tick")
        sentences.append(
            tpl.format(
                player=player, npc=npc_name, location=location, clock=event.clock, trigger=event.trigger, amount=""
            )
        )

    return sentences


def _resolve_impact_marker(cons: str, fmt: dict) -> str | None:
    """Handle 'mark <impact>' and 'clear <impact>'. Returns None if not an impact marker."""
    if cons.startswith("mark "):
        fmt["impact"] = impact_label(cons[5:].strip())
        return pick_template("impact_mark").format(**fmt)
    if cons.startswith("clear "):
        fmt["impact"] = impact_label(cons[6:].strip())
        return pick_template("impact_clear").format(**fmt)
    return None


def _resolve_bond_delta(cons: str, fmt: dict) -> str:
    """'<Name> bond +N' / '<Name> bond -N' → bond_gain/bond_loss template."""
    bond_npc = cons.split("bond")[0].strip()
    if bond_npc:
        fmt["npc"] = bond_npc
    tpl_key = "bond_loss" if "-" in cons.split()[-1] else "bond_gain"
    return pick_template(tpl_key).format(**fmt)


def _resolve_resource_loss(track: str, cons: str, delta: str, fmt: dict) -> str:
    """Resource reduction: health/spirit (severity-scaled), supply, momentum."""
    try:
        amount = int(delta.replace("-", ""))
    except ValueError:
        amount = 1
    fmt["amount"] = str(amount)
    severity = "heavy" if amount >= 2 else "light"

    if track in ("health", "spirit"):
        return pick_template(f"{track}_{severity}").format(**fmt)
    if track == "supply" or "supply" in cons:
        return pick_template("supply_any").format(**fmt)
    if track == "momentum":
        return pick_template("momentum_loss").format(**fmt)
    return ""


def _resolve_resource_gain(track: str, cons: str, fmt: dict) -> str:
    """Resource increase: health/spirit, supply, momentum."""
    if track in ("health", "spirit"):
        return pick_template(f"{track}_gain").format(**fmt)
    if track == "supply" or "supply" in cons:
        return pick_template("supply_gain").format(**fmt)
    if track == "momentum":
        return pick_template("momentum_gain").format(**fmt)
    return ""


def resolve_consequence_sentence(cons: str, player: str, npc_name: str, location: str) -> str:
    """Resolve a single mechanical consequence string to a narrative sentence.

    Recognises impact markers ('mark wounded' / 'clear wounded'), bond deltas
    ('Kira bond +1'), resource changes ('health -2', 'momentum +1'), and
    compound consequences ('supply -1, health -1').
    """
    fmt: dict = {"player": player, "npc": npc_name, "location": location, "amount": ""}

    impact_sentence = _resolve_impact_marker(cons, fmt)
    if impact_sentence is not None:
        return impact_sentence

    parts = cons.split()
    if len(parts) >= 2:
        track = parts[0].lower()
        delta = parts[-1]

        if "bond" in cons.lower():
            return _resolve_bond_delta(cons, fmt)
        if "-" in delta:
            return _resolve_resource_loss(track, cons, delta, fmt)
        if "+" in delta:
            return _resolve_resource_gain(track, cons, fmt)

    # Compound: "supply -1, health -1"
    if "," in cons:
        sub_sentences = []
        for sub in cons.split(","):
            sub = sub.strip()
            if sub:
                s = resolve_consequence_sentence(sub, player, npc_name, location)
                if s:
                    sub_sentences.append(s)
        return " ".join(sub_sentences)

    return ""
