from __future__ import annotations

from dataclasses import dataclass

from .oracle_rolls import LINK_PATTERN, is_table_link, link_path, roll_rows
from .packages import SettingPackage

_MAX_DEPTH = 4


@dataclass(frozen=True)
class CascadeStep:
    path: str
    label: str
    text: str


def roll_oracle_cascade(pkg: SettingPackage, entry_path: str) -> list[CascadeStep]:
    steps: list[CascadeStep] = []
    current_path = entry_path
    for _ in range(_MAX_DEPTH):
        text = "; ".join(row.text for row in roll_rows(pkg.oracle_table(current_path)).rows)

        next_path, label = _extract_next_path(text)
        if next_path is None:
            steps.append(CascadeStep(path=current_path, label=text, text=text))
            return steps

        steps.append(CascadeStep(path=current_path, label=label or text, text=text))
        current_path = next_path

    raise RuntimeError(f"Oracle cascade from '{entry_path}' links on past {_MAX_DEPTH} tables")


def _extract_next_path(text: str) -> tuple[str | None, str | None]:
    match = LINK_PATTERN.search(text)
    if match is None or not is_table_link(match.group(2)):
        return None, None
    return link_path(match.group(2)), match.group(1)
