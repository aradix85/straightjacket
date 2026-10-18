from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .loader import OracleRow, OracleTable

if TYPE_CHECKING:
    from .settings import SettingPackage

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")
_LINK_PREFIXES = ("id:", "datasworn:")
_LINK_KINDS = ("oracle_rollable:", "oracle_collection:")
_ORACLE_INFIXES = ("collections/oracles/", "oracles/")
_TABLE_KIND = "oracle_rollable:"
_ORACLE_SEGMENT = "/oracles/"
_COLLECTION_SEGMENT = "/collections/"


@dataclass(frozen=True)
class RolledOracle:
    text: str
    choice: str


def link_path(target: str) -> str:
    rest = target
    for prefix in _LINK_PREFIXES:
        rest = rest.removeprefix(prefix)
    for kind in _LINK_KINDS:
        rest = rest.removeprefix(kind)
    rest = rest.split("/", 1)[1]
    for infix in _ORACLE_INFIXES:
        if rest.startswith(infix):
            return rest[len(infix) :]
    return rest


def is_table_link(target: str) -> bool:
    if _TABLE_KIND in target:
        return True
    return _ORACLE_SEGMENT in f"/{target}" and _COLLECTION_SEGMENT not in f"/{target}"


def roll_oracle(pkg: SettingPackage, path: str) -> RolledOracle:
    table = pkg.oracle_table(path)
    row = table.roll().row
    repeats = _repeat_count(row)
    if repeats:
        text = "; ".join(_resolve_row(pkg, picked).text for picked in _distinct_rows(table, repeats))
        return RolledOracle(text=text, choice=_slug(text))
    return _resolve_row(pkg, row)


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


def _repeat_count(row: OracleRow) -> int:
    return sum(int(i["number_of_rolls"]) for i in _auto_rolls(row) if i["oracle"] is None)


def _distinct_rows(table: OracleTable, count: int) -> list[OracleRow]:
    picked: list[OracleRow] = []
    while len(picked) < count:
        row = table.roll().row
        if _repeat_count(row) or any(row is earlier for earlier in picked):
            continue
        picked.append(row)
    return picked


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
