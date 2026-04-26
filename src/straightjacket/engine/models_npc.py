from __future__ import annotations

from dataclasses import dataclass, field

from .serialization import SerializableMixin, serialize


NPC_STATUSES: frozenset[str] = frozenset({"active", "background", "deceased", "lore"})


@dataclass
class MemoryEntry(SerializableMixin):
    scene: int
    event: str
    emotional_weight: str
    importance: int
    type: str
    tone: str = ""
    tone_key: str = ""
    about_npc: str | None = None
    _score_debug: str = ""

    def to_dict(self) -> dict:
        d = serialize(self)
        if not d.get("_score_debug"):
            d.pop("_score_debug", None)
        return d


@dataclass
class NpcData(SerializableMixin):
    id: str
    name: str
    disposition: str
    status: str
    description: str = ""
    agenda: str = ""
    instinct: str = ""
    arc: str = ""
    secrets: list[str] = field(default_factory=list)
    memory: list[MemoryEntry] = field(default_factory=list)
    introduced: bool = False
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    importance_accumulator: int = 0
    last_reflection_scene: int = 0
    last_location: str = ""
    needs_reflection: bool = False
    gather_count: int = 0
