#!/usr/bin/env python3
"""NPC model types: MemoryEntry, NpcData."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models_base import _fields_from_dict, _fields_to_dict


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
        if not d.get("_score_debug"):
            d.pop("_score_debug", None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return _fields_from_dict(cls, data)


@dataclass
class NpcData:
    """Single NPC. All fields explicit with defaults."""

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
