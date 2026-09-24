from __future__ import annotations


def unique_id(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    suffix = 2
    while f"{base}_{suffix}" in taken:
        suffix += 1
    return f"{base}_{suffix}"
