from __future__ import annotations

import json
import random
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from ..models import FateResult, GameState
from .config import gm

_MYTHIC_DATA_PATH = PROJECT_ROOT / "data" / "mythic_gme_2e.json"

_mythic: dict[str, Any] | None = None


def _load_mythic() -> dict[str, Any]:
    global _mythic
    if _mythic is None:
        with _MYTHIC_DATA_PATH.open(encoding="utf-8") as f:
            _mythic = json.load(f)
        log(f"[Fate] Loaded {_MYTHIC_DATA_PATH}")
    return _mythic


def resolve_fate_chart(odds: str, chaos_factor: int) -> FateResult:
    data = _load_mythic()
    chart = data["fate_chart"]

    if odds not in chart:
        raise KeyError(f"Unknown odds level '{odds}' (valid: {sorted(chart.keys())})")
    if not 1 <= chaos_factor <= len(chart[odds]):
        raise KeyError(f"Unknown chaos_factor {chaos_factor} (valid: 1..{len(chart[odds])})")

    cell = chart[odds][chaos_factor - 1]
    roll = random.randint(1, gm().mythic_dice.fate_chart_die)

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

    result = FateResult(answer=answer, random_event_triggered=event_triggered)
    log(f"[Fate] Chart: {odds} CF{chaos_factor} roll={roll} → {answer}{' +EVENT' if event_triggered else ''}")
    return result


def _check_chart_random_event(roll: int, chaos_factor: int) -> bool:
    if roll == gm().mythic_dice.fate_chart_die:
        return True
    tens = roll // 10
    ones = roll % 10
    if tens != ones:
        return False
    return ones <= chaos_factor


_CHECK_ANSWER_PRECEDENCE = ("exceptional_yes", "exceptional_no", "yes", "no")


def _check_answer(answers: dict[str, dict[str, int]], total: int) -> str:
    for answer in _CHECK_ANSWER_PRECEDENCE:
        bounds = answers[answer]
        if "min_total" in bounds and total < bounds["min_total"]:
            continue
        if "max_total" in bounds and total > bounds["max_total"]:
            continue
        return answer
    raise ValueError(f"fate_check answers in mythic_gme_2e.json cover no total {total}")


def resolve_fate_check(odds: str, chaos_factor: int) -> FateResult:
    check = _load_mythic()["fate_check"]
    odds_modifiers = {row["odds"]: row["modifier"] for row in check["odds_modifiers"]}
    chaos_modifiers = {row["chaos_factor"]: row["modifier"] for row in check["chaos_factor_modifiers"]}
    if odds not in odds_modifiers:
        raise KeyError(f"Unknown odds level '{odds}' (valid: {sorted(odds_modifiers)})")
    if chaos_factor not in chaos_modifiers:
        raise KeyError(f"Unknown chaos_factor {chaos_factor} (valid: {sorted(chaos_modifiers)})")

    die = gm().mythic_dice.fate_check_die
    d1, d2 = random.randint(1, die), random.randint(1, die)

    odds_mod = odds_modifiers[odds]
    cf_mod = chaos_modifiers[chaos_factor]
    total = d1 + d2 + odds_mod + cf_mod
    answer = _check_answer(check["answers"], total)

    event_triggered = _check_check_random_event(d1, d2, chaos_factor)

    result = FateResult(answer=answer, random_event_triggered=event_triggered)
    log(
        f"[Fate] Check: {odds} CF{chaos_factor} {d1}+{d2}+{odds_mod}+{cf_mod}={total} → {answer}"
        f"{' +EVENT' if event_triggered else ''}"
    )
    return result


def _check_check_random_event(d1: int, d2: int, chaos_factor: int) -> bool:
    if d1 != d2:
        return False
    return d1 <= chaos_factor


def resolve_fate(game: GameState, odds: str) -> FateResult:
    method = gm().fate.default_method
    if method == "fate_check":
        result = resolve_fate_check(odds, game.world.chaos_factor)
    elif method == "fate_chart":
        result = resolve_fate_chart(odds, game.world.chaos_factor)
    else:
        raise ValueError(f"Unknown fate method {method!r}; valid: 'fate_chart', 'fate_check'")

    if result.random_event_triggered:
        from .random_events import generate_random_event

        generate_random_event(game, source="fate_doublet")

    return result


def score_to_odds(score: int) -> str:
    for entry in gm().fate.likelihood_rules.score_to_odds:
        if score >= int(entry["min_score"]):
            return str(entry["odds"])
    raise ValueError(
        f"score_to_odds has no matching threshold for score={score}; table must include a catch-all entry at the bottom"
    )
