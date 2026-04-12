#!/usr/bin/env python3
"""NPC model types: MemoryEntry, NpcData."""

from __future__ import annotations

from dataclasses import dataclass, field

from .serialization import SerializableMixin, serialize

# Canonical NPC status values. Used by correction ops and anywhere status is validated.
NPC_STATUSES: frozenset[str] = frozenset({"active", "background", "deceased", "lore"})


@dataclass
class MemoryEntry(SerializableMixin):
    """Single NPC memory (observation or reflection). All fields explicit."""

    scene: int = 0
    event: str = ""
    emotional_weight: str = "neutral"
    importance: int = 3
    type: str = "observation"  # observation, reflection
    about_npc: str | None = None
    tone: str = ""  # Narrative compound (e.g. "protective_guilt")
    tone_key: str = ""  # Machine-readable enum word
    _score_debug: str = ""  # Debug info from score_importance

    def to_dict(self) -> dict:
        d = serialize(self)
        if not d.get("_score_debug"):
            d.pop("_score_debug", None)
        return d


@dataclass
class NpcData(SerializableMixin):
    """Single NPC. All fields explicit with defaults."""

    id: str = ""
    name: str = ""
    description: str = ""
    agenda: str = ""
    instinct: str = ""
    arc: str = ""  # Narrative trajectory — set by Director, evolves each reflection
    secrets: list[str] = field(default_factory=list)
    disposition: str = "neutral"
    status: str = "active"
    memory: list[MemoryEntry] = field(default_factory=list)
    introduced: bool = True
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    importance_accumulator: int = 0
    last_reflection_scene: int = 0
    last_location: str = ""
    needs_reflection: bool = False
    gather_count: int = 0  # Successful gather_information moves targeting this NPC
