#!/usr/bin/env python3
"""NPC model types: MemoryEntry, NpcData."""

from __future__ import annotations

from dataclasses import dataclass, field

from .serialization import SerializableMixin, serialize

# Canonical NPC status values. Used by correction ops and anywhere status is validated.
NPC_STATUSES: frozenset[str] = frozenset({"active", "background", "deceased", "lore"})


@dataclass
class MemoryEntry(SerializableMixin):
    """Single NPC memory (observation or reflection).

    scene/event/emotional_weight/importance/type are required — a memory without
    these is meaningless. tone and tone_key are legit optional: not every memory
    is scored for narrative tone; empty strings mean "not scored".
    """

    scene: int
    event: str
    emotional_weight: str  # emotion keyword from emotions/importance.yaml
    importance: int  # 1-5, scored by score_importance or set by reflection
    type: str  # observation, reflection
    tone: str = ""  # narrative compound (e.g. "protective_guilt"); "" = not scored
    tone_key: str = ""  # machine-readable enum word; "" = not scored
    about_npc: str | None = None
    _score_debug: str = ""  # Debug info from score_importance

    def to_dict(self) -> dict:
        d = serialize(self)
        if not d.get("_score_debug"):
            d.pop("_score_debug", None)
        return d


@dataclass
class NpcData(SerializableMixin):
    """Single NPC. Structural identity fields required; runtime-state fields default sensibly.

    `introduced` defaults to False: a freshly constructed NPC hasn't been shown
    on-screen yet. Sites that construct NPCs from visible narration set
    introduced=True explicitly.
    """

    id: str
    name: str
    disposition: str  # one of engine.disposition values
    status: str  # one of NPC_STATUSES
    description: str = ""
    agenda: str = ""
    instinct: str = ""
    arc: str = ""  # Narrative trajectory — set by Director, evolves each reflection
    secrets: list[str] = field(default_factory=list)
    memory: list[MemoryEntry] = field(default_factory=list)
    introduced: bool = False
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    importance_accumulator: int = 0
    last_reflection_scene: int = 0
    last_location: str = ""
    needs_reflection: bool = False
    gather_count: int = 0  # Successful gather_information moves targeting this NPC
