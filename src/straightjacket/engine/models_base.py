from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .engine_loader import eng
from .logging_util import log
from .serialization import SerializableMixin, deserialize, serialize


@dataclass
class Resources(SerializableMixin):
    health: int
    spirit: int
    supply: int
    momentum: int
    max_momentum: int
    next_move_bonus: int = 0

    @classmethod
    def from_config(cls) -> Resources:
        _e = eng()
        return cls(
            health=_e.resources.health_start,
            spirit=_e.resources.spirit_start,
            supply=_e.resources.supply_start,
            momentum=_e.momentum.start,
            max_momentum=_e.momentum.max,
        )

    def damage(self, track: str, amount: int) -> int:
        old = getattr(self, track)
        new = max(0, old - amount)
        setattr(self, track, new)
        actual: int = old - new
        if actual > 0:
            log(f"[Resources] {track} -{actual} ({old}→{new})")
        return actual

    def heal(self, track: str, amount: int, cap: int) -> int:
        old = getattr(self, track)
        new = min(cap, old + amount)
        setattr(self, track, new)
        actual: int = new - old
        if actual > 0:
            log(f"[Resources] {track} +{actual} ({old}→{new})")
        return actual

    def adjust_momentum(self, delta: int, floor: int, ceiling: int) -> None:
        old = self.momentum
        self.momentum = max(floor, min(ceiling, self.momentum + delta))
        if self.momentum != old:
            log(f"[Resources] momentum {'+' if delta > 0 else ''}{delta} ({old}→{self.momentum})")

    def reset_momentum(self, reset_floor: int, reset_value: int, max_cap: int) -> None:
        old = self.momentum
        self.momentum = max(reset_floor, reset_value - (max_cap - self.max_momentum))
        log(f"[Resources] momentum burned ({old}→{self.momentum})")

    def snapshot(self) -> dict[str, Any]:
        return serialize(self)

    def restore(self, snap: dict[str, Any]) -> None:
        restored = deserialize(Resources, snap)
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(restored, f))


@dataclass
class ClockData(SerializableMixin):
    name: str
    clock_type: str
    segments: int
    trigger_description: str
    owner_kind: str
    creation_source: str
    filled: int = 0
    owner_id: str | None = None
    fired: bool = False
    fired_at_scene: int = 0


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
    current_location: str = ""
    current_scene_context: str = ""
    time_of_day: str = ""
    location_history: list[str] = field(default_factory=list)
    clocks: list[ClockData] = field(default_factory=list)
    pending_clock_fills: list[ClockFillResult] = field(default_factory=list)
    pending_threat_events: list[ThreatEvent] = field(default_factory=list)
    combat_position: str = ""
    facts: list[ResolvedFact] = field(default_factory=list)
    places: list[PlaceRecord] = field(default_factory=list)

    @classmethod
    def from_config(cls) -> WorldState:
        return cls(chaos_factor=eng().chaos.start)

    def tick_chaos(self, direction: int) -> None:
        old = self.chaos_factor
        chaos = eng().chaos
        self.chaos_factor = max(chaos.min, min(chaos.max, self.chaos_factor + direction))
        if self.chaos_factor != old:
            log(f"[World] chaos {old}→{self.chaos_factor}")

    def snapshot(self) -> dict[str, Any]:
        return serialize(self)

    def restore(self, snap: dict[str, Any]) -> None:
        restored = deserialize(WorldState, snap)
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(restored, f))


@dataclass
class ProgressTrack(SerializableMixin):
    id: str
    name: str
    track_type: str
    rank: str
    max_ticks: int
    bound_impact: str
    ticks: int = 0
    status: str = "active"
    completions: int = 0

    @classmethod
    def new(cls, *, id: str, name: str, track_type: str, rank: str) -> ProgressTrack:
        return cls(
            id=id, name=name, track_type=track_type, rank=rank, max_ticks=eng().progress.max_ticks, bound_impact=""
        )

    @property
    def ticks_per_mark(self) -> int:
        return eng().progress.ticks_per_mark[self.rank]

    @property
    def filled_boxes(self) -> int:
        return self.ticks // eng().progress.ticks_per_box

    def ticks_for_filled_boxes(self, filled_boxes: int) -> int:
        return min(self.max_ticks, filled_boxes * eng().progress.ticks_per_box)

    def mark_progress(self) -> int:
        old = self.ticks
        self.ticks = min(self.max_ticks, self.ticks + self.ticks_per_mark)
        return self.ticks - old


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
    menace_ticks: int = 0
    status: str = "active"

    @classmethod
    def new(
        cls,
        *,
        id: str,
        name: str,
        category: str,
        linked_vow_id: str | None,
        rank: str,
        description: str,
        creation_source: str,
    ) -> ThreatData:
        return cls(
            id=id,
            name=name,
            category=category,
            linked_vow_id=linked_vow_id,
            rank=rank,
            max_menace_ticks=eng().progress.max_ticks,
            description=description,
            creation_source=creation_source,
        )

    @property
    def menace_per_mark(self) -> int:
        return eng().progress.ticks_per_mark[self.rank]

    @property
    def menace_filled_boxes(self) -> int:
        return self.menace_ticks // eng().progress.ticks_per_box

    @property
    def menace_total_boxes(self) -> int:
        return self.max_menace_ticks // eng().progress.ticks_per_box

    def advance_menace(self, marks: int) -> int:
        old = self.menace_ticks
        self.menace_ticks = min(self.max_menace_ticks, self.menace_ticks + self.menace_per_mark * marks)
        return self.menace_ticks - old

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
    values: dict[str, Any]

    @property
    def label(self) -> str:
        return eng().ai_text.consequence_labels[self.kind].format(**self.values)


def consequence(kind: str, /, **values: Any) -> Consequence:
    return Consequence(kind=kind, values=values)


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
    target: str = ""
    target_id: str = ""


@dataclass
class SceneSetup(SerializableMixin):
    scene_type: str
    adjustments: list[str] = field(default_factory=list)
    interrupt_event: RandomEvent | None = None
    narrative_hint: str = ""


@dataclass
class FateResult(SerializableMixin):
    answer: str
    random_event_triggered: bool


@dataclass
class PlayerPreferences(SerializableMixin):
    player_wishes: str = ""
    content_lines: str = ""
