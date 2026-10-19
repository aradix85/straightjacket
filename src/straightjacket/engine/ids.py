from __future__ import annotations

from collections.abc import Iterable


def unique_id(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    suffix = 2
    while f"{base}_{suffix}" in taken:
        suffix += 1
    return f"{base}_{suffix}"


def next_id(prefix: str, taken: Iterable[str]) -> str:
    numbers = [int(rest) for t in taken if t.startswith(prefix) and (rest := t[len(prefix) :]).isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1}"
