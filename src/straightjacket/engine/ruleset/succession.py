from __future__ import annotations

from ..logging_util import log
from ..models import GameState, InheritanceRollResult, NpcData, PredecessorRecord, ProgressTrack
from .bond import connection_track_id
from .config import rules
from .legacy import LEGACY_TRACKS, get_legacy_track
from .progress import filled_boxes, ticks_for_filled_boxes
from .rolls import roll_progress


def build_predecessor_record(game: GameState, end_reason: str) -> PredecessorRecord:
    return PredecessorRecord(
        player_name=game.player_name,
        pronouns=game.pronouns,
        character_concept=game.character_concept,
        background_vow=game.background_vow,
        setting_id=game.setting_id,
        chapters_played=game.campaign.chapter_number,
        scenes_played=game.narrative.scene_count,
        end_reason=end_reason,
        legacy_quests_filled_boxes=filled_boxes(game.campaign.legacy_quests),
        legacy_bonds_filled_boxes=filled_boxes(game.campaign.legacy_bonds),
        legacy_discoveries_filled_boxes=filled_boxes(game.campaign.legacy_discoveries),
        inheritance_rolls=[],
    )


def run_inheritance_rolls(game: GameState) -> list[InheritanceRollResult]:
    move_name = rules().succession.inheritance.move_name
    rolls: list[InheritanceRollResult] = []
    for name in LEGACY_TRACKS:
        track = get_legacy_track(game, name)
        boxes = filled_boxes(track)
        roll = roll_progress(track_name=track.name, filled_boxes=boxes, move=move_name)
        fraction = rules().succession.inheritance.fraction_by_result[roll.result]
        new_boxes = round(boxes * fraction)
        rolls.append(InheritanceRollResult(track_name=name, result=roll.result, new_filled_boxes=new_boxes))
        log(
            f"[Succession] Inheritance roll {name}: {boxes} boxes vs 2d10 "
            f"({roll.c1}, {roll.c2}) → {roll.result}, fraction={fraction}, new={new_boxes} boxes"
        )
    return rolls


def seed_successor_legacy(game: GameState, rolls: list[InheritanceRollResult]) -> None:
    by_name = {r.track_name: r for r in rolls}
    for name in LEGACY_TRACKS:
        track = get_legacy_track(game, name)
        roll = by_name[name]
        track.ticks = ticks_for_filled_boxes(track, roll.new_filled_boxes)
        track.status = "active"
    seeded = ", ".join(f"{name}={filled_boxes(get_legacy_track(game, name))}" for name in LEGACY_TRACKS)
    log(f"[Succession] Successor legacy seeded (boxes of {rules().progress.boxes}): {seeded}")


def apply_npc_carryover(
    npcs: list[NpcData], connection_tracks: list[ProgressTrack]
) -> tuple[list[NpcData], list[ProgressTrack]]:
    carryover = rules().succession.npc_carryover
    kept_npcs: list[NpcData] = []
    kept_track_ids: set[str] = set()

    for npc in npcs:
        if npc.status not in carryover:
            raise ValueError(
                f"NPC {npc.id} has status {npc.status!r} with no succession.npc_carryover rule. "
                f"Update ruleset/succession.yaml or NPC status."
            )
        rule = carryover[npc.status]
        if not rule.keep:
            log(f"[Succession] Pruning {npc.status} NPC: {npc.name} ({npc.id})")
            continue
        kept_npcs.append(npc)
        kept_track_ids.add(connection_track_id(npc.id))

    kept_tracks: list[ProgressTrack] = []
    npc_status_by_track: dict[str, str] = {connection_track_id(n.id): n.status for n in npcs}
    for track in connection_tracks:
        if track.id not in kept_track_ids:
            continue
        status = npc_status_by_track[track.id]
        fraction = carryover[status].track_fraction
        new_filled = round(filled_boxes(track) * fraction)
        new_track = ProgressTrack(
            id=track.id,
            name=track.name,
            track_type=track.track_type,
            rank=track.rank,
            max_ticks=track.max_ticks,
            bound_impact=track.bound_impact,
            ticks=0,
            status="active",
        )
        new_track.ticks = ticks_for_filled_boxes(new_track, new_filled)
        kept_tracks.append(new_track)
        log(
            f"[Succession] NPC {track.name} ({track.id}): {filled_boxes(track)} → "
            f"{new_filled} boxes (fraction {fraction}, status {status})"
        )

    return kept_npcs, kept_tracks
