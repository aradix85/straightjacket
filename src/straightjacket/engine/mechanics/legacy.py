#!/usr/bin/env python3
"""Legacy tracks and XP mechanics.

Three campaign-persistent legacy tracks (quests, bonds, discoveries) accumulate
progress from move outcomes. Filled boxes grant XP. XP is spent on asset
abilities or new assets.

Rank convention: legacy tracks are "epic" (1 tick per mark). The effective
tick amount per mark is adjusted by the rank of the originating vow/bond:
a completed troublesome vow marks less legacy progress than an epic one.
"""

from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ProgressTrack, ThreatData


LEGACY_TRACKS: tuple[str, ...] = ("quests", "bonds", "discoveries")


def get_legacy_track(game: GameState, name: str) -> ProgressTrack:
    """Return the legacy track for the given name (quests/bonds/discoveries)."""
    if name == "quests":
        return game.campaign.legacy_quests
    if name == "bonds":
        return game.campaign.legacy_bonds
    if name == "discoveries":
        return game.campaign.legacy_discoveries
    raise ValueError(f"Unknown legacy track: {name!r}. Valid: {LEGACY_TRACKS}")


def mark_legacy(game: GameState, track_name: str, source_rank: str = "dangerous") -> int:
    """Mark progress on a legacy track based on source rank. Awards XP for filled boxes.

    Source rank determines tick amount: troublesome=1 tick, dangerous=2, formidable=4,
    extreme=8, epic=12. This is inverted from normal progress ranks — legacy tracks
    record the *difficulty* of what was accomplished, so harder accomplishments fill
    faster.

    Returns XP granted from newly filled boxes.
    """
    track = get_legacy_track(game, track_name)
    ticks_by_rank = {
        "troublesome": 1,
        "dangerous": 2,
        "formidable": 4,
        "extreme": 8,
        "epic": 12,
    }
    ticks = ticks_by_rank.get(source_rank, 2)

    old_boxes = track.filled_boxes
    track.ticks = min(track.max_ticks, track.ticks + ticks)
    new_boxes = track.filled_boxes
    boxes_gained = new_boxes - old_boxes

    xp_gained = boxes_gained * eng().legacy.xp_per_box
    if xp_gained > 0:
        game.campaign.xp += xp_gained
        log(
            f"[Legacy] {track_name} +{ticks} ticks ({old_boxes}→{new_boxes} boxes), "
            f"+{xp_gained} XP (total {game.campaign.xp})"
        )
    else:
        log(f"[Legacy] {track_name} +{ticks} ticks (no box crossed)")
    return xp_gained


def apply_threat_overcome_bonus(game: GameState, threat: ThreatData) -> int:
    """Grant bonus XP when a vow completes with an overcome threat at high menace.

    Called from complete_track after the threat is marked overcome. Returns XP granted.
    """
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
    """Spend XP on an asset upgrade or new asset. Returns XP spent, or 0 on failure.

    kind: "upgrade" (existing asset ability) or "new" (acquire new asset).
    """
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
