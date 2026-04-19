"""Shared test helpers.

Production dataclasses (GameState, NpcData, ClockData, ProgressTrack, ThreatData,
MemoryEntry, FateResult) have most structural fields required — there is no
universal default for domain enums. Tests that don't care about those values
use these helpers; tests that DO care pass their own kwargs, which override
the helper defaults via setdefault.

The helpers exist in the test layer only. Production code still constructs
these dataclasses with all fields explicit.
"""

from __future__ import annotations

from typing import Any


def make_game_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import GameState

    kwargs.setdefault("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    return GameState(**kwargs)


def make_npc(**kwargs: Any) -> Any:
    from straightjacket.engine.models import NpcData

    kwargs.setdefault("disposition", "neutral")
    kwargs.setdefault("status", "active")
    return NpcData(**kwargs)


def make_clock(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ClockData

    kwargs.setdefault("clock_type", "threat")
    kwargs.setdefault("segments", 6)
    return ClockData(**kwargs)


def make_progress_track(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ProgressTrack

    kwargs.setdefault("id", "track_test")
    kwargs.setdefault("name", "Test Track")
    kwargs.setdefault("track_type", "vow")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_ticks", 40)
    return ProgressTrack(**kwargs)


def make_threat(**kwargs: Any) -> Any:
    from straightjacket.engine.models import ThreatData

    kwargs.setdefault("id", "threat_test")
    kwargs.setdefault("name", "Test Threat")
    kwargs.setdefault("category", "scheming_leader")
    kwargs.setdefault("linked_vow_id", "")
    kwargs.setdefault("rank", "dangerous")
    kwargs.setdefault("max_menace_ticks", 40)
    return ThreatData(**kwargs)


def make_memory(**kwargs: Any) -> Any:
    from straightjacket.engine.models import MemoryEntry

    kwargs.setdefault("scene", 1)
    kwargs.setdefault("event", "")
    kwargs.setdefault("emotional_weight", "neutral")
    kwargs.setdefault("importance", 3)
    kwargs.setdefault("type", "observation")
    return MemoryEntry(**kwargs)


def make_fate_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import FateResult

    kwargs.setdefault("answer", "yes")
    kwargs.setdefault("odds", "fifty_fifty")
    kwargs.setdefault("chaos_factor", 5)
    kwargs.setdefault("method", "fate_chart")
    kwargs.setdefault("roll", 50)
    return FateResult(**kwargs)


def make_random_event(**kwargs: Any) -> Any:
    from straightjacket.engine.models import RandomEvent

    kwargs.setdefault("focus", "npc_action")
    kwargs.setdefault("focus_roll", 50)
    kwargs.setdefault("meaning_action", "Act")
    kwargs.setdefault("meaning_subject", "Thing")
    kwargs.setdefault("meaning_table", "actions")
    kwargs.setdefault("source", "fate_doublet")
    return RandomEvent(**kwargs)


def make_brain_result(**kwargs: Any) -> Any:
    from straightjacket.engine.models import BrainResult

    kwargs.setdefault("type", "action")
    kwargs.setdefault("move", "dialog")
    kwargs.setdefault("stat", "none")
    return BrainResult(**kwargs)


def make_world_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import WorldState

    kwargs.setdefault("chaos_factor", 5)
    return WorldState(**kwargs)
