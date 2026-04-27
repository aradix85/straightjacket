from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, ClockEvent, GameState, RollResult
from ..npc import find_npc, normalize_for_match

from .impacts import impact_label


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


def tick_threat_clock(game: GameState, ticks: int, clock_events: list[ClockEvent]) -> None:
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
    templates = eng().get_raw("consequence_templates")
    options = templates[key]
    if isinstance(options, str):
        return options
    return random.choice(options)


def _classify(cons: str, default_npc: str) -> tuple[str, str, str] | None:
    if cons.startswith("mark "):
        return "impact_mark", "", impact_label(cons[5:].strip())
    if cons.startswith("clear "):
        return "impact_clear", "", impact_label(cons[6:].strip())

    parts = cons.split()
    if len(parts) >= 2 and "bond" in cons.lower():
        bond_npc = cons.split("bond")[0].strip()
        subject = bond_npc or default_npc
        delta = parts[-1]
        return ("bond_loss" if "-" in delta else "bond_gain", subject, "")

    if len(parts) >= 2:
        track = parts[0].lower()
        delta = parts[-1]
        if "-" in delta:
            try:
                amount = int(delta.replace("-", ""))
            except ValueError:
                amount = 1
            severity = "heavy" if amount >= 2 else "light"
            if track in ("health", "spirit"):
                return f"{track}_{severity}", "", ""
            if track == "supply" or "supply" in cons:
                return "supply_any", "", ""
            if track == "momentum":
                return "momentum_loss", "", ""
            return None
        if "+" in delta:
            if track in ("health", "spirit"):
                return f"{track}_gain", "", ""
            if track == "supply" or "supply" in cons:
                return "supply_gain", "", ""
            if track == "momentum":
                return "momentum_gain", "", ""
            return None
    return None


def generate_consequence_sentences(
    consequences: list[str],
    clock_events: list[ClockEvent],
    game: GameState,
    brain: BrainResult,
) -> list[str]:
    target = find_npc(game, brain.target_npc) if brain.target_npc else None
    player = game.player_name
    npc_name = target.name if target else ""
    location = game.world.current_location

    sentences: list[str] = []

    for cons in consequences:
        sentence = resolve_consequence_sentence(cons, player, npc_name, location)
        if sentence:
            sentences.append(sentence)

    for ev in clock_events:
        key = "clock_triggered" if ev.triggered else "clock_tick"
        tpl = pick_template(key)
        sentences.append(
            tpl.format(player=player, npc=npc_name, location=location, clock=ev.clock, trigger=ev.trigger, amount="")
        )

    return sentences


def resolve_consequence_sentence(cons: str, player: str, npc_name: str, location: str) -> str:
    if "," in cons:
        parts = []
        for sub in cons.split(","):
            sub = sub.strip()
            if not sub:
                continue
            s = resolve_consequence_sentence(sub, player, npc_name, location)
            if s:
                parts.append(s)
        return " ".join(parts)

    classified = _classify(cons, npc_name)
    if classified is None:
        return ""

    event_code, subject_override, impact_text = classified
    fmt: dict = {
        "player": player,
        "npc": subject_override or npc_name,
        "location": location,
        "amount": "",
        "impact": impact_text,
    }
    return pick_template(event_code).format(**fmt)
