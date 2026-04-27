from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .engine_loader import eng
from .logging_util import log
from .serialization import SerializableMixin, deserialize, serialize


@dataclass
class EngineConfig(SerializableMixin):
    narration_lang: str = ""


@dataclass
class Resources(SerializableMixin):
    health: int
    spirit: int
    supply: int
    momentum: int
    max_momentum: int

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

    def damage(self, track: str, amount: int, floor: int = 0) -> int:
        old = getattr(self, track)
        new = max(floor, old - amount)
        setattr(self, track, new)
        actual = old - new
        if actual > 0:
            log(f"[Resources] {track} -{actual} ({old}→{new})")
        return actual

    def heal(self, track: str, amount: int, cap: int) -> int:
        old = getattr(self, track)
        new = min(cap, old + amount)
        setattr(self, track, new)
        actual = new - old
        if actual > 0:
            log(f"[Resources] {track} +{actual} ({old}→{new})")
        return actual

    def adjust_momentum(self, delta: int, floor: int, ceiling: int) -> None:
        old = self.momentum
        self.momentum = max(floor, min(ceiling, self.momentum + delta))
        if self.momentum != old:
            log(f"[Resources] momentum {'+' if delta > 0 else ''}{delta} ({old}→{self.momentum})")

    def reset_momentum(self, floor: int, reset_value: int, max_cap: int) -> None:
        old = self.momentum
        self.momentum = max(floor, reset_value - (max_cap - self.max_momentum))
        log(f"[Resources] momentum burned ({old}→{self.momentum})")

    def snapshot(self) -> dict:
        return serialize(self)

    def restore(self, snap: dict) -> None:
        for k, v in snap.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class ClockData(SerializableMixin):
    name: str
    clock_type: str
    segments: int
    trigger_description: str
    filled: int = 0
    owner: str = ""
    fired: bool = False
    fired_at_scene: int = 0


@dataclass
class WorldState(SerializableMixin):
    chaos_factor: int
    current_location: str = ""
    current_scene_context: str = ""
    time_of_day: str = ""
    location_history: list[str] = field(default_factory=list)
    clocks: list[ClockData] = field(default_factory=list)
    combat_position: str = ""

    @classmethod
    def from_config(cls) -> WorldState:
        return cls(chaos_factor=eng().chaos.start)

    def tick_chaos(self, direction: int, floor: int = 1, ceiling: int = 9) -> None:
        old = self.chaos_factor
        self.chaos_factor = max(floor, min(ceiling, self.chaos_factor + direction))
        if self.chaos_factor != old:
            log(f"[World] chaos {old}→{self.chaos_factor}")

    def snapshot(self) -> dict:
        return serialize(self)

    def restore(self, snap: dict) -> None:
        restored = deserialize(WorldState, snap)
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(restored, f))


@dataclass
class ProgressTrack(SerializableMixin):
    TICKS_PER_BOX: ClassVar[int] = 4

    id: str
    name: str
    track_type: str
    rank: str
    max_ticks: int
    ticks: int = 0
    status: str = "active"

    @classmethod
    def new(cls, *, id: str, name: str, track_type: str, rank: str, ticks: int = 0) -> ProgressTrack:
        return cls(id=id, name=name, track_type=track_type, rank=rank, max_ticks=eng().progress.max_ticks, ticks=ticks)

    @property
    def ticks_per_mark(self) -> int:
        return eng().progress.ticks_per_mark(self.rank)

    @property
    def filled_boxes(self) -> int:
        return self.ticks // ProgressTrack.TICKS_PER_BOX

    def ticks_for_filled_boxes(self, filled_boxes: int) -> int:
        return min(self.max_ticks, filled_boxes * ProgressTrack.TICKS_PER_BOX)

    def mark_progress(self) -> int:
        old = self.ticks
        self.ticks = min(self.max_ticks, self.ticks + self.ticks_per_mark)
        return self.ticks - old


THREAT_CATEGORIES: tuple[str, ...] = (
    "burgeoning_conflict",
    "cursed_site",
    "environmental_calamity",
    "malignant_plague",
    "rampaging_creature",
    "ravaging_horde",
    "scheming_leader",
    "power_hungry_mystic",
    "zealous_cult",
)


@dataclass
class ThreatData(SerializableMixin):
    id: str
    name: str
    category: str
    linked_vow_id: str
    rank: str
    max_menace_ticks: int
    description: str
    menace_ticks: int = 0
    status: str = "active"

    @classmethod
    def new(cls, *, id: str, name: str, category: str, linked_vow_id: str, rank: str, description: str) -> ThreatData:
        return cls(
            id=id,
            name=name,
            category=category,
            linked_vow_id=linked_vow_id,
            rank=rank,
            max_menace_ticks=eng().progress.max_ticks,
            description=description,
        )

    @property
    def menace_per_mark(self) -> int:
        return eng().progress.ticks_per_mark(self.rank)

    @property
    def menace_filled_boxes(self) -> int:
        return self.menace_ticks // ProgressTrack.TICKS_PER_BOX

    def advance_menace(self, marks: int = 1) -> int:
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
    ticks_added: int
    menace_full: bool
    source: str


@dataclass
class ClockEvent(SerializableMixin):
    clock: str
    trigger: str
    autonomous: bool
    triggered: bool


@dataclass
class ConsequenceEvent(SerializableMixin):
    event_code: str
    subject: str
    acceptable_phrasings: list[str] = field(default_factory=list)


@dataclass
class RandomEvent(SerializableMixin):
    focus: str
    focus_roll: int
    meaning_action: str
    meaning_subject: str
    meaning_table: str
    source: str
    target: str = ""
    target_id: str = ""


@dataclass
class FateResult(SerializableMixin):
    answer: str
    odds: str
    chaos_factor: int
    method: str
    roll: int
    question: str
    random_event_triggered: bool = False
    random_event: RandomEvent | None = None


@dataclass
class PlayerPreferences(SerializableMixin):
    player_wishes: str = ""
    content_lines: str = ""
