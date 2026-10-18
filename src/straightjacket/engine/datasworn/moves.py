from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field

from ..logging_util import log
from .loader import Setting
from .oracle_rolls import plain_text
from .settings import load_package


@dataclass
class RollOption:
    using: str = ""
    stat: str = ""
    condition_meter: str = ""
    value: int | None = None
    label: str = ""


@dataclass
class TriggerCondition:
    roll_options: list[RollOption] = field(default_factory=list)


@dataclass
class MoveOutcome:
    text: str = ""


@dataclass
class Move:
    name: str = ""
    roll_type: str = ""
    text: str = ""
    conditions: list[TriggerCondition] = field(default_factory=list)
    outcomes: dict[str, MoveOutcome] = field(default_factory=dict)
    track_category: str = ""

    @property
    def valid_stats(self) -> list[str]:
        stats: list[str] = []
        seen: set[str] = set()
        for cond in self.conditions:
            for ro in cond.roll_options:
                if ro.using == "stat" and ro.stat and ro.stat not in seen:
                    stats.append(ro.stat)
                    seen.add(ro.stat)
        return stats


def _parse_roll_option(raw: dict[str, Any]) -> RollOption:
    return RollOption(
        using=raw["using"],
        stat=raw.get("stat", ""),
        condition_meter=raw.get("condition_meter", ""),
        value=raw.get("value"),
        label=raw.get("label", ""),
    )


def _parse_outcomes(raw: dict[str, Any] | None) -> dict[str, MoveOutcome]:
    if raw is None:
        return {}
    return {key: MoveOutcome(text=raw[key]["text"]) for key in ("strong_hit", "weak_hit", "miss")}


def outcome_text(setting_id: str, move_key: str, result: str) -> str:
    move = get_moves(setting_id).get(move_key)
    if move is None or not move.outcomes:
        return ""
    return plain_text(move.outcomes[result.lower()].text)


def _parse_move(raw: dict[str, Any]) -> Move:
    return Move(
        name=raw["name"],
        roll_type=raw["roll_type"],
        text=raw["text"],
        conditions=[
            TriggerCondition(roll_options=[_parse_roll_option(ro) for ro in c["roll_options"]])
            for c in raw["trigger"]["conditions"] or []
        ],
        outcomes=_parse_outcomes(raw.get("outcomes")),
        track_category=raw.get("tracks", {}).get("category", ""),
    )


def _load_moves_from_setting(setting: Setting) -> dict[str, Move]:
    return {
        f"{cat_key}/{move_key}": _parse_move(move_data)
        for cat_key, cat_data in setting.raw["moves"].items()
        for move_key, move_data in cat_data["contents"].items()
    }


_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    if setting_id in _cache:
        return _cache[setting_id]

    moves: dict[str, Move] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        moves.update(_load_moves_from_setting(pkg.data))
    log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")
    _cache[setting_id] = moves
    return moves


def clear_cache() -> None:
    _cache.clear()
