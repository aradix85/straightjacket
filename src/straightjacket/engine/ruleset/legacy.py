from __future__ import annotations

from typing import Any

from ...i18n import t
from ..logging_util import log
from ..models import CampaignState, GameState, ProgressTrack, ThreatData
from .assets import asset_data, enable_next_ability, enabled_abilities
from .config import rules
from .progress import filled_boxes

LEGACY_TRACKS: tuple[str, ...] = ("quests", "bonds", "discoveries")


def _legacy_track(track_id: str, name_key: str) -> ProgressTrack:
    return ProgressTrack(
        id=track_id,
        name=t(name_key),
        track_type="legacy",
        rank=rules().legacy.starting_rank,
        max_ticks=rules().progress.max_ticks,
        bound_impact="",
    )


def new_campaign() -> CampaignState:
    return CampaignState(
        legacy_quests=_legacy_track("legacy_quests", "status.legacy_name_quests"),
        legacy_bonds=_legacy_track("legacy_bonds", "status.legacy_name_bonds"),
        legacy_discoveries=_legacy_track("legacy_discoveries", "status.legacy_name_discoveries"),
    )


def get_legacy_track(game: GameState, name: str) -> ProgressTrack:
    if name == "quests":
        return game.campaign.legacy_quests
    if name == "bonds":
        return game.campaign.legacy_bonds
    if name == "discoveries":
        return game.campaign.legacy_discoveries
    raise ValueError(f"Unknown legacy track: {name!r}. Valid: {LEGACY_TRACKS}")


def shifted_rank(rank: str, shift: int) -> str | None:
    ranks = list(rules().legacy.ticks_by_rank)
    index = ranks.index(rank) + shift
    return ranks[index] if 0 <= index < len(ranks) else None


def mark_legacy(game: GameState, track_name: str, source_rank: str) -> None:
    mark_legacy_ticks(game, track_name, rules().legacy.ticks_by_rank[source_rank])


def mark_legacy_ticks(game: GameState, track_name: str, ticks: int) -> None:
    track = get_legacy_track(game, track_name)
    cfg = rules().legacy
    xp_gained = 0
    for _ in range(ticks):
        boxes_before = filled_boxes(track)
        track.ticks += 1
        if filled_boxes(track) > boxes_before:
            xp_gained += cfg.xp_per_box if track.completions == 0 else cfg.xp_per_box_after_clear
        if track.ticks >= track.max_ticks:
            track.ticks = 0
            track.completions += 1
            log(f"[Legacy] {track_name} filled and cleared (completion {track.completions})")
    if xp_gained > 0:
        game.campaign.xp += xp_gained
    log(
        f"[Legacy] {track_name} +{ticks} ticks ({filled_boxes(track)} boxes, completions {track.completions}), "
        f"+{xp_gained} XP (total {game.campaign.xp})"
    )


def apply_threat_overcome_bonus(game: GameState, threat: ThreatData) -> None:
    cfg = rules().legacy
    ratio = threat.menace_ticks / threat.max_menace_ticks
    if ratio < cfg.threat_overcome_threshold:
        return
    game.campaign.xp += cfg.threat_overcome_bonus
    log(
        f"[Legacy] Threat '{threat.name}' overcome at menace {ratio:.0%} "
        f"→ +{cfg.threat_overcome_bonus} XP (total {game.campaign.xp})"
    )


def advance_cost(kind: str) -> int:
    cfg = rules().legacy
    if kind == "upgrade":
        return cfg.asset_upgrade_cost
    if kind == "new":
        return cfg.new_asset_cost
    raise ValueError(f"Unknown advance: {kind!r}. Valid: 'upgrade', 'new'")


def _held_id(game: GameState, data: dict[str, Any]) -> str | None:
    for held in (*game.paths, *game.assets):
        held_data = asset_data(game, held)
        if held_data is None:
            raise ValueError(f"Held asset {held!r} is not in setting {game.setting_id!r}")
        if held_data["_id"] == data["_id"]:
            return held
    return None


def advance_asset(game: GameState, asset_id: str, kind: str) -> str | None:
    cost = advance_cost(kind)
    data = asset_data(game, asset_id)
    if data is None:
        return "unknown"
    held_id = _held_id(game, data)
    if kind == "new":
        if held_id is not None:
            return "held"
    elif held_id is None:
        return "not_held"
    elif all(enabled_abilities(game, held_id)):
        return "fully_upgraded"
    if game.campaign.xp_available < cost:
        return "insufficient"
    if held_id is None:
        game.assets.append(asset_id)
    else:
        enable_next_ability(game, held_id)
    game.campaign.xp_spent += cost
    log(f"[Legacy] {kind} '{asset_id}' for {cost} XP (available {game.campaign.xp_available})")
    return None
