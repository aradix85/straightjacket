from __future__ import annotations

from dataclasses import dataclass, field

from .serialization import SerializableMixin


@dataclass
class MemoryEntry(SerializableMixin):
    scene: int
    event: str
    emotional_weight: str
    importance: int
    type: str
    tone: str
    tone_key: str
    about_npc: str | None


@dataclass(kw_only=True)
class NpcData(SerializableMixin):
    id: str
    name: str
    disposition: str
    status: str
    name_rolled: bool
    description: str
    agenda: str
    instinct: str
    arc: str
    secrets: list[str] = field(default_factory=list)
    memory: list[MemoryEntry] = field(default_factory=list)
    introduced: bool
    aliases: list[str] = field(default_factory=list)
    importance_accumulator: int
    last_reflection_scene: int
    last_location: str
    needs_reflection: bool
    gather_count: int
