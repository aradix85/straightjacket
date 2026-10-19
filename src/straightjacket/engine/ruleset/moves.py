from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..logging_util import log
from ..setting.loader import OracleTable, parse_oracle_table
from ..setting.oracle_rolls import is_table_link, link_path, plain_text
from ..setting.packages import load_package
from .datasworn import RulesFile, load_ruleset


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
    suggestions: list[str]
    allow_momentum_burn: bool

    @property
    def is_action_roll(self) -> bool:
        return self.roll_type == "action_roll"

    @property
    def is_progress_roll(self) -> bool:
        return self.roll_type == "progress_roll"

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
    return {key: MoveOutcome(text=outcome["text"]) for key, outcome in raw.items()}


def _parse_tables(raw: dict[str, Any] | None) -> dict[str, OracleTable]:
    if raw is None:
        return {}
    return {key: parse_oracle_table(table["_id"], table) for key, table in raw.items()}


def _offered_table(setting_id: str, move: Move, key: str) -> OracleTable | None:
    if key in move.tables:
        return move.tables[key]
    for ref in move.suggestions:
        if is_table_link(ref) and link_path(ref).rsplit("/", 1)[-1] == key:
            return load_package(setting_id).table_by_id(ref)
    return None


def offers_table(setting_id: str, move: Move, key: str) -> bool:
    return _offered_table(setting_id, move, key) is not None


def move_table(setting_id: str, move: Move, key: str) -> OracleTable:
    table = _offered_table(setting_id, move, key)
    if table is None:
        raise KeyError(f"{move.name} neither carries nor suggests a table {key!r} in setting {setting_id!r}")
    return table


def outcome_text(setting_id: str, move_key: str, result: str) -> str:
    move = get_moves(setting_id).get(move_key)
    if move is None or not move.outcomes:
        return ""
    return plain_text(move.outcomes[result.lower()].text)


def _parse_move(raw: dict[str, Any]) -> Move:
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
        tables=_parse_tables(raw.get("oracles")),
        suggestions=list(raw.get("suggestions", [])),
        allow_momentum_burn=raw["allow_momentum_burn"],
    )


def _load_moves(rules_file: RulesFile) -> dict[str, Move]:
    return {
        f"{cat_key}/{move_key}": _parse_move(move_data)
        for cat_key, cat_data in rules_file.moves.items()
        for move_key, move_data in cat_data["contents"].items()
    }


_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    if setting_id in _cache:
        return _cache[setting_id]

    moves: dict[str, Move] = {}
    for rules_file in load_ruleset(setting_id).files:
        moves.update(_load_moves(rules_file))
    log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")
    _cache[setting_id] = moves
    return moves


def clear_cache() -> None:
    _cache.clear()
