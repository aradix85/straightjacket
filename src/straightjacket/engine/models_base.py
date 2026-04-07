#!/usr/bin/env python3
"""Base model types: serialization helpers, resource tracks, world state.

EngineConfig, Resources, ClockData, WorldState, ClockEvent, PlayerPreferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .logging_util import log


# ── Generic serialization helpers ─────────────────────────────

def _fields_to_dict(obj: Any) -> dict:
    """Serialize a dataclass by iterating its fields. No nested type handling."""
    return {f.name: getattr(obj, f.name) for f in obj.__dataclass_fields__.values()}


def _fields_from_dict(cls: Any, data: dict) -> Any:
    """Deserialize a dataclass, filtering to known fields only."""
    known = {f.name for f in cls.__dataclass_fields__.values()}
    return cls(**{k: v for k, v in data.items() if k in known})


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

    def snapshot(self) -> dict:
        return _fields_to_dict(self)

    def restore(self, snap: dict) -> None:
        self.health = snap["health"]
        self.spirit = snap["spirit"]
        self.supply = snap["supply"]
        self.momentum = snap["momentum"]
        self.max_momentum = snap["max_momentum"]

    def to_dict(self) -> dict:
        return self.snapshot()

    @classmethod
    def from_dict(cls, data: dict) -> Resources:
        return cls(
            health=data["health"], spirit=data["spirit"], supply=data["supply"],
            momentum=data["momentum"], max_momentum=data["max_momentum"],
        )


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
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ClockData:
        return _fields_from_dict(cls, data)


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

    def snapshot(self) -> dict:
        return {
            "current_location": self.current_location,
            "current_scene_context": self.current_scene_context,
            "time_of_day": self.time_of_day,
            "location_history": list(self.location_history),
            "chaos_factor": self.chaos_factor,
            "clocks": [c.to_dict() for c in self.clocks],
        }

    def restore(self, snap: dict) -> None:
        self.current_location = snap["current_location"]
        self.current_scene_context = snap["current_scene_context"]
        self.time_of_day = snap["time_of_day"]
        self.location_history = list(snap["location_history"])
        self.chaos_factor = snap["chaos_factor"]
        self.clocks = [ClockData.from_dict(c) for c in snap["clocks"]]

    def to_dict(self) -> dict:
        return self.snapshot()

    @classmethod
    def from_dict(cls, data: dict) -> WorldState:
        return cls(
            current_location=data["current_location"],
            current_scene_context=data["current_scene_context"],
            time_of_day=data["time_of_day"],
            location_history=list(data["location_history"]),
            chaos_factor=data["chaos_factor"],
            clocks=[ClockData.from_dict(c) for c in data["clocks"]],
        )


@dataclass
class ClockEvent:
    """A clock tick event from apply_consequences or tick_autonomous_clocks."""
    clock: str = ""
    trigger: str = ""
    autonomous: bool = False
    triggered: bool = False

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ClockEvent:
        return _fields_from_dict(cls, data)


@dataclass
class PlayerPreferences:
    """Content boundaries and wishes (per-game, set at creation)."""
    player_wishes: str = ""
    content_lines: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PlayerPreferences:
        return _fields_from_dict(cls, data)
