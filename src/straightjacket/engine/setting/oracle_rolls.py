from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .loader import OracleRow, OracleTable

if TYPE_CHECKING:
    from .packages import SettingPackage

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")
_LINK_PREFIX = "datasworn:"
_LINK_KINDS = ("oracle_rollable:", "oracle_collection:")
_TABLE_KIND = "oracle_rollable:"
_DUPLICATE_RULES = ("reroll", "keep", "make_it_worse")
_EMPHASIS = "__"


@dataclass(frozen=True)
class RolledOracle:
    text: str
    choice: str


@dataclass(frozen=True)
class TableRoll:
    rows: list[OracleRow]
    worse: bool


def plain_text(text: str) -> str:
    return LINK_PATTERN.sub(r"\1", text).replace(_EMPHASIS, "").strip()


def link_owner_and_path(target: str) -> tuple[str, str]:
    rest = target.removeprefix(_LINK_PREFIX)
    for kind in _LINK_KINDS:
        rest = rest.removeprefix(kind)
    owner, path = rest.split("/", 1)
    return owner, path


def link_path(target: str) -> str:
    return link_owner_and_path(target)[1]


def is_table_link(target: str) -> bool:
    return target.removeprefix(_LINK_PREFIX).startswith(_TABLE_KIND)


def roll_rows(table: OracleTable) -> TableRoll:
    row = table.roll()
    instruction = _roll_again(row)
    if instruction is None:
        return TableRoll(rows=[row], worse=False)
    rule = instruction["duplicates"]
    if rule not in _DUPLICATE_RULES:
        raise ValueError(f"Oracle table '{table.id}' has an unknown duplicates rule {rule!r}")
    picked: list[OracleRow] = []
    while len(picked) < int(instruction["number_of_rolls"]):
        again = table.roll()
        if _roll_again(again) is not None or (rule == "reroll" and _among(again, picked)):
            continue
        picked.append(again)
    distinct = [row for i, row in enumerate(picked) if not _among(row, picked[:i])]
    if rule == "make_it_worse" and len(distinct) < len(picked):
        return TableRoll(rows=distinct, worse=True)
    return TableRoll(rows=picked, worse=False)


def roll_oracle(pkg: SettingPackage, path: str) -> RolledOracle:
    return roll_table(pkg, pkg.oracle_table(path))


def roll_table(pkg: SettingPackage, table: OracleTable) -> RolledOracle:
    rows = roll_rows(table).rows
    if len(rows) == 1:
        return _resolve_row(pkg, rows[0])
    text = "; ".join(_resolve_row(pkg, row).text for row in rows)
    return RolledOracle(text=text, choice=_slug(text))


def roll_generator_tables(pkg: SettingPackage, tables: dict[str, str]) -> dict[str, str]:
    results: dict[str, str] = {}
    choices: dict[str, str] = {}
    for role, template in tables.items():
        path = PLACEHOLDER_PATTERN.sub(lambda m: choices[m.group(1)], template)
        rolled = roll_oracle(pkg, path)
        results[role] = rolled.text
        choices[role] = rolled.choice
    return results


def _auto_rolls(row: OracleRow) -> list[dict[str, Any]]:
    return [instruction for instruction in row.oracle_rolls or [] if instruction["auto"]]


def _roll_again(row: OracleRow) -> dict[str, Any] | None:
    return next((i for i in _auto_rolls(row) if i["oracle"] is None), None)


def _among(row: OracleRow, rows: list[OracleRow]) -> bool:
    return any(row is earlier for earlier in rows)


def _resolve_row(pkg: SettingPackage, row: OracleRow) -> RolledOracle:
    rolled: dict[str, list[str]] = {}
    for instruction in _auto_rolls(row):
        if instruction["oracle"] is None:
            continue
        path = link_path(str(instruction["oracle"]))
        rolled[path] = [roll_oracle(pkg, path).text for _ in range(int(instruction["number_of_rolls"]))]

    def replace(match: re.Match[str]) -> str:
        pending = rolled.get(link_path(match.group(2)))
        return pending.pop(0) if pending else match.group(1)

    text = LINK_PATTERN.sub(replace, row.text).strip()
    only_link = LINK_PATTERN.fullmatch(row.text.strip())
    choice = link_path(only_link.group(2)).rsplit("/", 1)[-1] if only_link else _slug(text)
    return RolledOracle(text=text, choice=choice)


def _slug(text: str) -> str:
    return re.sub(r"\W+", "_", text.lower()).strip("_")
