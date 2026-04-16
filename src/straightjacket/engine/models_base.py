#!/usr/bin/env python3
"""Base model types: serialization helpers, resource tracks, world state, progress.

EngineConfig, Resources, ClockData, ProgressTrack, WorldState, ClockEvent, PlayerPreferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .logging_util import log
from .serialization import SerializableMixin, deserialize, serialize


# ENGINE CONFIG (runtime, from UI)


@dataclass
class EngineConfig(SerializableMixin):
    """Runtime configuration passed to engine functions."""

    narration_lang: str = ""


@dataclass
class Resources(SerializableMixin):
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
        return serialize(self)

    def restore(self, snap: dict) -> None:
        for k, v in snap.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class ClockData(SerializableMixin):
    """Single clock (threat, scheme, or progress). All fields explicit."""

    name: str = ""
    clock_type: str = "threat"
    segments: int = 6
    filled: int = 0
    trigger_description: str = ""
    owner: str = ""
    fired: bool = False
    fired_at_scene: int = 0


@dataclass
class WorldState(SerializableMixin):
    """Physical world: location, time, chaos, clocks, combat position."""

    current_location: str = ""
    current_scene_context: str = ""
    time_of_day: str = ""
    location_history: list[str] = field(default_factory=list)
    chaos_factor: int = 5
    clocks: list[ClockData] = field(default_factory=list)
    combat_position: str = ""  # "in_control", "bad_spot", or "" (not in combat)

    def tick_chaos(self, direction: int, floor: int = 1, ceiling: int = 9) -> None:
        """Adjust chaos factor. +1 on miss, -1 on strong hit or interrupt."""
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


PROGRESS_RANKS: dict[str, int] = {
    "troublesome": 12,  # 3 boxes (12 ticks) per mark
    "dangerous": 8,  # 2 boxes (8 ticks) per mark
    "formidable": 4,  # 1 box (4 ticks) per mark
    "extreme": 2,  # 2 ticks per mark
    "epic": 1,  # 1 tick per mark
}


@dataclass
class ProgressTrack(SerializableMixin):
    """Ranked progress track (vows, connections, expeditions, combat, custom)."""

    id: str = ""
    name: str = ""
    track_type: str = "vow"  # vow, connection, expedition, combat, custom
    rank: str = "dangerous"  # troublesome, dangerous, formidable, extreme, epic
    ticks: int = 0
    max_ticks: int = 40  # 10 boxes × 4 ticks
    status: str = "active"  # active, completed, failed

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
    """Active threat with menace track competing against a vow's progress."""

    id: str = ""
    name: str = ""
    category: str = ""  # one of THREAT_CATEGORIES
    description: str = ""
    linked_vow_id: str = ""  # ProgressTrack id of the associated vow
    rank: str = "dangerous"  # matches linked vow rank; determines menace tick size
    menace_ticks: int = 0
    max_menace_ticks: int = 40  # 10 boxes × 4 ticks
    status: str = "active"  # active, resolved, overcome

    @property
    def menace_per_mark(self) -> int:
        return PROGRESS_RANKS.get(self.rank, 8)

    @property
    def menace_filled_boxes(self) -> int:
        return self.menace_ticks // 4

    def advance_menace(self, marks: int = 1) -> int:
        """Advance menace track. Returns ticks added."""
        old = self.menace_ticks
        self.menace_ticks = min(self.max_menace_ticks, self.menace_ticks + self.menace_per_mark * marks)
        return self.menace_ticks - old

    @property
    def menace_full(self) -> bool:
        return self.menace_ticks >= self.max_menace_ticks


@dataclass
class ThreatEvent(SerializableMixin):
    """A menace advancement event, parallel to ClockEvent."""

    threat_id: str = ""
    threat_name: str = ""
    ticks_added: int = 0
    menace_full: bool = False
    source: str = ""  # "miss", "random_event", "autonomous"


@dataclass
class ClockEvent(SerializableMixin):
    """A clock tick event from resolve_move_outcome or tick_autonomous_clocks."""

    clock: str = ""
    trigger: str = ""
    autonomous: bool = False
    triggered: bool = False


@dataclass
class RandomEvent(SerializableMixin):
    """Structured random event from Mythic GME 2e event pipeline.

    Assembled from: event focus (d100) + target selection + meaning table roll.
    Injected as <random_event> tag in narrator prompt.
    """

    focus: str = ""  # event focus category (e.g. "npc_action", "pc_negative")
    focus_roll: int = 0
    target: str = ""  # selected NPC name, thread name, or empty
    target_id: str = ""  # NPC id or thread id
    meaning_action: str = ""  # verb from actions table
    meaning_subject: str = ""  # subject from actions table
    meaning_table: str = "actions"  # which meaning table was used
    source: str = ""  # "fate_doublet", "interrupt_scene"


@dataclass
class FateResult(SerializableMixin):
    """Result of a fate question (Mythic GME 2e fate chart or fate check)."""

    answer: str = ""  # yes, no, exceptional_yes, exceptional_no
    odds: str = "fifty_fifty"
    chaos_factor: int = 5
    method: str = "fate_chart"  # fate_chart, fate_check
    roll: int = 0  # d100 for chart, 2d10 sum for check
    random_event_triggered: bool = False
    random_event: RandomEvent | None = None
    question: str = ""


@dataclass
class PlayerPreferences(SerializableMixin):
    """Content boundaries and wishes (per-game, set at creation)."""

    player_wishes: str = ""
    content_lines: str = ""
