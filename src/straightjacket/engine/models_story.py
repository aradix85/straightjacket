"""Story model types: threads, character lists, scene log, narration, story blueprint,
director guidance, narrative state, campaign state."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..i18n import t
from .engine_loader import eng
from .models_base import ClockEvent, ProgressTrack, ThreatData
from .serialization import SerializableMixin


@dataclass
class ThreadEntry(SerializableMixin):
    """Active thread in the Mythic threads list."""

    id: str
    name: str
    thread_type: str  # vow, goal, tension, subplot
    source: str  # creation, vow, director, event
    weight: int = 1
    linked_track_id: str = ""  # ProgressTrack id if this thread is a vow
    active: bool = True


@dataclass
class CharacterListEntry(SerializableMixin):
    """Entry in the Mythic characters list."""

    id: str
    name: str
    entry_type: str  # npc, entity, abstract
    weight: int = 1
    active: bool = True


@dataclass
class SceneLogEntry(SerializableMixin):
    """One entry in the session log. Created per turn/correction.

    npc_activation, validator, and revelation_check are intentionally untyped dicts.
    They carry ephemeral diagnostic data (debug scores, validation reports) that
    varies per turn and is never read back by game logic — only logged and displayed.
    Typing them would add dataclasses with no consumers.
    """

    scene: int = 0
    scene_type: str = field(kw_only=True)  # expected, altered, interrupt
    summary: str = ""
    move: str = ""
    result: str = ""
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str = "risky"
    effect: str = "standard"
    npc_activation: dict = field(default_factory=dict)  # diagnostic: {npc_name: {score, reasons, status}}
    validator: dict = field(default_factory=dict)  # diagnostic: {passed, retries, violations, checks}
    rich_summary: str = ""
    director_trigger: str = ""
    oracle_answer: str = ""
    revelation_check: dict = field(default_factory=dict)  # diagnostic: {id, confirmed}


@dataclass
class NarrationEntry(SerializableMixin):
    """One entry in narration history. Used for narrator conversation context."""

    scene: int
    prompt_summary: str
    narration: str


@dataclass
class StoryAct(SerializableMixin):
    """Single act in a story blueprint."""

    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""


@dataclass
class CurrentAct:
    """Computed act info from get_current_act(). Not serialized."""

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
class Revelation(SerializableMixin):
    """Story revelation with timing and weight."""

    id: str = ""
    content: str = ""
    earliest_scene: int = 999
    dramatic_weight: str = "medium"


@dataclass
class PossibleEnding(SerializableMixin):
    """Possible story ending."""

    type: str = ""
    description: str = ""


@dataclass
class StoryBlueprint(SerializableMixin):
    """Story architect output. Tracks act structure, revelations, and completion."""

    central_conflict: str = ""
    antagonist_force: str = ""
    thematic_thread: str = ""
    structure_type: str = "3act"
    acts: list[StoryAct] = field(default_factory=list)
    revelations: list[Revelation] = field(default_factory=list)
    possible_endings: list[PossibleEnding] = field(default_factory=list)
    revealed: list[str] = field(default_factory=list)
    triggered_transitions: list[str] = field(default_factory=list)
    triggered_director_phases: list[str] = field(default_factory=list)
    story_complete: bool = False


@dataclass
class DirectorGuidance(SerializableMixin):
    """Director output stored between turns for narrator context."""

    narrator_guidance: str = ""
    npc_guidance: dict[str, str] = field(default_factory=dict)
    arc_notes: str = ""


@dataclass
class NarrativeState(SerializableMixin):
    """Scene tracking, history, story arc, director guidance."""

    scene_count: int = 0
    session_log: list[SceneLogEntry] = field(default_factory=list)
    narration_history: list[NarrationEntry] = field(default_factory=list)
    story_blueprint: StoryBlueprint | None = None
    director_guidance: DirectorGuidance = field(default_factory=DirectorGuidance)
    scene_intensity_history: list[str] = field(default_factory=list)
    threads: list[ThreadEntry] = field(default_factory=list)
    characters_list: list[CharacterListEntry] = field(default_factory=list)

    def snapshot(self) -> dict:
        """Lightweight snapshot for undo. Captures lengths (not full lists) and mutable sub-state."""
        return {
            "scene_count": self.scene_count,
            "session_log_len": len(self.session_log),
            "narration_history_len": len(self.narration_history),
            "threads_len": len(self.threads),
            "characters_list_len": len(self.characters_list),
            "director_guidance": self.director_guidance.to_dict(),
            "scene_intensity_history": list(self.scene_intensity_history),
            "story_blueprint_snapshot": {
                "revealed": list(self.story_blueprint.revealed),
                "triggered_transitions": list(self.story_blueprint.triggered_transitions),
                "triggered_director_phases": list(self.story_blueprint.triggered_director_phases),
                "story_complete": self.story_blueprint.story_complete,
            }
            if self.story_blueprint
            else None,
        }

    def restore(self, snap: dict) -> None:
        """Restore from a lightweight snapshot. Truncates lists to snapshotted lengths."""
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        self.session_log = self.session_log[: snap["session_log_len"]]
        self.narration_history = self.narration_history[: snap["narration_history_len"]]
        self.threads = self.threads[: snap["threads_len"]]
        self.characters_list = self.characters_list[: snap["characters_list_len"]]
        bp_snap = snap["story_blueprint_snapshot"]
        if bp_snap is not None and self.story_blueprint is not None:
            self.story_blueprint.revealed = list(bp_snap["revealed"])
            self.story_blueprint.triggered_transitions = list(bp_snap["triggered_transitions"])
            self.story_blueprint.triggered_director_phases = list(bp_snap["triggered_director_phases"])
            self.story_blueprint.story_complete = bp_snap["story_complete"]
        elif bp_snap is None:
            # Blueprint was absent at snapshot time — remove any blueprint added since
            self.story_blueprint = None


@dataclass
class NpcEvolution(SerializableMixin):
    """Projected NPC change from chapter summary."""

    name: str
    projection: str


@dataclass
class ChapterSummary(SerializableMixin):
    """Snapshot of a completed chapter for campaign continuity.

    Two kinds of fields. Narrative fields (title, summary, unresolved_threads,
    character_growth, npc_evolutions, thematic_question, post_story_location)
    are AI-written: interpretation of what the chapter meant. Mechanical fields
    (chapter, scenes, progress_tracks, threats, impacts, assets, threads) are
    engine-written: a hard snapshot of game state at chapter-end. The narrative
    is colour; the mechanical state is canon. Step 2 (chapter_validator) checks
    that the AI text does not contradict the snapshot.

    All fields required. The mechanical fields make chapter transitions auditable
    and allow the chapter-end state to be restored after _reset_chapter_mechanics
    instead of relying on which fields the reset happens not to touch.
    """

    chapter: int
    title: str
    summary: str
    unresolved_threads: list[str]
    character_growth: str
    npc_evolutions: list[NpcEvolution]
    thematic_question: str
    post_story_location: str
    scenes: int
    progress_tracks: list[ProgressTrack]
    threats: list[ThreatData]
    impacts: list[str]
    assets: list[str]
    threads: list[ThreadEntry]


def _legacy_quests_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_quests",
        name=t("status.legacy_name_quests"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


def _legacy_bonds_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_bonds",
        name=t("status.legacy_name_bonds"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


def _legacy_discoveries_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_discoveries",
        name=t("status.legacy_name_discoveries"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


@dataclass
class CampaignState(SerializableMixin):
    """Chapter progression, epilogue, campaign-persistent XP and legacy tracks."""

    campaign_history: list[ChapterSummary] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_shown: bool = False
    epilogue_dismissed: bool = False
    epilogue_text: str = ""

    # Campaign-persistent progression
    xp: int = 0  # Total XP earned across campaign
    xp_spent: int = 0  # Total XP spent on assets/upgrades
    legacy_quests: ProgressTrack = field(default_factory=_legacy_quests_factory)
    legacy_bonds: ProgressTrack = field(default_factory=_legacy_bonds_factory)
    legacy_discoveries: ProgressTrack = field(default_factory=_legacy_discoveries_factory)

    @property
    def xp_available(self) -> int:
        return self.xp - self.xp_spent

    def snapshot(self) -> dict:
        """Lightweight snapshot for turn undo. Captures fields that can change
        mid-turn. campaign_history, chapter_number, and epilogue_text are excluded
        because they only change at chapter boundaries (start_new_chapter), never
        during normal turn processing or correction. Legacy tracks and XP CAN
        change mid-turn via legacy_reward effects and threat bonuses."""
        return {
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
            "xp": self.xp,
            "xp_spent": self.xp_spent,
            "legacy_quests": self.legacy_quests.to_dict(),
            "legacy_bonds": self.legacy_bonds.to_dict(),
            "legacy_discoveries": self.legacy_discoveries.to_dict(),
        }

    def restore(self, snap: dict) -> None:
        self.epilogue_shown = snap["epilogue_shown"]
        self.epilogue_dismissed = snap["epilogue_dismissed"]
        self.xp = snap["xp"]
        self.xp_spent = snap["xp_spent"]
        self.legacy_quests = ProgressTrack.from_dict(snap["legacy_quests"])
        self.legacy_bonds = ProgressTrack.from_dict(snap["legacy_bonds"])
        self.legacy_discoveries = ProgressTrack.from_dict(snap["legacy_discoveries"])
