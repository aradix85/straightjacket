#!/usr/bin/env python3
"""Straightjacket data models: EngineConfig, GameState (with sub-objects), RollResult.

GameState is decomposed into logical groups:
- Resources: health, spirit, supply, momentum (tracks that change every turn)
- WorldState: location, time, chaos, clocks (the physical world)
- NarrativeState: scene tracking, history, story arc, director guidance
- CampaignState: chapter progression, epilogue
- PlayerPreferences: content boundaries and wishes

Each group owns its fields and provides mutation methods with clamping/logging.
GameState provides snapshot()/restore() for atomic undo (correction, burn).
GameState provides to_dict()/from_dict() for serialization (replaces SAVE_FIELDS).

Serialization helpers:
- _fields_to_dict(obj): generic field-iteration serializer for flat dataclasses.
- _fields_from_dict(cls, data): generic known-field-filter deserializer.
Classes with nested types or special logic override to_dict/from_dict directly.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

from .logging_util import log


# ── Generic serialization helpers ─────────────────────────────
# Used by flat dataclasses whose fields are all primitives or lists of primitives.
# Classes with nested dataclass fields (e.g. list[ClockData]) override manually.

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
    """Runtime configuration passed to engine functions.
    The UI layer populates this from session state; defaults here are structural
    fallbacks only. Actual defaults come from config.yaml via config_loader.
    """
    narration_lang: str = ""

# SUB-OBJECTS

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
    clock_type: str = "threat"          # threat, scheme, progress
    segments: int = 6
    filled: int = 0
    trigger_description: str = ""
    owner: str = ""                     # NPC name or "world"
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
class SceneLogEntry:
    """One entry in the session log. Created per turn/correction."""

    scene: int = 0
    summary: str = ""
    move: str = ""
    result: str = ""
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str = "risky"
    effect: str = "standard"
    dramatic_question: str = ""
    chaos_interrupt: str | None = None
    npc_activation: dict = field(default_factory=dict)
    validator: dict = field(default_factory=dict)
    rich_summary: str = ""              # Set by Director after the fact
    director_trigger: str = ""          # Set by turn pipeline after the fact
    revelation_check: dict = field(default_factory=dict)  # {id, confirmed} when a revelation was pending

    def to_dict(self) -> dict:
        d = {}
        for f in self.__dataclass_fields__.values():
            val = getattr(self, f.name)
            if f.name == "clock_events":
                d[f.name] = [e.to_dict() for e in val]
            else:
                d[f.name] = val
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SceneLogEntry:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        if "clock_events" in kwargs and isinstance(kwargs["clock_events"], list):
            kwargs["clock_events"] = [ClockEvent.from_dict(e) for e in kwargs["clock_events"]]
        return cls(**kwargs)

@dataclass
class NarrationEntry:
    """One entry in narration history. Used for narrator conversation context."""

    scene: int = 0
    prompt_summary: str = ""
    narration: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NarrationEntry:
        return _fields_from_dict(cls, data)

@dataclass
class StoryAct:
    """Single act in a story blueprint."""
    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StoryAct:
        return _fields_from_dict(cls, data)

@dataclass
class CurrentAct:
    """Computed act info from get_current_act(). StoryAct fields plus runtime state."""
    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""
    act_number: int = 1
    total_acts: int = 3
    progress: str = "early"
    approaching_end: bool = False

@dataclass
class Revelation:
    """Story revelation with timing and weight."""
    id: str = ""
    content: str = ""
    earliest_scene: int = 999
    dramatic_weight: str = "medium"

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Revelation:
        return _fields_from_dict(cls, data)

@dataclass
class PossibleEnding:
    """Possible story ending."""
    type: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PossibleEnding:
        return _fields_from_dict(cls, data)

@dataclass
class StoryBlueprint:
    """Story architect output. Tracks act structure, revelations, and completion.

    Runtime fields (revealed, triggered_transitions, story_complete) are
    mutated by the engine during play. The rest is set once by the architect.
    """
    central_conflict: str = ""
    antagonist_force: str = ""
    thematic_thread: str = ""
    structure_type: str = "3act"
    acts: list[StoryAct] = field(default_factory=list)
    revelations: list[Revelation] = field(default_factory=list)
    possible_endings: list[PossibleEnding] = field(default_factory=list)
    # Runtime state (mutated during play)
    revealed: list[str] = field(default_factory=list)
    triggered_transitions: list[str] = field(default_factory=list)
    triggered_director_phases: list[str] = field(default_factory=list)
    story_complete: bool = False

    def to_dict(self) -> dict:
        return {
            "central_conflict": self.central_conflict,
            "antagonist_force": self.antagonist_force,
            "thematic_thread": self.thematic_thread,
            "structure_type": self.structure_type,
            "acts": [a.to_dict() for a in self.acts],
            "revelations": [r.to_dict() for r in self.revelations],
            "possible_endings": [e.to_dict() for e in self.possible_endings],
            "revealed": list(self.revealed),
            "triggered_transitions": list(self.triggered_transitions),
            "triggered_director_phases": list(self.triggered_director_phases),
            "story_complete": self.story_complete,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StoryBlueprint:
        """Deserialize from own to_dict() output. Call sites that pass raw AI
        output must sanitize missing keys before calling this."""
        bp = cls(
            central_conflict=data["central_conflict"],
            antagonist_force=data["antagonist_force"],
            thematic_thread=data["thematic_thread"],
            structure_type=data["structure_type"],
            revealed=list(data["revealed"]),
            triggered_transitions=list(data["triggered_transitions"]),
            triggered_director_phases=list(data.get("triggered_director_phases", [])),
            story_complete=bool(data["story_complete"]),
        )
        bp.acts = [StoryAct.from_dict(a) for a in data["acts"]]
        bp.revelations = [Revelation.from_dict(r) for r in data["revelations"]]
        bp.possible_endings = [PossibleEnding.from_dict(e) for e in data["possible_endings"]]
        return bp

    @property
    def has_acts(self) -> bool:
        """Convenience: check if blueprint has act structure."""
        return bool(self.acts)

@dataclass
class DirectorGuidance:
    """Director output stored between turns for narrator context."""
    narrator_guidance: str = ""
    npc_guidance: dict[str, str] = field(default_factory=dict)
    pacing: str = ""
    arc_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "narrator_guidance": self.narrator_guidance,
            "npc_guidance": dict(self.npc_guidance),
            "pacing": self.pacing,
            "arc_notes": self.arc_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DirectorGuidance:
        return cls(
            narrator_guidance=data["narrator_guidance"],
            npc_guidance=dict(data["npc_guidance"]),
            pacing=data["pacing"],
            arc_notes=data["arc_notes"],
        )

@dataclass
class NarrativeState:
    """Scene tracking, history, story arc, director guidance."""
    scene_count: int = 0
    session_log: list[SceneLogEntry] = field(default_factory=list)
    narration_history: list[NarrationEntry] = field(default_factory=list)
    story_blueprint: StoryBlueprint | None = None
    director_guidance: DirectorGuidance = field(default_factory=DirectorGuidance)
    scene_intensity_history: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "scene_count": self.scene_count,
            "session_log_len": len(self.session_log),
            "narration_history_len": len(self.narration_history),
            "director_guidance": self.director_guidance.to_dict(),
            "scene_intensity_history": list(self.scene_intensity_history),
            "story_blueprint_snapshot": {
                "revealed": list(self.story_blueprint.revealed),
                "triggered_transitions": list(self.story_blueprint.triggered_transitions),
                "triggered_director_phases": list(self.story_blueprint.triggered_director_phases),
                "story_complete": self.story_blueprint.story_complete,
            } if self.story_blueprint else None,
        }

    def restore(self, snap: dict) -> None:
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        # Trim lists back to pre-turn length (remove entries added during the turn)
        self.session_log = self.session_log[:snap["session_log_len"]]
        self.narration_history = self.narration_history[:snap["narration_history_len"]]
        # Blueprint sub-fields
        bp_snap = snap["story_blueprint_snapshot"]
        if bp_snap is not None and self.story_blueprint is not None:
            self.story_blueprint.revealed = list(bp_snap["revealed"])
            self.story_blueprint.triggered_transitions = list(bp_snap["triggered_transitions"])
            self.story_blueprint.triggered_director_phases = list(bp_snap.get("triggered_director_phases", []))
            self.story_blueprint.story_complete = bp_snap["story_complete"]

    def to_dict(self) -> dict:
        return {
            "scene_count": self.scene_count,
            "session_log": [e.to_dict() for e in self.session_log],
            "narration_history": [e.to_dict() for e in self.narration_history],
            "story_blueprint": self.story_blueprint.to_dict() if self.story_blueprint else None,
            "director_guidance": self.director_guidance.to_dict(),
            "scene_intensity_history": list(self.scene_intensity_history),
        }

    @classmethod
    def from_dict(cls, data: dict) -> NarrativeState:
        n = cls()
        n.scene_count = data["scene_count"]
        n.session_log = [SceneLogEntry.from_dict(e) for e in data["session_log"]]
        n.narration_history = [NarrationEntry.from_dict(e) for e in data["narration_history"]]
        bp = data["story_blueprint"]
        n.story_blueprint = StoryBlueprint.from_dict(bp) if bp is not None else None
        n.director_guidance = DirectorGuidance.from_dict(data["director_guidance"])
        n.scene_intensity_history = list(data["scene_intensity_history"])
        return n

@dataclass
class NpcEvolution:
    """Projected NPC change from chapter summary."""
    name: str = ""
    projection: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NpcEvolution:
        return _fields_from_dict(cls, data)

@dataclass
class ChapterSummary:
    """Summary of a completed chapter for campaign continuity."""
    chapter: int = 0
    title: str = ""
    summary: str = ""
    unresolved_threads: list[str] = field(default_factory=list)
    character_growth: str = ""
    npc_evolutions: list[NpcEvolution] = field(default_factory=list)
    thematic_question: str = ""
    post_story_location: str = ""
    scenes: int = 0

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "title": self.title,
            "summary": self.summary,
            "unresolved_threads": list(self.unresolved_threads),
            "character_growth": self.character_growth,
            "npc_evolutions": [e.to_dict() for e in self.npc_evolutions],
            "thematic_question": self.thematic_question,
            "post_story_location": self.post_story_location,
            "scenes": self.scenes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChapterSummary:
        evolutions = [NpcEvolution.from_dict(e) for e in data["npc_evolutions"]]
        return cls(
            chapter=data["chapter"],
            title=data["title"],
            summary=data["summary"],
            unresolved_threads=list(data["unresolved_threads"]),
            character_growth=data["character_growth"],
            npc_evolutions=evolutions,
            thematic_question=data["thematic_question"],
            post_story_location=data["post_story_location"],
            scenes=data["scenes"],
        )

@dataclass
class CampaignState:
    """Chapter progression and epilogue."""
    campaign_history: list[ChapterSummary] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_shown: bool = False
    epilogue_dismissed: bool = False
    epilogue_text: str = ""

    def snapshot(self) -> dict:
        """Only epilogue flags — chapter_number and campaign_history are
        never mutated within a turn, so correction/burn doesn't need them."""
        return {
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
        }

    def restore(self, snap: dict) -> None:
        self.epilogue_shown = snap["epilogue_shown"]
        self.epilogue_dismissed = snap["epilogue_dismissed"]

    def to_dict(self) -> dict:
        return {
            "campaign_history": [ch.to_dict() for ch in self.campaign_history],
            "chapter_number": self.chapter_number,
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
            "epilogue_text": self.epilogue_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CampaignState:
        return cls(
            campaign_history=[ChapterSummary.from_dict(ch) for ch in data["campaign_history"]],
            chapter_number=data["chapter_number"],
            epilogue_shown=data["epilogue_shown"],
            epilogue_dismissed=data["epilogue_dismissed"],
            epilogue_text=data["epilogue_text"],
        )

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

# NPC MEMORY ENTRY

@dataclass
class MemoryEntry:
    """Single NPC memory (observation or reflection). All fields explicit."""

    scene: int = 0
    event: str = ""
    emotional_weight: str = "neutral"
    importance: int = 3
    type: str = "observation"           # observation, reflection
    about_npc: str | None = None
    tone: str = ""                      # Narrative compound (e.g. "protective_guilt")
    tone_key: str = ""                  # Machine-readable enum word
    _score_debug: str = ""              # Debug info from score_importance

    def to_dict(self) -> dict:
        d = _fields_to_dict(self)
        # Strip private debug field from serialization if empty
        if not d.get("_score_debug"):
            d.pop("_score_debug", None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return _fields_from_dict(cls, data)

# NPC DATA

@dataclass
class NpcData:
    """Single NPC. All fields explicit with defaults.
    to_dict()/from_dict() for serialization. No dict-style access.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    agenda: str = ""
    instinct: str = ""
    arc: str = ""                       # Narrative trajectory — set by Director, evolves each reflection
    secrets: list[str] = field(default_factory=list)
    disposition: str = "neutral"
    bond: int = 0
    bond_max: int = 4
    status: str = "active"
    memory: list[MemoryEntry] = field(default_factory=list)
    introduced: bool = True
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    importance_accumulator: int = 0
    last_reflection_scene: int = 0
    last_location: str = ""
    needs_reflection: bool = False

    def to_dict(self) -> dict:
        d = {}
        for f in self.__dataclass_fields__.values():
            val = getattr(self, f.name)
            if f.name == "memory":
                d[f.name] = [m.to_dict() for m in val]
            elif f.name in ("secrets", "aliases", "keywords"):
                d[f.name] = list(val)
            else:
                d[f.name] = val
        return d

    @classmethod
    def from_dict(cls, data: dict) -> NpcData:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs: dict[str, Any] = {}
        for k, v in data.items():
            if k == "memory" and isinstance(v, list):
                kwargs["memory"] = [MemoryEntry.from_dict(m) for m in v]
            elif k in known:
                kwargs[k] = v
        return cls(**kwargs)

# TURN SNAPSHOT

@dataclass
class TurnSnapshot:
    """Snapshot of game state plus turn context for correction/burn.

    State fields (resources, world, etc.) are stored as dicts for restore().
    Turn context (player_input, brain, roll, narration) is set during turn processing.
    """
    # State snapshot (for restore)
    resources: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    narrative: dict = field(default_factory=dict)
    campaign: dict = field(default_factory=dict)
    npcs: list[dict] = field(default_factory=list)
    crisis_mode: bool = False
    game_over: bool = False
    # Turn context (set during processing)
    player_input: str = ""
    brain: BrainResult | None = None
    roll: RollResult | None = None
    narration: str | None = None

    def to_dict(self) -> dict:
        d = {
            "resources": self.resources,
            "world": self.world,
            "narrative": self.narrative,
            "campaign": self.campaign,
            "npcs": self.npcs,
            "crisis_mode": self.crisis_mode,
            "game_over": self.game_over,
            "player_input": self.player_input,
            "brain": _fields_to_dict(self.brain) if self.brain else None,
            "narration": self.narration,
        }
        if self.roll is not None:
            d["roll"] = dataclasses.asdict(self.roll)
        else:
            d["roll"] = None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TurnSnapshot:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        snap = cls(**kwargs)
        # Reconstruct RollResult from persisted dict
        if isinstance(snap.roll, dict):
            try:
                snap.roll = RollResult(**snap.roll)
            except (TypeError, KeyError):
                snap.roll = None
        # Reconstruct BrainResult from persisted dict
        if isinstance(snap.brain, dict):
            snap.brain = BrainResult.from_dict(snap.brain)
        return snap


# GAME STATE

@dataclass
class GameState:
    """Complete game state. Sub-objects own logically grouped fields.

    Fields that don't fit a sub-object stay on GameState directly:
    - Character identity (player_name, concept, stats, archetype, backstory)
    - Setting description (genre, tone, description)
    - NPCs (complex nested list, accessed everywhere)
    - Flags (crisis_mode, game_over)
    - last_turn_snapshot (transient, for correction/burn)
    """

    # ── Character identity ────────────────────────────────────
    player_name: str = ""
    character_concept: str = ""
    pronouns: str = ""               # "he/him", "she/her", "they/them", or custom
    paths: list[str] = field(default_factory=list)  # 2 Datasworn path IDs
    background_vow: str = ""         # What drives this character
    setting_id: str = ""             # Setting package ID (e.g. "starforged")
    setting_genre: str = ""
    setting_tone: str = ""
    setting_archetype: str = ""
    setting_description: str = ""
    edge: int = 1
    heart: int = 2
    iron: int = 1
    shadow: int = 1
    wits: int = 2
    backstory: str = ""

    # ── Sub-objects ────────────────────────────────────────────
    resources: Resources = field(default_factory=Resources)
    world: WorldState = field(default_factory=WorldState)
    narrative: NarrativeState = field(default_factory=NarrativeState)
    campaign: CampaignState = field(default_factory=CampaignState)
    preferences: PlayerPreferences = field(default_factory=PlayerPreferences)

    # ── Shared mutable state ──────────────────────────────────
    npcs: list[NpcData] = field(default_factory=list)
    crisis_mode: bool = False
    game_over: bool = False

    # ── Transient ─────────────────────────────────────────────
    last_turn_snapshot: TurnSnapshot | None = field(default=None, repr=False)
    post_epilogue_director_done: bool = field(default=False, repr=False)

    # ── Convenience accessors ─────────────────────────────────
    # These exist ONLY for get_stat() which needs to reach character stats.
    # All resource/world/narrative access goes through the sub-objects.

    def get_stat(self, name: str) -> int:
        """Get a character stat by name (edge/heart/iron/shadow/wits)."""
        return getattr(self, name, 0)

    # ── Snapshot / Restore ────────────────────────────────────

    def snapshot(self) -> TurnSnapshot:
        """Complete snapshot of all mutable state. Called once at turn start.
        Returns a TurnSnapshot — only restore() knows how to unpack it.
        """
        return TurnSnapshot(
            resources=self.resources.snapshot(),
            world=self.world.snapshot(),
            narrative=self.narrative.snapshot(),
            campaign=self.campaign.snapshot(),
            npcs=[n.to_dict() for n in self.npcs],
            crisis_mode=self.crisis_mode,
            game_over=self.game_over,
        )

    def restore(self, snap: TurnSnapshot) -> None:
        """Restore all mutable state from a snapshot. Used by correction and burn."""
        self.resources.restore(snap.resources)
        self.world.restore(snap.world)
        self.narrative.restore(snap.narrative)
        self.campaign.restore(snap.campaign)
        self.npcs = [NpcData.from_dict(n) for n in snap.npcs]
        self.crisis_mode = snap.crisis_mode
        self.game_over = snap.game_over
        log(f"[GameState] Restored from snapshot: "
            f"H{self.resources.health} Sp{self.resources.spirit} "
            f"Su{self.resources.supply} Chaos{self.world.chaos_factor}")

    # ── Serialization ─────────────────────────────────────────

    _IDENTITY_FIELDS = (
        "player_name", "character_concept", "pronouns", "paths",
        "background_vow", "setting_id", "setting_genre",
        "setting_tone", "setting_archetype", "setting_description",
        "edge", "heart", "iron", "shadow", "wits", "backstory",
    )

    _SUB_OBJECTS = ("resources", "world", "narrative", "campaign", "preferences")

    def to_dict(self) -> dict:
        """Serialize to nested dict for JSON persistence."""
        d = {k: getattr(self, k) for k in self._IDENTITY_FIELDS}
        for name in self._SUB_OBJECTS:
            d[name] = getattr(self, name).to_dict()
        d["npcs"] = [n.to_dict() for n in self.npcs]
        d["crisis_mode"] = self.crisis_mode
        d["game_over"] = self.game_over
        d["last_turn_snapshot"] = self.last_turn_snapshot.to_dict() if self.last_turn_snapshot else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GameState:
        """Deserialize from nested dict."""
        game = cls()
        for k in cls._IDENTITY_FIELDS:
            setattr(game, k, data[k])
        game.resources = Resources.from_dict(data["resources"])
        game.world = WorldState.from_dict(data["world"])
        game.narrative = NarrativeState.from_dict(data["narrative"])
        game.campaign = CampaignState.from_dict(data["campaign"])
        game.preferences = PlayerPreferences.from_dict(data["preferences"])
        game.npcs = [NpcData.from_dict(n) for n in data["npcs"]]
        game.crisis_mode = data["crisis_mode"]
        game.game_over = data["game_over"]
        snap = data["last_turn_snapshot"]
        game.last_turn_snapshot = TurnSnapshot.from_dict(snap) if snap is not None else None
        return game

# ROLL RESULT

@dataclass
class RollResult:
    d1: int
    d2: int
    c1: int
    c2: int
    stat_name: str
    stat_value: int
    action_score: int
    result: str
    move: str
    match: bool = False

# BRAIN RESULT

@dataclass
class BrainResult:
    """Structured output from call_brain. Replaces the raw dict."""
    type: str = "action"
    move: str = "dialog"
    stat: str = "none"
    approach: str = ""
    target_npc: str | None = None
    dialog_only: bool = False
    player_intent: str = ""
    world_addition: str | None = None
    position: str = "risky"
    effect: str = "standard"
    dramatic_question: str = ""
    location_change: str | None = None
    time_progression: str = "none"

    @classmethod
    def from_dict(cls, data: dict) -> BrainResult:
        return _fields_from_dict(cls, data)
