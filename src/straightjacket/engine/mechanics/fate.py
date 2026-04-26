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
    global _mythic
    if _mythic is None:
        with open(_MYTHIC_DATA_PATH, encoding="utf-8") as f:
            _mythic = json.load(f)
        log(f"[Fate] Loaded {_MYTHIC_DATA_PATH}")
    return _mythic


def get_odds_levels() -> tuple[str, ...]:
    return tuple(eng().enums.odds_levels)


def resolve_fate_chart(odds: str, chaos_factor: int, question: str, roll: int | None = None) -> FateResult:
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
        question=question,
        random_event_triggered=event_triggered,
    )
    log(f"[Fate] Chart: {odds} CF{chaos_factor} roll={roll} → {answer}{' +EVENT' if event_triggered else ''}")
    return result


def _check_chart_random_event(roll: int, chaos_factor: int) -> bool:
    if roll == 100:
        return True
    if roll < 11:
        return False
    tens = roll // 10
    ones = roll % 10
    if tens != ones:
        return False
    return ones <= chaos_factor


def resolve_fate_check(odds: str, chaos_factor: int, question: str, dice: tuple[int, int] | None = None) -> FateResult:
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
        question=question,
        random_event_triggered=event_triggered,
    )
    log(
        f"[Fate] Check: {odds} CF{chaos_factor} {d1}+{d2}+{odds_mod}+{cf_mod}={total} → {answer}"
        f"{' +EVENT' if event_triggered else ''}"
    )
    return result


def _check_check_random_event(d1: int, d2: int, chaos_factor: int) -> bool:
    if d1 != d2:
        return False
    return d1 <= chaos_factor


def resolve_fate(
    game: GameState,
    odds: str,
    chaos_factor: int,
    question: str,
    method: str | None = None,
) -> FateResult:
    if method is None:
        method = eng().fate.default_method

    if method == "fate_check":
        result = resolve_fate_check(odds, chaos_factor, question)
    else:
        result = resolve_fate_chart(odds, chaos_factor, question)

    if result.random_event_triggered:
        from .random_events import generate_random_event

        result.random_event = generate_random_event(game, source="fate_doublet")

    return result


def resolve_likelihood(game: GameState, context_hint: str = "") -> str:
    _e = eng()
    rules = _e.fate.likelihood_rules

    score = 0

    if context_hint:
        hint_lower = context_hint.lower()
        npc = _find_hint_npc(game, hint_lower)
        if npc:
            disp = npc.disposition
            disp_scores = rules.disposition_scores
            if disp in disp_scores:
                score += int(disp_scores[disp])

    cf = game.world.chaos_factor
    cf_thresholds = rules.chaos_thresholds
    if cf >= cf_thresholds["high"]:
        score += int(rules.chaos_scores["high"])
    elif cf <= cf_thresholds["low"]:
        score += int(rules.chaos_scores["low"])

    res = game.resources
    resource_critical = int(rules.resource_critical_below)
    if res.health <= resource_critical or res.spirit <= resource_critical:
        score += int(rules.resource_scores["critical"])

    return _score_to_odds(score, rules)


def _find_hint_npc(game: GameState, hint_lower: str) -> NpcData | None:
    for npc in game.npcs:
        if npc.status != "active":
            continue
        if npc.name.lower() in hint_lower or npc.id in hint_lower:
            return npc
    return None


def _score_to_odds(score: int, rules: Any) -> str:
    thresholds = rules.score_to_odds

    for entry in thresholds:
        if score >= int(entry["min_score"]):
            return str(entry["odds"])
    raise ValueError(
        f"score_to_odds has no matching threshold for score={score}; table must include a catch-all entry at the bottom"
    )
