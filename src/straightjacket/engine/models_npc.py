#!/usr/bin/env python3
"""NPC model types: MemoryEntry, NpcData."""

from __future__ import annotations

from dataclasses import dataclass, field

from .serialization import deserialize, serialize


@dataclass
class MemoryEntry:
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

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return deserialize(cls, data)


@dataclass
class NpcData:
    """Single NPC. All fields explicit with defaults."""

    id: str = ""
    name: str = ""
    description: str = ""
    agenda: str = ""
    instinct: str = ""
    arc: str = ""  # Narrative trajectory — set by Director, evolves each reflection
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
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> NpcData:
        return deserialize(cls, data)
