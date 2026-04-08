#!/usr/bin/env python3
"""Base model types: serialization helpers, resource tracks, world state, progress.

EngineConfig, Resources, ClockData, ProgressTrack, WorldState, ClockEvent, PlayerPreferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .logging_util import log
from .serialization import deserialize, serialize


# ENGINE CONFIG (runtime, from UI)


@dataclass
class EngineConfig:
    """Runtime configuration passed to engine functions."""

    narration_lang: str = ""


@dataclass
class Resources:
    """Mutable resource tracks: health, spirit, supply, momentum."""

    health: int = 5
    spirit: int = 5
    supply: int = 5
    momentum: int = 2
    max_momentum: int = 10

    def damage(self, track: str, amount: int, floor: int = 0) -> int:
        """Reduce a track by amount, clamped to floor. Returns actual loss."""
        old = getattr(self, track)
        new = max(floor, old - amount)
        setattr(self, track, new)
        actual = old - new
        if actual > 0:
            log(f"[Resources] {track} -{actual} ({old}→{new})")
        return actual

    def heal(self, track: str, amount: int, cap: int) -> int:
        """Increase a track by amount, clamped to cap. Returns actual gain."""
        old = getattr(self, track)
        new = min(cap, old + amount)
        setattr(self, track, new)
        actual = new - old
        if actual > 0:
            log(f"[Resources] {track} +{actual} ({old}→{new})")
        return actual

    def adjust_momentum(self, delta: int, floor: int, ceiling: int) -> None:
        """Change momentum by delta, clamped to [floor, ceiling]."""
        old = self.momentum
        self.momentum = max(floor, min(ceiling, self.momentum + delta))
        if self.momentum != old:
            log(f"[Resources] momentum {'+' if delta > 0 else ''}{delta} ({old}→{self.momentum})")

    def reset_momentum(self, floor: int, reset_value: int, max_cap: int) -> None:
        """Reset momentum after burn. Drops to reset_value adjusted for max_momentum cap."""
        old = self.momentum
        self.momentum = max(floor, reset_value - (max_cap - self.max_momentum))
        log(f"[Resources] momentum burned ({old}→{self.momentum})")

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> Resources:
        return deserialize(cls, data)

    def snapshot(self) -> dict:
        return serialize(self)

    def restore(self, snap: dict) -> None:
        for k, v in snap.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class ClockData:
    """Single clock (threat, scheme, or progress). All fields explicit."""

    name: str = ""
    clock_type: str = "threat"
    segments: int = 6
    filled: int = 0
    trigger_description: str = ""
    owner: str = ""
    fired: bool = False
    fired_at_scene: int = 0

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> ClockData:
        return deserialize(cls, data)


@dataclass
class WorldState:
    """Physical world: location, time, chaos, clocks."""

    current_location: str = ""
    current_scene_context: str = ""
    time_of_day: str = ""
    location_history: list[str] = field(default_factory=list)
    chaos_factor: int = 5
    clocks: list[ClockData] = field(default_factory=list)

    def tick_chaos(self, direction: int, floor: int = 3, ceiling: int = 9) -> None:
        """Adjust chaos factor. +1 on miss, -1 on strong hit or interrupt."""
        old = self.chaos_factor
        self.chaos_factor = max(floor, min(ceiling, self.chaos_factor + direction))
        if self.chaos_factor != old:
            log(f"[World] chaos {old}→{self.chaos_factor}")

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> WorldState:
        return deserialize(cls, data)

    def snapshot(self) -> dict:
        return serialize(self)

    def restore(self, snap: dict) -> None:
        restored = deserialize(WorldState, snap)
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(restored, f))


PROGRESS_RANKS: dict[str, int] = {
    "troublesome": 12,  # 3 boxes (12 ticks) per mark
    "dangerous": 8,  # 2 boxes (8 ticks) per mark
    "formidable": 4,  # 1 box (4 ticks) per mark
    "extreme": 2,  # 2 ticks per mark
    "epic": 1,  # 1 tick per mark
}


@dataclass
class ProgressTrack:
    """Ranked progress track (vows, connections, expeditions, combat, custom)."""

    id: str = ""
    name: str = ""
    track_type: str = "vow"  # vow, connection, expedition, combat, custom
    rank: str = "dangerous"  # troublesome, dangerous, formidable, extreme, epic
    ticks: int = 0
    max_ticks: int = 40  # 10 boxes × 4 ticks

    @property
    def ticks_per_mark(self) -> int:
        return PROGRESS_RANKS.get(self.rank, 8)

    @property
    def filled_boxes(self) -> int:
        return self.ticks // 4

    def mark_progress(self) -> int:
        """Mark progress: add ticks_per_mark, clamped to max. Returns ticks added."""
        old = self.ticks
        self.ticks = min(self.max_ticks, self.ticks + self.ticks_per_mark)
        return self.ticks - old

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> ProgressTrack:
        return deserialize(cls, data)


@dataclass
class ClockEvent:
    """A clock tick event from apply_consequences or tick_autonomous_clocks."""

    clock: str = ""
    trigger: str = ""
    autonomous: bool = False
    triggered: bool = False

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> ClockEvent:
        return deserialize(cls, data)


@dataclass
class PlayerPreferences:
    """Content boundaries and wishes (per-game, set at creation)."""

    player_wishes: str = ""
    content_lines: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> PlayerPreferences:
        return deserialize(cls, data)
