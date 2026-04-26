from __future__ import annotations

from dataclasses import dataclass, field

from ..logging_util import log
from .loader import Setting, load_setting
from .settings import datasworn_id_of, parent_of


@dataclass
class RollOption:
    using: str = ""
    stat: str = ""
    condition_meter: str = ""
    control: str = ""
    assets: list[str] = field(default_factory=list)
    value: int | None = None
    label: str = ""


@dataclass
class TriggerCondition:
    method: str = ""
    roll_options: list[RollOption] = field(default_factory=list)
    text: str = ""


@dataclass
class MoveOutcome:
    text: str = ""


@dataclass
class Move:
    id: str = ""
    key: str = ""
    name: str = ""
    category: str = ""
    roll_type: str = ""
    text: str = ""

    trigger_text: str = ""
    conditions: list[TriggerCondition] = field(default_factory=list)

    outcomes: dict[str, MoveOutcome] = field(default_factory=dict)

    track_category: str = ""
    oracle_ids: list[str] = field(default_factory=list)
    replaces: list[str] = field(default_factory=list)
    allow_momentum_burn: bool | None = None

    @property
    def valid_stats(self) -> list[str]:
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
        if self.conditions:
            return self.conditions[0].method
        return ""


def _parse_roll_option(raw: dict) -> RollOption:
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
    roll_options = [_parse_roll_option(ro) for ro in raw.get("roll_options", [])]
    return TriggerCondition(
        method=raw.get("method", ""),
        roll_options=roll_options,
        text=raw.get("text", ""),
    )


def _parse_outcomes(raw: dict | None) -> dict[str, MoveOutcome]:
    if not raw:
        return {}
    result: dict[str, MoveOutcome] = {}
    for key in ("strong_hit", "weak_hit", "miss"):
        entry = raw.get(key)
        if entry and isinstance(entry, dict):
            result[key] = MoveOutcome(text=entry.get("text", ""))
    return result


def _parse_oracle_ids(raw: list | dict | None) -> list[str]:
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
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, str)]
    if isinstance(raw, str):
        return [raw]
    return []


def _parse_move(raw: dict, category: str) -> Move:
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


def _load_moves_from_setting(setting: Setting) -> dict[str, Move]:
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
    setting_ds = load_setting(datasworn_id_of(setting_id))

    if parent_id:
        parent_ds = load_setting(datasworn_id_of(parent_id))
        moves = _load_moves_from_setting(parent_ds)
        expansion_moves = _load_moves_from_setting(setting_ds)
        for key, move in expansion_moves.items():
            moves[key] = move
        log(
            f"[Moves] Loaded {setting_id} ({len(expansion_moves)} moves) "
            f"on {parent_id} ({len(moves) - len(expansion_moves)} base) = {len(moves)} total"
        )
    else:
        moves = _load_moves_from_setting(setting_ds)
        log(f"[Moves] Loaded {setting_id}: {len(moves)} moves")

    return moves


_cache: dict[str, dict[str, Move]] = {}


def get_moves(setting_id: str) -> dict[str, Move]:
    if setting_id in _cache:
        return _cache[setting_id]

    parent = parent_of(setting_id)
    moves = load_moves(setting_id, parent_id=parent)
    _cache[setting_id] = moves
    return moves


def clear_cache() -> None:
    _cache.clear()
