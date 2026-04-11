#!/usr/bin/env python3
"""Dice rolls, mechanical consequences, clocks, momentum burn, consequence sentences."""

from __future__ import annotations

import random

from ...i18n import E
from ..config_loader import _ConfigNode
from ..engine_loader import damage, eng
from ..logging_util import log
from ..models import BrainResult, ClockEvent, GameState, NpcData, Resources, RollResult
from ..npc import find_npc, normalize_for_match


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


def _move_set(category: str) -> set[str]:
    """Read a move category set from engine.yaml move_categories."""
    return set(eng().move_categories.get(category, []))


# CONSEQUENCES


def apply_consequences(
    game: GameState, roll: RollResult, brain: BrainResult, position: str, effect: str
) -> tuple[list[str], list[ClockEvent]]:
    """Apply mechanical consequences. Position scales severity.
    All damage values and move categories come from engine.yaml."""
    consequences: list[str] = []
    clock_events: list[ClockEvent] = []
    tid = brain.target_npc
    target = find_npc(game, tid) if tid else None
    _e = eng()
    res = game.resources

    if roll.move in _move_set("social") and target is None:
        log(
            f"[Consequences] Social move '{roll.move}' has no resolvable target "
            f"(target_npc={tid!r}) — bond/disposition effects skipped",
            level="warning",
        )

    if roll.result == "MISS":
        _apply_miss(res, roll, brain, target, position, consequences, _e)

        mom_loss = damage("momentum.loss", position)
        res.adjust_momentum(-mom_loss, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        consequences.append(f"momentum -{mom_loss}")

        clock_ticks = damage("damage.miss.clock_ticks", position)
        if clock_ticks > 0:
            _tick_threat_clock(game, clock_ticks, clock_events)

    elif roll.result == "WEAK_HIT":
        res.adjust_momentum(+_e.momentum.gain.weak_hit, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        if roll.move in _move_set("bond_on_weak_hit") and target:
            target.bond = min(target.bond_max, target.bond + 1)
        _apply_recovery(res, roll.move, _e.recovery.weak_hit, _e, consequences)

        # Threat clock pressure: controlled=no tick, risky=probabilistic, desperate=guaranteed
        if position != "controlled":
            should_tick = (position == "desperate") or (random.random() < _e.pacing.weak_hit_clock_tick_chance)
            if should_tick:
                _tick_threat_clock(game, 1, clock_events)

    else:  # STRONG_HIT
        mom_gain = damage("momentum.gain.strong_hit", effect)
        res.adjust_momentum(+mom_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        if roll.move in _move_set("bond_on_strong_hit") and target:
            target.bond = min(target.bond_max, target.bond + 1)
        if roll.move in _move_set("disposition_shift_on_strong_hit") and target:
            shifts = dict(_e.disposition_shifts.items())
            target.disposition = shifts.get(target.disposition, target.disposition)
        _apply_recovery(res, roll.move, damage("recovery.strong_hit", effect), _e, consequences)

    # --- Crisis check -----------------
    if res.health <= 0 and res.spirit <= 0:
        game.game_over = True
        game.crisis_mode = True
    elif res.health <= 0 or res.spirit <= 0:
        game.crisis_mode = True
    else:
        game.crisis_mode = False

    return consequences, clock_events


# ── Consequence helpers ───────────────────────────────────────


def _miss_endure_map() -> dict[str, str]:
    """Read miss endure move→track mapping from engine.yaml."""
    return dict(eng().move_routing.miss_endure.items())


def _apply_miss(
    res: Resources,
    roll: RollResult,
    brain: BrainResult,
    target: NpcData | None,
    position: str,
    consequences: list[str],
    _e: _ConfigNode,
) -> None:
    """Apply miss-specific damage based on move category."""
    move = roll.move

    # Endure moves: single-track damage
    miss_endure = _miss_endure_map()
    if move in miss_endure:
        track = miss_endure[move]
        dmg = damage("damage.miss.endure", position)
        lost = res.damage(track, dmg)
        if lost:
            consequences.append(f"{track} -{lost}")

    # Combat: health damage
    elif move in _move_set("combat"):
        dmg = damage("damage.miss.combat", position)
        lost = res.damage("health", dmg)
        if lost:
            consequences.append(f"health -{lost}")

    # Social: bond loss + spirit damage
    elif move in _move_set("social"):
        if target:
            bond_loss = damage("damage.miss.social.bond", position)
            old_bond = target.bond
            target.bond = max(0, target.bond - bond_loss)
            if target.bond < old_bond:
                consequences.append(f"{target.name} bond -{old_bond - target.bond}")
        dmg = damage("damage.miss.social.spirit", position)
        lost = res.damage("spirit", dmg)
        if lost:
            consequences.append(f"spirit -{lost}")

    # Everything else: supply + optional health
    else:
        parts = []
        supply_loss = damage("damage.miss.other.supply", position)
        lost_su = res.damage("supply", supply_loss)
        if lost_su:
            parts.append(f"supply -{lost_su}")
        health_loss = damage("damage.miss.other.health", position)
        if health_loss > 0:
            lost_h = res.damage("health", health_loss)
            if lost_h:
                parts.append(f"health -{lost_h}")
        if parts:
            consequences.append(", ".join(parts))


def _recovery_moves_map() -> dict[str, tuple[str, str]]:
    """Read recovery move→(track, cap_attr) mapping from engine.yaml."""
    raw = eng().move_routing.recovery
    result = {}
    for move in raw:
        entry = raw[move]
        result[move] = (entry.track, entry.cap)
    return result


def _apply_recovery(res: Resources, move: str, amount: int, _e: _ConfigNode, consequences: list[str]) -> None:
    """Apply recovery healing for endure/resupply moves."""
    recovery_map = _recovery_moves_map()
    entry = recovery_map.get(move)
    if not entry:
        return
    track, cap_attr = entry
    cap = getattr(_e.resources, cap_attr)
    gained = res.heal(track, amount, cap=cap)
    if gained:
        consequences.append(f"{track} +{gained}")


def _tick_threat_clock(game: GameState, ticks: int, clock_events: list[ClockEvent]) -> None:
    """Advance the first unfilled threat clock by ticks. Fire if full."""
    for clock in game.world.clocks:
        if clock.clock_type == "threat" and clock.filled < clock.segments:
            clock.filled = min(clock.segments, clock.filled + ticks)
            if clock.filled >= clock.segments:
                clock.fired = True
                clock.fired_at_scene = game.narrative.scene_count
                clock_events.append(ClockEvent(clock=clock.name, trigger=clock.trigger_description))
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


# ── NPC agency & autonomous clocks ────────────────────────────


def check_npc_agency(game: GameState) -> tuple[list[str], list[ClockEvent]]:
    """Advance NPC-owned clocks every 5th scene. Returns (actions, clock_events)."""
    if game.narrative.scene_count % 5 != 0:
        return [], []
    actions: list[str] = []
    clock_events: list[ClockEvent] = []
    for npc in game.npcs:
        if npc.status == "active" and npc.agenda:
            actions.append(f'NPC "{npc.name}" pursues agenda "{npc.agenda}" {E["dash"]} concrete offscreen action.')
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
                        actions.append(f'CLOCK FILLED "{clock.name}": {clock.trigger_description}')
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


# ── Consequence sentence generation (step 4) ────────────────


def _pick_template(key: str, fallback: str = "") -> str:
    """Pick a random template string from engine.yaml consequence_templates."""
    templates = eng().get("consequence_templates", {})
    options = templates.get(key, [])
    if not options:
        return fallback
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
        sentence = _resolve_consequence_sentence(cons, player, npc_name, location)
        if sentence:
            sentences.append(sentence)

    for event in clock_events:
        if event.triggered:
            tpl = _pick_template("clock_triggered", f"Time's up: {event.clock}.")
            sentences.append(
                tpl.format(
                    player=player, npc=npc_name, location=location, clock=event.clock, trigger=event.trigger, amount=""
                )
            )
        else:
            tpl = _pick_template("clock_tick")
            if tpl:
                sentences.append(
                    tpl.format(
                        player=player,
                        npc=npc_name,
                        location=location,
                        clock=event.clock,
                        trigger=event.trigger,
                        amount="",
                    )
                )

    return sentences


def _resolve_consequence_sentence(cons: str, player: str, npc_name: str, location: str) -> str:
    """Resolve a single mechanical consequence string to a narrative sentence."""
    fmt = {"player": player, "npc": npc_name, "location": location, "amount": ""}

    # Parse "track -N" or "track +N" pattern
    parts = cons.split()
    if len(parts) >= 2:
        track = parts[0].lower()
        delta = parts[-1]

        # "Kira bond -1" → track=bond, npc=Kira
        if "bond" in cons.lower():
            if "-" in delta:
                tpl = _pick_template("bond_loss")
                # Extract NPC name from "Name bond -N"
                bond_npc = cons.split("bond")[0].strip()
                if bond_npc:
                    fmt["npc"] = bond_npc
            else:
                tpl = _pick_template("bond_gain")
                bond_npc = cons.split("bond")[0].strip()
                if bond_npc:
                    fmt["npc"] = bond_npc
            if tpl:
                return tpl.format(**fmt)
            return ""

        if "-" in delta:
            try:
                amount = int(delta.replace("-", ""))
            except ValueError:
                amount = 1
            fmt["amount"] = str(amount)
            severity = "heavy" if amount >= 2 else "light"

            if track in ("health", "spirit"):
                tpl = _pick_template(f"{track}_{severity}")
            elif track == "supply" or "supply" in cons:
                tpl = _pick_template("supply_any")
            elif track == "momentum":
                tpl = _pick_template("momentum_loss")
            else:
                tpl = ""

            if tpl:
                return tpl.format(**fmt)

        elif "+" in delta:
            if track in ("health", "spirit"):
                tpl = _pick_template(f"{track}_gain")
            elif track == "supply" or "supply" in cons:
                tpl = _pick_template("supply_gain")
            elif track == "momentum":
                tpl = _pick_template("momentum_gain")
            else:
                tpl = ""

            if tpl:
                return tpl.format(**fmt)

    # Compound: "supply -1, health -1"
    if "," in cons:
        sub_sentences = []
        for sub in cons.split(","):
            sub = sub.strip()
            if sub:
                s = _resolve_consequence_sentence(sub, player, npc_name, location)
                if s:
                    sub_sentences.append(s)
        return " ".join(sub_sentences)

    return ""
