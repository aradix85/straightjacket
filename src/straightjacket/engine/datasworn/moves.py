#!/usr/bin/env python3
"""Datasworn move loader.

Parses Datasworn JSON move definitions into typed dataclasses.
Supports all four Ironsworn-family settings and handles expansion
overrides (Delve→Classic, Sundered Isles→Starforged).

Usage:
    from straightjacket.engine.datasworn.moves import load_moves

    moves = load_moves("starforged")
    fd = moves["face_danger"]
    fd.roll_type        # "action_roll"
    fd.valid_stats      # ["edge", "heart", "iron", "shadow", "wits"]
    fd.category         # "adventure"
    fd.outcomes         # {"strong_hit": MoveOutcome(...), ...}

    # Expansion merge:
    moves = load_moves("sundered_isles", parent_id="starforged")
    # SI overrides applied on top of Starforged base
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..logging_util import log
from .loader import Setting, load_setting


# ── Roll option: one way a move can be rolled ─────────────────


@dataclass
class RollOption:
    """Single roll option within a trigger condition.

    using: what to roll with — "stat", "condition_meter", "asset_control",
           "custom", "progress_track", or a legacy track name.
    stat: stat name when using="stat" (edge, heart, iron, shadow, wits).
    condition_meter: meter name when using="condition_meter" (health, spirit, supply).
    control: asset control name when using="asset_control" (health, integrity, supply).
    assets: asset glob patterns when using="asset_control".
    value: fixed numeric value when using="custom".
    label: display label when using="custom".
    """

    using: str = ""
    stat: str = ""
    condition_meter: str = ""
    control: str = ""
    assets: list[str] = field(default_factory=list)
    value: int | None = None
    label: str = ""


# ── Trigger condition: one way to activate a move ─────────────


@dataclass
class TriggerCondition:
    """One trigger condition (a move can have multiple).

    method: how to select the roll value — "player_choice", "highest",
            "lowest", "progress_roll", "all".
    roll_options: the values available for this condition.
    text: flavor text describing when this condition applies.
    """

    method: str = ""
    roll_options: list[RollOption] = field(default_factory=list)
    text: str = ""


# ── Move outcome: what happens on a given result ─────────────


@dataclass
class MoveOutcome:
    """Outcome text for one result tier (strong_hit, weak_hit, miss)."""

    text: str = ""


# ── Move: complete move definition ───────────────────────────


@dataclass
class Move:
    """Datasworn move definition.

    Pure data — no game logic. The engine reads these to determine
    valid stats, roll type, and associated oracles/tracks.
    """

    id: str = ""
    key: str = ""  # short name: "face_danger", "endure_harm"
    name: str = ""  # display name: "Face Danger", "Endure Harm"
    category: str = ""  # parent category: "adventure", "combat", "suffer"
    roll_type: str = ""  # "action_roll", "progress_roll", "no_roll", "special_track"
    text: str = ""  # full move text (markdown)

    trigger_text: str = ""
    conditions: list[TriggerCondition] = field(default_factory=list)

    outcomes: dict[str, MoveOutcome] = field(default_factory=dict)

    # Track category for progress moves (e.g. "Vow", "Connection", "Combat")
    track_category: str = ""

    # Oracle references (Datasworn IDs or inline tables)
    oracle_ids: list[str] = field(default_factory=list)

    # Expansion: what this move replaces (Datasworn IDs)
    replaces: list[str] = field(default_factory=list)

    # Whether momentum burn is allowed (SI overrides set this explicitly)
    allow_momentum_burn: bool | None = None

    @property
    def valid_stats(self) -> list[str]:
        """Extract stat names from trigger conditions. For Brain classification."""
        stats: list[str] = []
        seen: set[str] = set()
        for cond in self.conditions:
            for ro in cond.roll_options:
                if ro.using == "stat" and ro.stat and ro.stat not in seen:
                    stats.append(ro.stat)
                    seen.add(ro.stat)
        return stats

    @property
    def valid_condition_meters(self) -> list[str]:
        """Extract condition meter names from trigger conditions."""
        meters: list[str] = []
        seen: set[str] = set()
        for cond in self.conditions:
            for ro in cond.roll_options:
                if ro.using == "condition_meter" and ro.condition_meter and ro.condition_meter not in seen:
                    meters.append(ro.condition_meter)
                    seen.add(ro.condition_meter)
        return meters

    @property
    def trigger_method(self) -> str:
        """Primary trigger method. Empty if no conditions."""
        if self.conditions:
            return self.conditions[0].method
        return ""


# ── Parsing ──────────────────────────────────────────────────


def _parse_roll_option(raw: dict) -> RollOption:
    """Parse a single roll_option dict from Datasworn JSON."""
    assets_raw = raw.get("assets")
    return RollOption(
        using=raw.get("using", ""),
        stat=raw.get("stat", ""),
        condition_meter=raw.get("condition_meter", ""),
        control=raw.get("control", ""),
        assets=assets_raw if isinstance(assets_raw, list) else [],
        value=raw.get("value"),
        label=raw.get("label", ""),
    )


def _parse_condition(raw: dict) -> TriggerCondition:
    """Parse a single trigger condition dict."""
    roll_options = [_parse_roll_option(ro) for ro in raw.get("roll_options", [])]
    return TriggerCondition(
        method=raw.get("method", ""),
        roll_options=roll_options,
        text=raw.get("text", ""),
    )


def _parse_outcomes(raw: dict | None) -> dict[str, MoveOutcome]:
    """Parse outcomes dict. Returns empty dict for no-roll moves."""
    if not raw:
        return {}
    result: dict[str, MoveOutcome] = {}
    for key in ("strong_hit", "weak_hit", "miss"):
        entry = raw.get(key)
        if entry and isinstance(entry, dict):
            result[key] = MoveOutcome(text=entry.get("text", ""))
    return result


def _parse_oracle_ids(raw: list | dict | None) -> list[str]:
    """Extract oracle IDs from the oracles field.

    Two formats:
      Starforged/Classic/Delve: list of string IDs
      Sundered Isles: dict of inline oracle tables (extract the _id)
    """
    if isinstance(raw, list):
        return [o for o in raw if isinstance(o, str)]
    if isinstance(raw, dict):
        ids = []
        for table in raw.values():
            if isinstance(table, dict) and "_id" in table:
                ids.append(table["_id"])
        return ids
    return []


def _parse_replaces(raw: list | str | None) -> list[str]:
    """Normalize replaces field to list of strings."""
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, str)]
    if isinstance(raw, str):
        return [raw]
    return []


def _parse_move(raw: dict, category: str) -> Move:
    """Parse a single move dict from Datasworn JSON."""
    trigger = raw.get("trigger", {})
    conditions_raw = trigger.get("conditions") or []

    tracks = raw.get("tracks", {})
    allow_burn = raw.get("allow_momentum_burn")

    return Move(
        id=raw.get("_id", ""),
        key=raw.get("_id", "").rsplit("/", 1)[-1],
        name=raw.get("name", ""),
        category=category,
        roll_type=raw.get("roll_type", ""),
        text=raw.get("text", ""),
        trigger_text=trigger.get("text", ""),
        conditions=[_parse_condition(c) for c in conditions_raw],
        outcomes=_parse_outcomes(raw.get("outcomes")),
        track_category=tracks.get("category", ""),
        oracle_ids=_parse_oracle_ids(raw.get("oracles")),
        replaces=_parse_replaces(raw.get("replaces")),
        allow_momentum_burn=allow_burn if allow_burn is not None else None,
    )


# ── Loading ──────────────────────────────────────────────────


def _load_moves_from_setting(setting: Setting) -> dict[str, Move]:
    """Load all moves from a Datasworn Setting, keyed by category/move_key.

    Using category/key avoids collisions (Starforged has both
    adventure/face_danger and scene_challenge/face_danger).
    """
    raw_moves = setting.raw.get("moves", {})
    result: dict[str, Move] = {}
    for cat_key, cat_data in raw_moves.items():
        contents = cat_data.get("contents", {})
        for move_key, move_data in contents.items():
            move = _parse_move(move_data, cat_key)
            full_key = f"{cat_key}/{move_key}"
            result[full_key] = move
    return result


def load_moves(setting_id: str, parent_id: str | None = None) -> dict[str, Move]:
    """Load moves for a setting, with optional parent merge.

    For standalone settings (Classic, Starforged): loads directly.
    For expansions (Delve, Sundered Isles): loads parent first,
    then applies expansion overrides on top.

    Returns dict keyed by "category/move_key" (e.g. "adventure/face_danger").
    """
    if parent_id:
        parent_setting = load_setting(parent_id)
        moves = _load_moves_from_setting(parent_setting)
        expansion_setting = load_setting(setting_id)
        expansion_moves = _load_moves_from_setting(expansion_setting)

        # Apply overrides: expansion moves replace parent moves with same key
        for key, move in expansion_moves.items():
            moves[key] = move

        log(
            f"[Moves] Loaded {setting_id} ({len(expansion_moves)} moves) "
            f"on {parent_id} ({len(moves) - len(expansion_moves)} base) = {len(moves)} total"
        )
    else:
        setting = load_setting(setting_id)
        moves = _load_moves_from_setting(setting)
        log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")

    return moves


# ── Cache ────────────────────────────────────────────────────

# Parent mapping: which setting is the base for each expansion.
_PARENT_MAP: dict[str, str] = {
    "delve": "classic",
    "sundered_isles": "starforged",
}

_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    """Get moves for a setting. Cached after first load.

    Automatically resolves parent for expansions.
    """
    if setting_id in _cache:
        return _cache[setting_id]

    parent = _PARENT_MAP.get(setting_id)
    moves = load_moves(setting_id, parent_id=parent)
    _cache[setting_id] = moves
    return moves


def clear_cache() -> None:
    """Clear the moves cache."""
    _cache.clear()
