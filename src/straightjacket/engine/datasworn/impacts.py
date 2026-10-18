from __future__ import annotations

from dataclasses import dataclass

from .oracle_rolls import plain_text
from .settings import load_package


@dataclass(frozen=True)
class Impact:
    label: str
    prevents_recovery: list[str]
    permanent: bool
    description: str


_cache: dict[str, dict[str, Impact]] = {}


def get_impacts(setting_id: str) -> dict[str, Impact]:
    if setting_id in _cache:
        return _cache[setting_id]
    impacts: dict[str, Impact] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        for category in (pkg.data.raw["rules"].get("impacts") or {}).values():
            for key, raw in category["contents"].items():
                impacts[key] = Impact(
                    label=raw["label"],
                    prevents_recovery=list(raw["prevents_recovery"]),
                    permanent=raw["permanent"],
                    description=plain_text(raw["description"]),
                )
    _cache[setting_id] = impacts
    return impacts
