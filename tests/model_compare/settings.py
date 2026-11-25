from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from straightjacket.engine.serialization import build_strict

SETTINGS = Path(__file__).resolve().parent / "model_compare.yaml"
RUNS = Path(__file__).resolve().parent / "runs"


@dataclass(frozen=True)
class Source:
    name: str
    scenario: str
    style: str
    turns: int


@dataclass(frozen=True)
class Configuration:
    model: str
    effort: str
    fast: bool


@dataclass(frozen=True)
class Price:
    uncached: float
    cache_write: float
    cache_read: float
    output: float


@dataclass(frozen=True)
class CompareSettings:
    sources: list[Source]
    configurations: dict[str, Configuration]
    prices: dict[str, dict[str, Price]]
    rubrics: dict[str, str]


def load_settings() -> CompareSettings:
    with SETTINGS.open(encoding="utf-8") as f:
        return build_strict(CompareSettings, yaml.safe_load(f), SETTINGS.name)
