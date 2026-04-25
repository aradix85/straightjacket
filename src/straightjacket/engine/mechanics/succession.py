"""Character succession mechanics (Continue a Legacy).

When the predecessor's character ends — through face_death MISS, double-zero
crisis, or manual /retire — succession seeds a new character from a fraction
of the predecessor's legacy progress and a curated carry-over of NPCs and
their connection tracks.

This module owns three concerns: archiving the predecessor (build_predecessor_record),
rolling against each legacy track (run_inheritance_rolls), and reseeding NPCs
plus their connection tracks for the new character (apply_npc_carryover).

Orchestration — clearing the per-character mechanical state, accepting new
creation_data, threading through the WebSocket — lives in game/succession.py.
"""

from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import (
    GameState,
    InheritanceRollResult,
    NpcData,
    PredecessorRecord,
    ProgressTrack,
)
from .consequences import roll_progress
from .legacy import LEGACY_TRACKS, get_legacy_track


def build_predecessor_record(game: GameState, end_reason: str) -> PredecessorRecord:
    """Capture predecessor identity + pre-roll legacy state at succession time.

    Called before run_inheritance_rolls so the record reflects the boxes the
    rolls roll *against*. inheritance_rolls is filled in afterwards.
    """
    return PredecessorRecord(
        player_name=game.player_name,
        pronouns=game.pronouns,
        character_concept=game.character_concept,
        background_vow=game.background_vow,
        setting_id=game.setting_id,
        chapters_played=game.campaign.chapter_number,
        scenes_played=game.narrative.scene_count,
        end_reason=end_reason,
        legacy_quests_filled_boxes=game.campaign.legacy_quests.filled_boxes,
        legacy_bonds_filled_boxes=game.campaign.legacy_bonds.filled_boxes,
        legacy_discoveries_filled_boxes=game.campaign.legacy_discoveries.filled_boxes,
        inheritance_rolls=[],
    )


def _fraction_for_result(result: str) -> float:
    """Map roll result to the configured carry-over fraction."""
    inh = eng().succession.inheritance
    if result == "STRONG_HIT":
        return inh.strong_hit_fraction
    if result == "WEAK_HIT":
        return inh.weak_hit_fraction
    if result == "MISS":
        return inh.miss_fraction
    raise ValueError(f"Unknown roll result for inheritance: {result!r}")


def run_inheritance_rolls(game: GameState) -> list[InheritanceRollResult]:
    """Roll against each legacy track and return the per-track outcome.

    The roll uses progress dice (2d10 vs filled_boxes) on the predecessor's
    track. The new character's track will be seeded with
    round(predecessor_filled_boxes * fraction) filled boxes by the caller —
    this function does not mutate the predecessor's tracks.
    """
    move_name = eng().succession.inheritance.move_name
    rolls: list[InheritanceRollResult] = []
    for name in LEGACY_TRACKS:
        track = get_legacy_track(game, name)
        boxes = track.filled_boxes
        roll = roll_progress(track_name=track.name, filled_boxes=boxes, move=move_name)
        fraction = _fraction_for_result(roll.result)
        new_boxes = round(boxes * fraction)
        rolls.append(
            InheritanceRollResult(
                track_name=name,
                predecessor_filled_boxes=boxes,
                result=roll.result,
                fraction=fraction,
                new_filled_boxes=new_boxes,
            )
        )
        log(
            f"[Succession] Inheritance roll {name}: {boxes} boxes vs 2d10 "
            f"({roll.c1}, {roll.c2}) → {roll.result}, fraction={fraction}, new={new_boxes} boxes"
        )
    return rolls


def seed_successor_legacy(game: GameState, rolls: list[InheritanceRollResult]) -> None:
    """Apply inheritance rolls onto the campaign's legacy tracks in-place.

    Each track's filled_boxes is set to the roll's new_filled_boxes, expressed
    in ticks via ProgressTrack.ticks_for_filled_boxes (which clamps at
    max_ticks). Status returns to active. XP carries through CampaignState
    unchanged — XP is a campaign-wide accumulator, not a per-character resource.
    """
    by_name = {r.track_name: r for r in rolls}
    for name in LEGACY_TRACKS:
        track = get_legacy_track(game, name)
        roll = by_name[name]
        track.ticks = track.ticks_for_filled_boxes(roll.new_filled_boxes)
        track.status = "active"
    log(
        f"[Succession] Successor legacy seeded: "
        f"quests={game.campaign.legacy_quests.filled_boxes}/10 boxes, "
        f"bonds={game.campaign.legacy_bonds.filled_boxes}/10 boxes, "
        f"discoveries={game.campaign.legacy_discoveries.filled_boxes}/10 boxes"
    )


def apply_npc_carryover(
    npcs: list[NpcData], connection_tracks: list[ProgressTrack]
) -> tuple[list[NpcData], list[ProgressTrack]]:
    """Filter NPCs and rescale their connection tracks per succession.yaml.

    Returns (kept_npcs, kept_tracks). NPCs whose status maps to keep=False
    are pruned entirely (and their connection tracks dropped). NPCs that
    survive carry over with track.ticks scaled by the configured fraction;
    rank, max_ticks, name, id are preserved so existing narrative references
    stay intact. Status, memory, secrets, agenda, instinct on the NpcData
    itself are NOT modified — those are the predecessor's history with that
    person and remain part of who the NPC is.
    """
    rules = eng().succession.npc_carryover
    kept_npcs: list[NpcData] = []
    kept_track_ids: set[str] = set()

    for npc in npcs:
        if npc.status not in rules:
            raise ValueError(
                f"NPC {npc.id} has status {npc.status!r} with no succession.npc_carryover rule. "
                f"Update engine/succession.yaml or NPC status."
            )
        rule = rules[npc.status]
        if not rule.keep:
            log(f"[Succession] Pruning {npc.status} NPC: {npc.name} ({npc.id})")
            continue
        kept_npcs.append(npc)
        kept_track_ids.add(f"connection_{npc.id}")

    kept_tracks: list[ProgressTrack] = []
    npc_status_by_track: dict[str, str] = {f"connection_{n.id}": n.status for n in npcs}
    for track in connection_tracks:
        if track.id not in kept_track_ids:
            continue
        status = npc_status_by_track[track.id]
        fraction = rules[status].track_fraction
        new_filled = round(track.filled_boxes * fraction)
        new_track = ProgressTrack(
            id=track.id,
            name=track.name,
            track_type=track.track_type,
            rank=track.rank,
            max_ticks=track.max_ticks,
            ticks=0,
            status="active",
        )
        new_track.ticks = new_track.ticks_for_filled_boxes(new_filled)
        kept_tracks.append(new_track)
        log(
            f"[Succession] NPC {track.name} ({track.id}): {track.filled_boxes} → "
            f"{new_filled} boxes (fraction {fraction}, status {status})"
        )

    return kept_npcs, kept_tracks
