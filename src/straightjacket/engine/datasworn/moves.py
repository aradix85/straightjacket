from __future__ import annotations

from collections.abc import Callable
from typing import Any
from dataclasses import dataclass

from ..logging_util import log
from .loader import OracleTable, parse_oracle_table
from .oracle_rolls import plain_text
from .settings import SettingPackage, load_package


def _highest(values: dict[str, int]) -> str:
    return max(values, key=values.__getitem__)


def _lowest(values: dict[str, int]) -> str:
    return min(values, key=values.__getitem__)


PICK_METHODS: dict[str, Callable[[dict[str, int]], str]] = {"highest": _highest, "lowest": _lowest}


@dataclass
class RollOption:
    using: str
    stat: str
    condition_meter: str
    value: int | None
    label: str


@dataclass
class TriggerCondition:
    method: str
    text: str
    roll_options: list[RollOption]


@dataclass
class MoveOutcome:
    text: str


@dataclass
class Move:
    name: str
    roll_type: str
    conditions: list[TriggerCondition]
    outcomes: dict[str, MoveOutcome]
    track_category: str
    tables: dict[str, OracleTable]

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

    @property
    def stat_answers(self) -> list[str]:
        answers: list[str] = []
        for cond in self.conditions:
            stats = [ro.stat for ro in cond.roll_options if ro.using == "stat" and ro.stat]
            for answer in [cond.method] if cond.method in PICK_METHODS else stats:
                if answer not in answers:
                    answers.append(answer)
        return answers


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


def _parse_tables(raw: list[str] | dict[str, Any] | None, pkg: SettingPackage) -> dict[str, OracleTable]:
    if raw is None:
        return {}
    if isinstance(raw, list):
        return {ref.rsplit("/", 1)[-1]: pkg.table_by_id(ref) for ref in raw}
    return {key: parse_oracle_table(table["_id"], table) for key, table in raw.items()}


def outcome_text(setting_id: str, move_key: str, result: str) -> str:
    move = get_moves(setting_id).get(move_key)
    if move is None or not move.outcomes:
        return ""
    return plain_text(move.outcomes[result.lower()].text)


def _parse_move(raw: dict[str, Any], pkg: SettingPackage) -> Move:
    return Move(
        name=raw["name"],
        roll_type=raw["roll_type"],
        conditions=[
            TriggerCondition(
                method=c["method"],
                text=c.get("text") or "",
                roll_options=[_parse_roll_option(ro) for ro in c["roll_options"]],
            )
            for c in raw["trigger"]["conditions"] or []
        ],
        outcomes=_parse_outcomes(raw.get("outcomes")),
        track_category=raw.get("tracks", {}).get("category", ""),
        tables=_parse_tables(raw.get("oracles"), pkg),
    )


def _load_moves_from_setting(source: SettingPackage, pkg: SettingPackage) -> dict[str, Move]:
    return {
        f"{cat_key}/{move_key}": _parse_move(move_data, pkg)
        for cat_key, cat_data in source.data.raw["moves"].items()
        for move_key, move_data in cat_data["contents"].items()
    }


_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    if setting_id in _cache:
        return _cache[setting_id]

    pkg = load_package(setting_id)
    moves: dict[str, Move] = {}
    for source in reversed(list(pkg.chain())):
        moves.update(_load_moves_from_setting(source, pkg))
    log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")
    _cache[setting_id] = moves
    return moves


def clear_cache() -> None:
    _cache.clear()
