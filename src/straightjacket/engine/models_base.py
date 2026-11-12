from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.serialization import SerializableMixin

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

_D = TypeVar("_D", bound="DataclassInstance")


def _overwrite(target: _D, source: _D) -> None:
    for f in dataclasses.fields(source):
        setattr(target, f.name, copy.deepcopy(getattr(source, f.name)))


@dataclass
class Resources(SerializableMixin):
    meters: dict[str, int]
    next_move_bonus: int

    def snapshot(self) -> Resources:
        return copy.deepcopy(self)

    def restore(self, snap: Resources) -> None:
        _overwrite(self, snap)


@dataclass
class ClockData(SerializableMixin):
    name: str
    clock_type: str
    segments: int
    trigger_description: str
    owner_kind: str
    creation_source: str
    filled: int
    owner_id: str | None
    fired: bool
    fired_at_scene: int


@dataclass
class ResolvedFact(SerializableMixin):
    about: str
    about_name: str
    fact_type: str
    answer: str
    location: str


@dataclass
class GeneratedEntity(SerializableMixin):
    category: str
    results: dict[str, str]


@dataclass
class PlaceRecord(SerializableMixin):
    name: str
    entity: GeneratedEntity


@dataclass
class WorldState(SerializableMixin):
    chaos_factor: int
    current_location: str
    current_scene_context: str
    time_of_day: str
    combat_position: str
    location_history: list[str] = field(default_factory=list)
    clocks: list[ClockData] = field(default_factory=list)
    pending_clock_fills: list[ClockFillResult] = field(default_factory=list)
    pending_threat_events: list[ThreatEvent] = field(default_factory=list)
    facts: list[ResolvedFact] = field(default_factory=list)
    places: list[PlaceRecord] = field(default_factory=list)

    def snapshot(self) -> WorldState:
        return copy.deepcopy(self)

    def restore(self, snap: WorldState) -> None:
        _overwrite(self, snap)


@dataclass
class ProgressTrack(SerializableMixin):
    id: str
    name: str
    track_type: str
    rank: str
    max_ticks: int
    bound_impact: str
    vowed_to: str | None
    ticks: int
    status: str
    completions: int


@dataclass
class ThreatData(SerializableMixin):
    id: str
    name: str
    category: str
    linked_vow_id: str | None
    rank: str
    max_menace_ticks: int
    description: str
    creation_source: str
    menace_ticks: int
    status: str

    @property
    def menace_full(self) -> bool:
        return self.menace_ticks >= self.max_menace_ticks


@dataclass
class ThreatEvent(SerializableMixin):
    threat_id: str
    threat_name: str
    menace_full: bool
    source: str
    development: str


@dataclass
class Consequence(SerializableMixin):
    kind: str
    texts: dict[str, str]
    numbers: dict[str, int]

    @property
    def label(self) -> str:
        return eng().ai_text.consequence_labels[self.kind].format(**self.texts, **self.numbers)


def consequence(consequence_kind: str, /, **values: str | int) -> Consequence:
    return Consequence(
        kind=consequence_kind,
        texts={name: value for name, value in values.items() if isinstance(value, str)},
        numbers={name: value for name, value in values.items() if isinstance(value, int)},
    )


def labels_of(consequences: list[Consequence]) -> list[str]:
    return [c.label for c in consequences]


@dataclass
class ClockEvent(SerializableMixin):
    clock: str
    trigger: str
    autonomous: bool
    triggered: bool


@dataclass
class ClockFillResult(SerializableMixin):
    clock_name: str
    clock_type: str
    tag_text: str


@dataclass
class RandomEvent(SerializableMixin):
    focus: str
    meaning_action: str
    meaning_subject: str
    source: str
    target: str
    target_id: str


@dataclass
class SceneSetup(SerializableMixin):
    scene_type: str
    interrupt_event: RandomEvent | None
    narrative_hint: str
    adjustments: list[str] = field(default_factory=list)


@dataclass
class FateResult(SerializableMixin):
    answer: str
    random_event_triggered: bool


@dataclass
class PlayerPreferences(SerializableMixin):
    player_wishes: str
    content_lines: str
