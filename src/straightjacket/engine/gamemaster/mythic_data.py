from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import build_strict

if TYPE_CHECKING:
    from pathlib import Path

_MYTHIC_DATA_PATH = PROJECT_ROOT / "data" / "mythic_gme_2e.json"


@dataclass(frozen=True)
class FateCell:
    exceptional_yes: int | None
    yes: int
    exceptional_no: int | None


@dataclass(frozen=True)
class OddsModifier:
    odds: str
    modifier: int


@dataclass(frozen=True)
class ChaosModifier:
    chaos_factor: int
    modifier: int


@dataclass(frozen=True)
class FateCheck:
    odds_modifiers: list[OddsModifier]
    chaos_factor_modifiers: list[ChaosModifier]
    answers: dict[str, dict[str, int]]
    random_event_rule: str


@dataclass(frozen=True)
class EventFocusRow:
    min: int
    max: int
    focus: str


@dataclass(frozen=True)
class SceneAdjustmentRow:
    min: int
    max: int
    result: str


@dataclass(frozen=True)
class ActionWords:
    verbs: list[str]
    subjects: list[str]


@dataclass(frozen=True)
class DescriptionWords:
    adverbs: list[str]
    adjectives: list[str]


@dataclass(frozen=True)
class MeaningTables:
    actions: ActionWords
    descriptions: DescriptionWords
    elements: dict[str, list[str]]


@dataclass(frozen=True)
class MythicData:
    fate_chart: dict[str, list[FateCell]]
    fate_check: FateCheck
    event_focus: list[EventFocusRow]
    meaning_tables: MeaningTables
    scene_adjustment: list[SceneAdjustmentRow]
    scene_testing: object
    npc_behavior: object
    chaos_variants: object
    thread_progress: object
    discovery_check: object
    npc_statistics: object
    thread_discovery_check: object
    discovery_fate_question: object
    fate_as_rpg_rules: object
    prepared_adventure_event_focus: object
    player_vs_pc_knowledge: object


_cache: dict[Path, MythicData] = {}


def load_mythic() -> MythicData:
    if _MYTHIC_DATA_PATH not in _cache:
        with _MYTHIC_DATA_PATH.open(encoding="utf-8") as f:
            _cache[_MYTHIC_DATA_PATH] = build_strict(MythicData, json.load(f), _MYTHIC_DATA_PATH.name)
        log(f"[Mythic] Loaded {_MYTHIC_DATA_PATH}")
    return _cache[_MYTHIC_DATA_PATH]
