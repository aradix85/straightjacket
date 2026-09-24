from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ProgressTrack, ThreatData


LEGACY_TRACKS: tuple[str, ...] = ("quests", "bonds", "discoveries")


def get_legacy_track(game: GameState, name: str) -> ProgressTrack:
    if name == "quests":
        return game.campaign.legacy_quests
    if name == "bonds":
        return game.campaign.legacy_bonds
    if name == "discoveries":
        return game.campaign.legacy_discoveries
    raise ValueError(f"Unknown legacy track: {name!r}. Valid: {LEGACY_TRACKS}")


def shifted_rank(rank: str, shift: int) -> str | None:
    ranks = list(eng().legacy.ticks_by_rank)
    index = ranks.index(rank) + shift
    return ranks[index] if 0 <= index < len(ranks) else None


def mark_legacy(game: GameState, track_name: str, source_rank: str = "dangerous") -> int:
    return mark_legacy_ticks(game, track_name, eng().legacy.ticks_by_rank[source_rank])


def mark_legacy_ticks(game: GameState, track_name: str, ticks: int) -> int:
    track = get_legacy_track(game, track_name)
    cfg = eng().legacy
    xp_gained = 0
    for _ in range(ticks):
        boxes_before = track.filled_boxes
        track.ticks += 1
        if track.filled_boxes > boxes_before:
            xp_gained += cfg.xp_per_box if track.completions == 0 else cfg.xp_per_box_after_clear
        if track.ticks >= track.max_ticks:
            track.ticks = 0
            track.completions += 1
            log(f"[Legacy] {track_name} filled and cleared (completion {track.completions})")
    if xp_gained > 0:
        game.campaign.xp += xp_gained
    log(
        f"[Legacy] {track_name} +{ticks} ticks ({track.filled_boxes} boxes, completions {track.completions}), "
        f"+{xp_gained} XP (total {game.campaign.xp})"
    )
    return xp_gained


def apply_threat_overcome_bonus(game: GameState, threat: ThreatData) -> int:
    cfg = eng().legacy
    ratio = threat.menace_ticks / threat.max_menace_ticks if threat.max_menace_ticks else 0.0
    if ratio < cfg.threat_overcome_threshold:
        return 0
    game.campaign.xp += cfg.threat_overcome_bonus
    log(
        f"[Legacy] Threat '{threat.name}' overcome at menace {ratio:.0%} "
        f"→ +{cfg.threat_overcome_bonus} XP (total {game.campaign.xp})"
    )
    return cfg.threat_overcome_bonus


def advance_asset(game: GameState, asset_id: str, kind: str = "upgrade") -> int:
    cfg = eng().legacy
    cost = cfg.asset_upgrade_cost if kind == "upgrade" else cfg.new_asset_cost
    if game.campaign.xp_available < cost:
        log(f"[Legacy] advance_asset failed: need {cost} XP, have {game.campaign.xp_available}")
        return 0
    if kind == "new" and asset_id not in game.assets:
        game.assets.append(asset_id)
    game.campaign.xp_spent += cost
    log(f"[Legacy] {kind} '{asset_id}' for {cost} XP (available {game.campaign.xp_available})")
    return cost
