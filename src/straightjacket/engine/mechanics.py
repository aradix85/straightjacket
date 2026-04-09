#!/usr/bin/env python3
"""Straightjacket game mechanics: chaos, time/location, pacing, dice, consequences."""

from __future__ import annotations

import random

from ..i18n import E
from .config_loader import _ConfigNode
from .engine_loader import damage, eng
from .logging_util import log
from .models import BrainResult, ClockEvent, GameState, NpcData, Resources, RollResult
from .npc import find_npc, normalize_for_match

# LOCATION MATCHING

_LOC_STOP = {"in", "the", "of", "at", "near"}


def locations_match(loc_a: str, loc_b: str) -> bool:
    """Fuzzy location comparison for deduplication and spatial guards.

    Empty/blank input is treated as 'unspecified' and matches anything — this
    prevents false negatives when the engine hasn't established a location yet.
    """
    if not loc_a or not loc_b:
        return True

    def _words(s: str) -> list[str]:
        return [w for w in s.replace("_", " ").strip().lower().split() if w not in _LOC_STOP]

    wa, wb = _words(loc_a), _words(loc_b)
    if not wa or not wb:
        return False
    if wa == wb:
        return True
    shorter, longer = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(shorter) >= 2:
        return set(shorter).issubset(set(longer))
    return shorter[0] == longer[0]


# CHAOS FACTOR SYSTEM


def update_chaos_factor(game: GameState, result: str) -> None:
    """Adjust chaos factor based on roll result."""
    _e = eng()
    if result == "MISS":
        game.world.tick_chaos(+1, floor=_e.chaos.min, ceiling=_e.chaos.max)
    elif result == "STRONG_HIT":
        game.world.tick_chaos(-1, floor=_e.chaos.min, ceiling=_e.chaos.max)


def check_chaos_interrupt(game: GameState) -> str | None:
    """Roll against chaos factor to see if a scene interrupt triggers."""
    _e = eng()
    threshold = game.world.chaos_factor - 3
    if threshold <= 0:
        return None
    roll = random.randint(1, 10)
    if roll <= threshold:
        game.world.tick_chaos(-1, floor=_e.chaos.min, ceiling=_e.chaos.max)
        return random.choice(_e.chaos.interrupt_types)
    return None


# TEMPORAL & SPATIAL CONSISTENCY

TIME_PHASES = ["early_morning", "morning", "midday", "afternoon", "evening", "late_evening", "night", "deep_night"]


def advance_time(game: GameState, progression: str) -> None:
    """Advance time_of_day based on Brain's time_progression assessment."""
    if not game.world.time_of_day or progression in ("none", "short"):
        return
    try:
        idx = TIME_PHASES.index(game.world.time_of_day)
    except ValueError:
        return
    steps = {"moderate": 1, "long": 2}.get(progression, 0)
    if steps:
        new_idx = (idx + steps) % len(TIME_PHASES)
        game.world.time_of_day = TIME_PHASES[new_idx]


def update_location(game: GameState, new_location: str) -> None:
    """Update current location and maintain location history."""
    if not new_location:
        return
    new_location = new_location.replace("_", " ").strip()
    if not new_location:
        return
    w = game.world
    # First location ever: just set it, no comparison needed
    if not w.current_location:
        w.current_location = new_location
        return
    if locations_match(new_location, w.current_location):
        return
    if w.location_history:
        if locations_match(w.location_history[-1], w.current_location):
            w.location_history[-1] = w.current_location
        else:
            w.location_history.append(w.current_location)
    else:
        w.location_history.append(w.current_location)
    w.location_history = w.location_history[-5:]
    w.current_location = new_location


def apply_brain_location_time(game: GameState, brain: BrainResult) -> None:
    """Apply location change and engine-resolved time progression."""
    loc = brain.location_change
    has_location_change = bool(loc and loc != "null")
    if loc and has_location_change:
        update_location(game, loc)
    time_prog = resolve_time_progression(brain.move, has_location_change)
    advance_time(game, time_prog)


# POSITION / EFFECT / TIME RESOLVERS (step 2)


def resolve_position(game: GameState, brain: BrainResult) -> str:
    """Engine-computed position from game state. Replaces Brain's position field.

    Weighted scoring: each factor adds a signed weight. Sum maps to position
    via thresholds. Situational overrides apply after the sum for edge cases.
    """
    _e = eng()
    pr = _e.position_resolver
    w = pr.weights
    score = 0

    # Resource pressure
    res = game.resources
    for val in (res.health, res.spirit, res.supply):
        if val < w.resource_critical_below:
            score += w.resource_critical
        elif val < w.resource_low_below:
            score += w.resource_low

    # NPC disposition + bond (only when move targets an NPC)
    if brain.target_npc:
        target = find_npc(game, brain.target_npc)
        if target:
            disp_weights = {
                "hostile": w.npc_hostile,
                "distrustful": w.npc_distrustful,
                "friendly": w.npc_friendly,
                "loyal": w.npc_loyal,
            }
            score += disp_weights.get(target.disposition, 0)
            if target.bond >= 3:
                score += w.npc_bond_high
            elif target.bond <= 0:
                score += w.npc_bond_low

    # Chaos factor
    if game.world.chaos_factor >= 7:
        score += w.chaos_high
    elif game.world.chaos_factor <= 3:
        score += w.chaos_low

    # Recent roll momentum (consecutive results from session log)
    recent = game.narrative.session_log[-3:] if game.narrative.session_log else []
    recent_results = [e.result for e in recent if e.result]
    if len(recent_results) >= 2 and all(r == "MISS" for r in recent_results[-2:]):
        score += w.consecutive_misses
    elif len(recent_results) >= 2 and all(r == "STRONG_HIT" for r in recent_results[-2:]):
        score += w.consecutive_strong

    # Threat pressure (clocks at >= 75% filled)
    threat_penalty = 0
    for clock in game.world.clocks:
        if not clock.fired and clock.segments > 0 and clock.filled / clock.segments >= 0.75:
            threat_penalty += w.threat_clock_critical
    score += max(threat_penalty, w.threat_clock_critical * 2)  # cap at 2 clocks

    # Secured advantage (previous move was secure_advantage with a hit)
    if recent and recent[-1].move == "secure_advantage" and recent[-1].result in ("STRONG_HIT", "WEAK_HIT"):
        score += w.secured_advantage

    # Move category baseline
    move = brain.move
    cat = _move_category(move)
    baselines = pr.move_baselines
    score += baselines.get(cat, baselines.get("other", 0))

    # Map sum to position
    if score <= pr.desperate_below:
        position = "desperate"
    elif score >= pr.controlled_above:
        position = "controlled"
    else:
        position = "risky"

    # Situational overrides
    has_secured = recent and recent[-1].move == "secure_advantage" and recent[-1].result in ("STRONG_HIT", "WEAK_HIT")
    any_resource_critical = any(v < w.resource_critical_below for v in (res.health, res.spirit, res.supply))

    for override in pr.get("overrides", []):
        name = override.get("name", "")
        conditions = override.get("conditions", [])
        effect = override.get("effect", "")

        match = True
        for cond in conditions:
            if (
                cond == "secured_advantage"
                and not has_secured
                or cond == "any_resource_critical"
                and not any_resource_critical
                or cond == "crisis_mode"
                and not game.crisis_mode
                or cond == "recovery_move"
                and cat != "recovery"
                or cond == "previous_match"
                and not (recent and recent[-1].result and getattr(recent[-1], "match", False))
                or cond == "same_target_npc"
                and not (recent and brain.target_npc and getattr(recent[-1], "target_npc", None) == brain.target_npc)
            ):
                match = False

        if match and conditions:
            if (
                effect == "cap_at_risky"
                and position == "controlled"
                or effect == "floor_at_risky"
                and position == "controlled"
            ):
                position = "risky"
            elif effect == "floor_at_risky" and position == "desperate":
                # floor_at_risky means position can't go below risky
                pass  # desperate stays — floor means "at least risky", not "cap"
            elif effect == "shift_up_one":
                if position == "desperate":
                    position = "risky"
                elif position == "risky":
                    position = "controlled"
            log(f"[Position] Override '{name}' applied → {position}")

    log(f"[Position] score={score}, position={position} (move={move}, cat={cat})")
    return position


def resolve_effect(game: GameState, brain: BrainResult, position: str) -> str:
    """Engine-computed effect from game state + resolved position."""
    _e = eng()
    er = _e.effect_resolver
    w = er.weights
    score = 0

    # Position correlation
    pos_weights = {"desperate": w.desperate, "controlled": w.controlled}
    score += pos_weights.get(position, 0)

    # NPC bond (social moves)
    if brain.target_npc:
        target = find_npc(game, brain.target_npc)
        if target:
            if target.bond >= 3:
                score += w.bond_high
            elif target.bond <= 0:
                score += w.bond_low

    # Secured advantage
    recent = game.narrative.session_log[-1:] if game.narrative.session_log else []
    if recent and recent[0].move == "secure_advantage" and recent[0].result in ("STRONG_HIT", "WEAK_HIT"):
        score += w.secured_advantage

    # Move baseline
    baselines = er.move_baselines
    score += baselines.get(brain.move, baselines.get("other", 0))

    # Map to effect
    if score <= er.limited_below:
        effect = "limited"
    elif score >= er.great_above:
        effect = "great"
    else:
        effect = "standard"

    log(f"[Effect] score={score}, effect={effect} (position={position}, move={brain.move})")
    return effect


def resolve_time_progression(move: str, has_location_change: bool = False) -> str:
    """Engine-computed time progression from move type. No AI needed."""
    _e = eng()
    tmap = _e.time_progression_map
    if has_location_change:
        return tmap.get("_with_location_change", "long")
    return tmap.get(move, tmap.get("_default", "short"))


def _move_category(move: str) -> str:
    """Classify a move into its category for resolver lookups."""
    _e = eng()
    mc = _e.move_categories
    for cat in ("combat", "social", "endure", "recovery"):
        if move in mc.get(cat, []):
            return cat
    return "other"


# SCENE / SEQUEL PACING SYSTEM


def get_pacing_hint(game: GameState) -> str:
    """Analyze recent scene intensity and suggest pacing."""
    _e = eng()
    history = game.narrative.scene_intensity_history[-_e.pacing.window_size :]
    if not history:
        return "neutral"

    consecutive_intense = 0
    for h in reversed(history):
        if h in ("action", "interrupt"):
            consecutive_intense += 1
        else:
            break
    if consecutive_intense >= _e.pacing.intense_threshold:
        return "breather"

    consecutive_calm = 0
    for h in reversed(history):
        if h == "breather":
            consecutive_calm += 1
        else:
            break
    if consecutive_calm >= _e.pacing.calm_threshold:
        return "action"
    return "neutral"


def record_scene_intensity(game: GameState, scene_type: str) -> None:
    """Record a scene's intensity type for pacing analysis."""
    window = eng().pacing.window_size
    game.narrative.scene_intensity_history.append(scene_type)
    if len(game.narrative.scene_intensity_history) > window:
        game.narrative.scene_intensity_history = game.narrative.scene_intensity_history[-window:]


# KISHŌTENKETSU STRUCTURE SELECTION


def choose_story_structure(tone: str) -> str:
    """Choose between '3act' and 'kishotenketsu' based on tone probability."""
    _e = eng()
    kprob = _e.story.kishotenketsu_probability
    probability = kprob.get(tone, _e.story.kishotenketsu_default)
    return "kishotenketsu" if random.random() < probability else "3act"


# DICE & CONSEQUENCES


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

# Move → (track, damage_path) for miss damage routing.
_MISS_ENDURE = {"endure_harm": "health", "endure_stress": "spirit"}


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
    if move in _MISS_ENDURE:
        track = _MISS_ENDURE[move]
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


# Move → (track, resource_cap_attr) for recovery routing.
_RECOVERY_MOVES: dict[str, tuple[str, str]] = {
    "endure_harm": ("health", "health_max"),
    "endure_stress": ("spirit", "spirit_max"),
    "resupply": ("supply", "supply_max"),
}


def _apply_recovery(res: Resources, move: str, amount: int, _e: _ConfigNode, consequences: list[str]) -> None:
    """Apply recovery healing for endure/resupply moves."""
    entry = _RECOVERY_MOVES.get(move)
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


def purge_old_fired_clocks(game: GameState, keep_scenes: int = 3) -> None:
    """Remove fired clocks that triggered more than keep_scenes scenes ago."""
    before = len(game.world.clocks)
    game.world.clocks = [
        c for c in game.world.clocks if not c.fired or (game.narrative.scene_count - c.fired_at_scene) <= keep_scenes
    ]
    purged = before - len(game.world.clocks)
    if purged:
        log(f"[Clock] Purged {purged} expired fired clock(s) at scene {game.narrative.scene_count}")


# MEMORY EMOTIONAL WEIGHT DERIVATION


def derive_memory_emotion(move: str, result: str, disposition: str = "neutral") -> str:
    """Derive emotional_weight for an NPC memory from mechanical context.

    Uses engine.yaml memory_emotions table: (move_category, result) → base emotion,
    then appends disposition suffix. Falls back to 'neutral' for unknown combinations.
    """
    _e = eng()
    base_map = _e.memory_emotions.base
    suffix_map = _e.memory_emotions.disposition_suffix

    # Determine move category
    category = "other"
    for cat in ("combat", "social", "endure", "recovery"):
        cat_moves = _e.move_categories.get(cat, [])
        if move in cat_moves:
            category = cat
            break

    if move == "dialog" or result == "dialog":
        key = "dialog"
    else:
        key = f"{category}_{result}"

    base = base_map.get(key, "neutral")
    suffix = suffix_map.get(disposition, "")
    return base + suffix


# ENGINE-SIDE MEMORY GENERATION (step 3.1)


def generate_engine_memories(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    activated_npc_ids: set[str],
    consequences: list[str] | None = None,
) -> list[dict]:
    """Generate observation memories for activated NPCs from mechanical context.

    Replaces AI-generated memory_updates for known events. Engine knows:
    which NPCs were present, what move occurred, what the result was,
    what consequences applied. Templates from engine.yaml produce
    narrative-flavored memories the narrator can build on.
    """
    from .npc.memory import score_importance

    _e = eng()
    templates = _e.memory_templates
    result_text_map = _e.memory_result_text
    verb_map = _e.memory_move_verbs
    scene = game.narrative.scene_count

    move = brain.move
    result = roll.result if roll else "dialog"
    category = _move_category(move)
    intent = brain.player_intent or ""

    # Resolve template variables
    result_key = "dialog" if move == "dialog" else f"{category}_{result}"
    result_text = result_text_map.get(result_key, result_text_map.get("other_MISS", "something happened"))
    move_verb = verb_map.get(move, verb_map.get("_default", "acted"))

    if consequences:
        result_text += f" ({', '.join(consequences[:3])})"

    memories = []
    for npc in game.npcs:
        if npc.id not in activated_npc_ids:
            continue
        if npc.status not in ("active", "background"):
            continue

        # Choose template
        is_dialog = move == "dialog" or (roll is None)
        is_targeted = brain.target_npc and brain.target_npc == npc.id

        if is_dialog:
            if is_targeted or brain.target_npc:
                template = templates.get("dialog", "scene {scene}: conversation with {npc}")
            else:
                template = templates.get("dialog_no_target", "scene {scene}: conversation — {intent}")
        elif is_targeted:
            template = templates.get(
                "action_targeted", "scene {scene}: {player} {move_verb} involving {npc} — {result_text}"
            )
        else:
            template = templates.get("action", "scene {scene}: {player} {move_verb} — {result_text}")

        event_text = template.format(
            scene=scene,
            player=game.player_name,
            npc=npc.name,
            intent=intent[:80] if intent else "general",
            move_verb=move_verb,
            result_text=result_text,
            move=move,
            consequences=", ".join(consequences[:3]) if consequences else "",
        )

        emotional = derive_memory_emotion(move, result, npc.disposition)
        importance, debug = score_importance(emotional, event_text, debug=True)

        memories.append(
            {
                "npc_id": npc.id,
                "event": event_text,
                "emotional_weight": emotional,
                "importance": importance,
                "about_npc": brain.target_npc if brain.target_npc and brain.target_npc != npc.id else None,
                "_score_debug": f"engine-generated | {debug}",
            }
        )

    return memories


def generate_scene_context(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    activated_npc_names: list[str],
) -> str:
    """Engine-generated scene_context from mechanical context. Replaces AI-generated version."""
    _e = eng()
    move = brain.move
    location = game.world.current_location or "unknown"
    npc_summary = ", ".join(activated_npc_names[:3]) if activated_npc_names else "no one nearby"

    if move == "dialog" or roll is None:
        template = _e.get("scene_context_dialog", "conversation at {location} with {npc_summary}")
        return template.format(location=location, npc_summary=npc_summary)

    result = roll.result if roll else "MISS"
    move_label = _e.memory_move_verbs.get(move, move)
    template = _e.get("scene_context_template", "{result} on {move_label} at {location} — {npc_summary}")
    return template.format(
        result=result,
        move_label=move_label,
        location=location,
        npc_summary=npc_summary,
    )
