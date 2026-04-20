"""Mythic GME 2e fate system: fate chart, fate check, likelihood resolver.

Two resolution methods for yes/no questions about the fiction. Both produce
the same four outcomes (yes, no, exceptional_yes, exceptional_no) and can
trigger random events alongside the answer.

Data: data/mythic_gme_2e.json → fate_chart, fate_check.
Config: engine.yaml → fate (method selection, likelihood mapping).
"""

from __future__ import annotations

import json
import random

from typing import Any

from ..config_loader import PROJECT_ROOT
from ..engine_loader import eng
from ..logging_util import log
from ..models import FateResult, GameState, NpcData


_MYTHIC_DATA_PATH = PROJECT_ROOT / "data" / "mythic_gme_2e.json"

_mythic: dict | None = None


def _load_mythic() -> dict:
    """Load mythic_gme_2e.json. Cached after first access."""
    global _mythic
    if _mythic is None:
        with open(_MYTHIC_DATA_PATH, encoding="utf-8") as f:
            _mythic = json.load(f)
        log(f"[Fate] Loaded {_MYTHIC_DATA_PATH}")
    return _mythic


def get_odds_levels() -> tuple[str, ...]:
    """Odds levels in order from most-favorable to least-favorable."""
    return tuple(eng().enums.odds_levels)


def resolve_fate_chart(odds: str, chaos_factor: int, roll: int | None = None) -> FateResult:
    """Resolve a fate question using the fate chart method.

    Looks up (odds, chaos_factor) in the fate chart. Rolls d100 and compares
    against thresholds for exceptional_yes, yes, exceptional_no.

    Args:
        odds: one of get_odds_levels()
        chaos_factor: 1–9
        roll: override d100 roll (for testing), None = random
    """
    data = _load_mythic()
    chart = data["fate_chart"]

    if odds not in chart:
        raise KeyError(f"Unknown odds level '{odds}' (valid: {sorted(chart.keys())})")

    cf_index = max(0, min(8, chaos_factor - 1))
    cell = chart[odds][cf_index]

    if roll is None:
        roll = random.randint(1, 100)

    ey_threshold = cell["exceptional_yes"]
    yes_threshold = cell["yes"]
    en_threshold = cell["exceptional_no"]

    if ey_threshold is not None and roll <= ey_threshold:
        answer = "exceptional_yes"
    elif roll <= yes_threshold:
        answer = "yes"
    elif en_threshold is not None and roll >= en_threshold:
        answer = "exceptional_no"
    else:
        answer = "no"

    event_triggered = _check_chart_random_event(roll, chaos_factor)

    result = FateResult(
        answer=answer,
        odds=odds,
        chaos_factor=chaos_factor,
        method="fate_chart",
        roll=roll,
        random_event_triggered=event_triggered,
    )
    log(f"[Fate] Chart: {odds} CF{chaos_factor} roll={roll} → {answer}{' +EVENT' if event_triggered else ''}")
    return result


def _check_chart_random_event(roll: int, chaos_factor: int) -> bool:
    """Check if a fate chart roll triggers a random event.

    Doublet rule: d100 roll is a doublet (11, 22, ..., 99, 00) AND the
    single digit <= chaos factor. 00 counts as digit 0, which is always
    <= chaos factor (CF minimum is 1).
    """
    if roll == 100:
        # 00 on d100: digit is 0, always <= CF
        return True
    if roll < 11:
        return False
    tens = roll // 10
    ones = roll % 10
    if tens != ones:
        return False
    return ones <= chaos_factor


def resolve_fate_check(odds: str, chaos_factor: int, dice: tuple[int, int] | None = None) -> FateResult:
    """Resolve a fate question using the fate check method.

    Rolls 2d10, adds odds modifier + chaos modifier. Total determines outcome.
    Exceptional takes priority over normal in overlap ranges.

    Args:
        odds: one of get_odds_levels()
        chaos_factor: 1–9
        dice: override (d1, d2) tuple (for testing), None = random
    """
    cfg = eng().fate
    if odds not in cfg.odds_modifiers:
        raise KeyError(f"Unknown odds level '{odds}' (valid: {sorted(cfg.odds_modifiers.keys())})")
    if chaos_factor not in cfg.chaos_modifiers:
        raise KeyError(f"Unknown chaos_factor {chaos_factor} (valid: {sorted(cfg.chaos_modifiers.keys())})")

    if dice is None:
        d1 = random.randint(1, 10)
        d2 = random.randint(1, 10)
    else:
        d1, d2 = dice

    odds_mod = cfg.odds_modifiers[odds]
    cf_mod = cfg.chaos_modifiers[chaos_factor]
    total = d1 + d2 + odds_mod + cf_mod

    # Determine answer. Exceptional ranges take priority.
    if 18 <= total <= 20:
        answer = "exceptional_yes"
    elif 2 <= total <= 4:
        answer = "exceptional_no"
    elif total >= 11:
        answer = "yes"
    else:
        answer = "no"

    event_triggered = _check_check_random_event(d1, d2, chaos_factor)

    result = FateResult(
        answer=answer,
        odds=odds,
        chaos_factor=chaos_factor,
        method="fate_check",
        roll=d1 + d2,
        random_event_triggered=event_triggered,
    )
    log(
        f"[Fate] Check: {odds} CF{chaos_factor} {d1}+{d2}+{odds_mod}+{cf_mod}={total} → {answer}"
        f"{' +EVENT' if event_triggered else ''}"
    )
    return result


def _check_check_random_event(d1: int, d2: int, chaos_factor: int) -> bool:
    """Check if a fate check roll triggers a random event.

    Both dice show same number AND the digit <= chaos factor.
    """
    if d1 != d2:
        return False
    return d1 <= chaos_factor


def resolve_fate(
    game: GameState,
    odds: str,
    chaos_factor: int,
    method: str | None = None,
    question: str = "",
) -> FateResult:
    """Resolve a fate question using the configured method.

    Generates a random event via the pipeline when the roll triggers one.

    Args:
        game: GameState for random event generation and context
        odds: one of get_odds_levels()
        chaos_factor: 1–9
        method: "fate_chart" or "fate_check", None = read from engine.yaml
        question: the question being asked (stored in result for logging)
    """
    if method is None:
        method = eng().fate.default_method

    if method == "fate_check":
        result = resolve_fate_check(odds, chaos_factor)
    else:
        result = resolve_fate_chart(odds, chaos_factor)

    result.question = question

    if result.random_event_triggered:
        # circular: random_events imports from fate
        from .random_events import generate_random_event

        result.random_event = generate_random_event(game, source="fate_doublet")

    return result


def resolve_likelihood(game: GameState, context_hint: str = "") -> str:
    """Determine odds level from game state.

    Uses engine.yaml fate.likelihood_rules to map context factors to odds.
    Returns an odds level string. Default: fifty_fifty.

    The context_hint from Brain provides situational info (e.g. "NPC friendly",
    "dangerous area") but the engine derives the actual odds from game state.
    """
    _e = eng()
    rules = _e.fate.likelihood_rules

    score = 0

    # NPC disposition (if context_hint mentions an NPC, use their disposition)
    if context_hint:
        hint_lower = context_hint.lower()
        npc = _find_hint_npc(game, hint_lower)
        if npc:
            disp = npc.disposition
            disp_scores = rules.disposition_scores
            if disp in disp_scores:
                score += int(disp_scores[disp])

    # Chaos factor influence
    cf = game.world.chaos_factor
    cf_thresholds = rules.chaos_thresholds
    if cf >= cf_thresholds["high"]:
        score += int(rules.chaos_scores["high"])
    elif cf <= cf_thresholds["low"]:
        score += int(rules.chaos_scores["low"])

    # Resource pressure
    res = game.resources
    resource_critical = int(rules.resource_critical_below)
    if res.health <= resource_critical or res.spirit <= resource_critical:
        score += int(rules.resource_scores["critical"])

    # Map score to odds level
    return _score_to_odds(score, rules)


def _find_hint_npc(game: GameState, hint_lower: str) -> NpcData | None:
    """Find an NPC referenced in the context hint."""
    for npc in game.npcs:
        if npc.status != "active":
            continue
        if npc.name.lower() in hint_lower or npc.id in hint_lower:
            return npc
    return None


def _score_to_odds(score: int, rules: Any) -> str:
    """Map a numeric score to an odds level via engine.yaml thresholds."""
    thresholds = rules.score_to_odds
    # Sorted from highest to lowest score. Entries are dicts from YAML list.
    for entry in thresholds:
        if score >= int(entry["min_score"]):
            return str(entry["odds"])
    raise ValueError(
        f"score_to_odds has no matching threshold for score={score}; table must include a catch-all entry at the bottom"
    )
