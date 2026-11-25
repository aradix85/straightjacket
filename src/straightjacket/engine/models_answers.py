from __future__ import annotations

from dataclasses import dataclass

from straightjacket.engine.models_story import PossibleEnding
from straightjacket.engine.serialization import SerializableMixin


@dataclass
class FactRequest(SerializableMixin):
    fact_type: str
    about: str


@dataclass
class LocationChange(SerializableMixin):
    name: str
    kind: str


@dataclass(kw_only=True)
class BrainResult(SerializableMixin):
    move: str
    stat: str
    approach: str
    target_npc: str | None
    dialog_only: bool
    player_intent: str
    world_addition: str | None
    location_change: LocationChange | None
    track_name: str | None
    track_rank: str | None
    target_track: str | None
    target_clock: str | None
    target_threat: str | None
    bonus_id: str | None
    undetermined_facts: list[FactRequest]
    boasts: list[str]


@dataclass
class NewNpc(SerializableMixin):
    name: str
    description: str
    disposition: str


@dataclass
class NpcRename(SerializableMixin):
    npc_id: str
    new_name: str


@dataclass
class NpcDetail(SerializableMixin):
    npc_id: str
    full_name: str | None
    description: str | None


@dataclass
class DeceasedNpc(SerializableMixin):
    npc_id: str


@dataclass
class LoreNpc(SerializableMixin):
    name: str
    description: str


@dataclass
class NarratorMetadata(SerializableMixin):
    new_npcs: list[NewNpc]
    npc_renames: list[NpcRename]
    npc_details: list[NpcDetail]
    deceased_npcs: list[DeceasedNpc]
    lore_npcs: list[LoreNpc]


@dataclass
class OpeningNpc(SerializableMixin):
    name: str
    description: str
    agenda: str
    instinct: str
    secrets: list[str]
    disposition: str


@dataclass
class OpeningMemory(SerializableMixin):
    npc_name: str
    event: str
    emotional_weight: str


@dataclass
class OpeningSetup(SerializableMixin):
    npcs: list[OpeningNpc]
    location: str
    scene_context: str
    memory_updates: list[OpeningMemory]
    deceased_npcs: list[DeceasedNpc]


@dataclass
class NpcGuidance(SerializableMixin):
    npc_id: str
    guidance: str


@dataclass
class NpcReflection(SerializableMixin):
    reflection: str
    tone: str
    tone_key: str
    updated_description: str
    about_npc: str
    agenda: str
    instinct: str
    updated_agenda: str
    updated_arc: str


@dataclass
class DirectorAnswer(SerializableMixin):
    scene_summary: str
    narrator_guidance: str
    npc_guidance: list[NpcGuidance]
    npc_reflections: dict[str, NpcReflection]
    arc_notes: str


@dataclass
class VoicedAct(SerializableMixin):
    title: str
    goal: str
    mood: str
    transition_trigger: str


@dataclass
class VoicedRevelation(SerializableMixin):
    content: str


@dataclass
class BlueprintVoicing(SerializableMixin):
    central_conflict: str
    antagonist_force: str
    thematic_thread: str
    acts: list[VoicedAct]
    revelations: list[VoicedRevelation]
    possible_endings: list[PossibleEnding]


@dataclass
class NpcEdit(SerializableMixin):
    name: str | None
    description: str | None
    disposition: str | None
    agenda: str | None
    instinct: str | None
    aliases: list[str] | None
    status: str | None


@dataclass
class CorrectionOp(SerializableMixin):
    op: str
    npc_id: str | None
    split_name: str | None
    split_description: str | None
    merge_source_id: str | None
    fields: NpcEdit | None
    value: str | None


@dataclass
class CorrectionAnalysis(SerializableMixin):
    correction_source: str
    corrected_input: str
    narrator_guidance: str
    director_useful: bool
    state_ops: list[CorrectionOp]
