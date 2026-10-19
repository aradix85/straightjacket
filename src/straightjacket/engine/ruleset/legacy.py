from __future__ import annotations

from typing import Any

from ...i18n import t
from ..logging_util import log
from ..models import CampaignState, GameState, ProgressTrack, ThreatData
from ..setting.packages import load_package
from .assets import asset_data, enable_next_ability, enabled_abilities
from .config import rules
from .progress import filled_boxes, ranks


def _legacy_tracks(setting_id: str) -> dict[str, dict[str, Any]]:
    tracks: dict[str, dict[str, Any]] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        for raw in (pkg.data.raw["rules"].get("special_tracks") or {}).values():
            if not raw["optional"] and raw["label"] not in tracks:
                tracks[raw["label"]] = raw
    return tracks


def _earns_experience(setting_id: str, track_name: str) -> bool:
    tags: dict[str, dict[str, Any]] = _legacy_tracks(setting_id)[track_name].get("tags", {})
    return any(package_tags.get(rules().legacy.experience_tag) is True for package_tags in tags.values())


def _legacy_track(name: str) -> ProgressTrack:
    return ProgressTrack(
        id=f"legacy_{name}",
        name=t(f"status.legacy_name_{name}"),
        track_type="legacy",
        rank=rules().legacy.starting_rank,
        max_ticks=rules().progress.max_ticks,
        bound_impact="",
    )


def new_campaign(setting_id: str) -> CampaignState:
    return CampaignState(legacy={name: _legacy_track(name) for name in _legacy_tracks(setting_id)})


def shifted_rank(rank: str, shift: int) -> str | None:
    ordered = ranks()
    index = ordered.index(rank) + shift
    return ordered[index] if 0 <= index < len(ordered) else None


def mark_legacy(game: GameState, track_name: str, source_rank: str) -> None:
    mark_legacy_ticks(game, track_name, rules().legacy.ticks_by_rank[source_rank])


def mark_legacy_ticks(game: GameState, track_name: str, ticks: int) -> None:
    track = game.campaign.legacy[track_name]
    cfg = rules().legacy
    earns = _earns_experience(game.setting_id, track_name)
    xp_gained = 0
    for _ in range(ticks):
        boxes_before = filled_boxes(track)
        track.ticks += 1
        if earns and filled_boxes(track) > boxes_before:
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
