from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.logging_util import log
from straightjacket.engine.ruleset.datasworn import load_ruleset, rules_file
from straightjacket.engine.serialization import read_key, read_optional_key, shaped
from straightjacket.engine.setting.loader import parse_oracle_table
from straightjacket.engine.setting.oracle_rolls import is_table_link, link_path, plain_text
from straightjacket.engine.setting.packages import load_package

if TYPE_CHECKING:
    from collections.abc import Callable

    from straightjacket.engine.ruleset.datasworn import RulesFile
    from straightjacket.engine.setting.loader import OracleTable


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


def _parse_roll_option(raw: object, where: str) -> RollOption:
    return RollOption(
        using=read_key(raw, "using", str, where),
        stat=read_optional_key(raw, "stat", str, where) or "",
        condition_meter=read_optional_key(raw, "condition_meter", str, where) or "",
        value=read_optional_key(raw, "value", int, where),
        label=read_optional_key(raw, "label", str, where) or "",
    )


def _parse_condition(raw: object, where: str) -> TriggerCondition:
    return TriggerCondition(
        method=read_key(raw, "method", str, where),
        text=read_optional_key(raw, "text", str, where) or "",
        roll_options=[
            _parse_roll_option(option, f"{where}.roll_options[{index}]")
            for index, option in enumerate(read_key(raw, "roll_options", list, where))
        ],
    )


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
        msg = f"{move.name} neither carries nor suggests a table {key!r} in setting {setting_id!r}"
        raise KeyError(msg)
    return table


def outcome_text(setting_id: str, move_key: str, result: str) -> str:
    move = get_moves(setting_id).get(move_key)
    if move is None or not move.outcomes:
        return ""
    return plain_text(move.outcomes[result.lower()].text)


def _parse_move(raw: object, where: str) -> Move:
    trigger = read_key(raw, "trigger", dict, where)
    return Move(
        name=read_key(raw, "name", str, where),
        roll_type=read_key(raw, "roll_type", str, where),
        conditions=[
            _parse_condition(condition, f"{where}.trigger.conditions[{index}]")
            for index, condition in enumerate(read_key(trigger, "conditions", list, f"{where}.trigger"))
        ],
        outcomes={
            key: MoveOutcome(text=read_key(outcome, "text", str, f"{where}.outcomes.{key}"))
            for key, outcome in (read_optional_key(raw, "outcomes", dict, where) or {}).items()
        },
        track_category=read_optional_key(
            read_optional_key(raw, "tracks", dict, where) or {}, "category", str, f"{where}.tracks"
        )
        or "",
        tables={
            key: parse_oracle_table(
                read_key(table, "_id", str, f"{where}.oracles.{key}"), table, f"{where}.oracles.{key}"
            )
            for key, table in (read_optional_key(raw, "oracles", dict, where) or {}).items()
        },
        suggestions=[
            shaped(suggestion, str, f"{where}.suggestions: expected str")
            for suggestion in read_optional_key(raw, "suggestions", list, where) or []
        ],
        allow_momentum_burn=read_key(raw, "allow_momentum_burn", bool, where),
    )


def _load_moves(ruleset: RulesFile) -> dict[str, Move]:
    return {
        f"{cat_key}/{move_key}": _parse_move(move_data, f"{ruleset.datasworn_id}.moves.{cat_key}/{move_key}")
        for cat_key, cat_data in ruleset.moves.items()
        for move_key, move_data in read_key(cat_data, "contents", dict, f"{ruleset.datasworn_id}.moves").items()
    }


_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    if setting_id in _cache:
        return _cache[setting_id]

    moves: dict[str, Move] = {}
    for file in load_ruleset(setting_id).files:
        moves.update(_load_moves(file))
    log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")
    _cache[setting_id] = moves
    return moves


_file_cache: dict[str, dict[str, Move]] = {}


def move_of_file(datasworn_id: str, move_key: str) -> Move:
    if datasworn_id not in _file_cache:
        _file_cache[datasworn_id] = _load_moves(rules_file(datasworn_id))
    return _file_cache[datasworn_id][move_key]
