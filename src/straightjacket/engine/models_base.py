"""Base model types: serialization helpers, resource tracks, world state, progress.

EngineConfig, Resources, ClockData, ProgressTrack, WorldState, ClockEvent, PlayerPreferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .engine_loader import eng
from .logging_util import log
from .serialization import SerializableMixin, deserialize, serialize


# ENGINE CONFIG (runtime, from UI)


@dataclass
class EngineConfig(SerializableMixin):
    """Runtime configuration passed to engine functions."""

    narration_lang: str = ""


@dataclass
class Resources(SerializableMixin):
    """Mutable resource tracks: health, spirit, supply, momentum.

    Start values live in resources.yaml and momentum.yaml. Construct via
    Resources.from_config() for a fresh-game instance; deserialize() supplies
    values from saved state.
    """

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
    """Single clock (threat, scheme, or progress).

    clock_type, segments, and trigger_description have no domain-safe default —
    clocks are always constructed by game mechanics that know all three. A clock
    without a trigger description is meaningless to the narrator. fired_at_scene
    defaults to 0 because it is legitimate runtime state ("not yet fired").
    """

    name: str
    clock_type: str  # threat, scheme, progress
    segments: int
    trigger_description: str
    filled: int = 0
    owner: str = ""
    fired: bool = False
    fired_at_scene: int = 0


@dataclass
class WorldState(SerializableMixin):
    """Physical world: location, time, chaos, clocks, combat position.

    chaos_factor has no default — fresh games must seed from chaos.yaml via
    WorldState.from_config(); restored games read the saved value. Construct
    via from_config() for a fresh-game instance. combat_position="" is
    legitimate runtime state: empty string means "not in combat".
    """

    chaos_factor: int
    current_location: str = ""
    current_scene_context: str = ""
    time_of_day: str = ""
    location_history: list[str] = field(default_factory=list)
    clocks: list[ClockData] = field(default_factory=list)
    combat_position: str = ""  # "in_control", "bad_spot", or "" (not in combat)

    @classmethod
    def from_config(cls) -> WorldState:
        return cls(chaos_factor=eng().chaos.start)

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


# Progress-track ticks-per-mark now live in engine.yaml under
# `progress.track_types.default.ticks_per_mark`. Do NOT confuse with
# engine.yaml `legacy.ticks_by_rank`, which is the inverse legacy-reward
# table (higher rank = more XP ticks on completion).


@dataclass
class ProgressTrack(SerializableMixin):
    """Ranked progress track (vows, connections, expeditions, combat, custom, legacy).

    All structural fields required — no universal default. ticks/status default
    to fresh-track values. Use ProgressTrack.new(rank=...) for max_ticks from
    engine.progress.max_ticks config.
    """

    # Ticks per filled box. Hardcoded in the Ironsworn track design (a track is
    # 10 boxes wide, 4 ticks fill one box). Used by filled_boxes and the
    # ticks_for_filled_boxes inverse helper. Not configurable: the box-tick
    # ratio defines the track shape itself, not a tunable value.
    TICKS_PER_BOX: ClassVar[int] = 4

    id: str
    name: str
    track_type: str  # vow, connection, expedition, combat, custom, legacy, scene_challenge
    rank: str  # troublesome, dangerous, formidable, extreme, epic
    max_ticks: int
    ticks: int = 0
    status: str = "active"  # active, completed, failed

    @classmethod
    def new(cls, *, id: str, name: str, track_type: str, rank: str, ticks: int = 0) -> ProgressTrack:
        """Fresh track with max_ticks from progress.yaml."""

        return cls(id=id, name=name, track_type=track_type, rank=rank, max_ticks=eng().progress.max_ticks, ticks=ticks)

    @property
    def ticks_per_mark(self) -> int:
        return eng().progress.ticks_per_mark(self.rank)

    @property
    def filled_boxes(self) -> int:
        return self.ticks // ProgressTrack.TICKS_PER_BOX

    def ticks_for_filled_boxes(self, filled_boxes: int) -> int:
        """Inverse of filled_boxes: clamp to max_ticks, return tick count for box count."""
        return min(self.max_ticks, filled_boxes * ProgressTrack.TICKS_PER_BOX)

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
    """Active threat with menace track competing against a vow's progress.

    All structural fields required — rank, max_menace_ticks, and description
    have no universal default. A threat without a description is meaningless
    to the narrator.
    """

    id: str
    name: str
    category: str  # one of THREAT_CATEGORIES
    linked_vow_id: str  # ProgressTrack id of the associated vow
    rank: str  # matches linked vow rank; determines menace tick size
    max_menace_ticks: int
    description: str
    menace_ticks: int = 0
    status: str = "active"  # active, resolved, overcome

    @classmethod
    def new(cls, *, id: str, name: str, category: str, linked_vow_id: str, rank: str, description: str) -> ThreatData:
        """Fresh threat with max_menace_ticks from progress.yaml."""

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
        # engine.yaml `progress.track_types.default.ticks_per_mark` is the
        # ticks-per-mark table for progress/menace tracks. Distinct from
        # engine.yaml's legacy.ticks_by_rank, which is the legacy-track reward
        # table (inverse scale).

        return eng().progress.ticks_per_mark(self.rank)

    @property
    def menace_filled_boxes(self) -> int:
        return self.menace_ticks // ProgressTrack.TICKS_PER_BOX

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

    threat_id: str
    threat_name: str
    ticks_added: int
    menace_full: bool
    source: str  # "miss", "random_event", "autonomous"


@dataclass
class ClockEvent(SerializableMixin):
    """A clock tick event from resolve_move_outcome or tick_autonomous_clocks."""

    clock: str
    trigger: str
    autonomous: bool
    triggered: bool


@dataclass
class RandomEvent(SerializableMixin):
    """Structured random event from Mythic GME 2e event pipeline.

    Assembled from: event focus (d100) + target selection + meaning table roll.
    Injected as <random_event> tag in narrator prompt.
    """

    focus: str  # event focus category (e.g. "npc_action", "pc_negative")
    focus_roll: int
    meaning_action: str  # verb from actions table
    meaning_subject: str  # subject from actions table
    meaning_table: str  # which meaning table was rolled
    source: str  # "fate_doublet", "interrupt_scene"
    target: str = ""  # selected NPC name, thread name, or empty
    target_id: str = ""  # NPC id or thread id


@dataclass
class FateResult(SerializableMixin):
    """Result of a fate question (Mythic GME 2e fate chart or fate check)."""

    answer: str  # yes, no, exceptional_yes, exceptional_no
    odds: str  # one of engine.fate.odds_levels
    chaos_factor: int
    method: str  # fate_chart, fate_check
    roll: int  # d100 for chart, 2d10 sum for check
    question: str
    random_event_triggered: bool = False
    random_event: RandomEvent | None = None


@dataclass
class PlayerPreferences(SerializableMixin):
    """Content boundaries and wishes (per-game, set at creation)."""

    player_wishes: str = ""
    content_lines: str = ""
