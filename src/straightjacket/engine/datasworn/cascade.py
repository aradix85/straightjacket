from __future__ import annotations

import re
from dataclasses import dataclass

from .settings import SettingPackage

_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(id:([^)]+)\)")
_ORACLES_INFIX = "/oracles/"


@dataclass(frozen=True)
class CascadeStep:
    table_path: str
    label: str
    text: str


def roll_oracle_cascade(pkg: SettingPackage, entry_path: str, max_depth: int = 4) -> list[CascadeStep]:
    if not entry_path:
        raise ValueError("roll_oracle_cascade called with empty entry_path")

    steps: list[CascadeStep] = []
    current_path = entry_path
    for _ in range(max_depth):
        data = pkg.oracle_data_for(current_path)
        if data is None:
            raise KeyError(f"Oracle '{current_path}' not found in setting chain for {pkg.id}")
        table = data.oracle(current_path)
        if table is None:
            raise KeyError(f"Oracle table '{current_path}' missing from setting {pkg.id}")
        result = table.roll()

        next_path, label = _extract_next_path(result.value)
        if next_path is None:
            steps.append(CascadeStep(table_path=current_path, label=result.value, text=result.value))
            return steps

        steps.append(CascadeStep(table_path=current_path, label=label or result.value, text=result.value))
        current_path = next_path

    raise RuntimeError(f"Oracle cascade exceeded max_depth={max_depth} starting at '{entry_path}'")


def _extract_next_path(text: str) -> tuple[str | None, str | None]:
    match = _LINK_PATTERN.search(text)
    if match is None:
        return None, None
    label = match.group(1)
    target_id = match.group(2)
    if _ORACLES_INFIX not in target_id:
        return None, None
    after_oracles = target_id.split(_ORACLES_INFIX, 1)[1]
    return after_oracles, label
