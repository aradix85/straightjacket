from __future__ import annotations

from ..models import ProgressTrack, ThreatData
from .config import rules


def ranks() -> list[str]:
    return list(rules().progress.ticks_per_mark)


def new_track(*, id: str, name: str, track_type: str, rank: str) -> ProgressTrack:
    return ProgressTrack(
        id=id, name=name, track_type=track_type, rank=rank, max_ticks=rules().progress.max_ticks, bound_impact=""
    )


def ticks_per_mark(track: ProgressTrack) -> int:
    ticks: int = rules().progress.ticks_per_mark[track.rank]
    return ticks


def filled_boxes(track: ProgressTrack) -> int:
    return track.ticks // rules().progress.ticks_per_box


def ticks_for_filled_boxes(track: ProgressTrack, boxes: int) -> int:
    return min(track.max_ticks, boxes * rules().progress.ticks_per_box)


def mark_progress(track: ProgressTrack) -> int:
    old = track.ticks
    track.ticks = min(track.max_ticks, track.ticks + ticks_per_mark(track))
    return track.ticks - old


def new_threat(
    *,
    id: str,
    name: str,
    category: str,
    linked_vow_id: str | None,
    rank: str,
    description: str,
    creation_source: str,
) -> ThreatData:
    return ThreatData(
        id=id,
        name=name,
        category=category,
        linked_vow_id=linked_vow_id,
        rank=rank,
        max_menace_ticks=rules().progress.max_ticks,
        description=description,
        creation_source=creation_source,
    )


def menace_per_mark(threat: ThreatData) -> int:
    ticks: int = rules().progress.ticks_per_mark[threat.rank]
    return ticks


def menace_boxes(threat: ThreatData) -> int:
    return threat.menace_ticks // rules().progress.ticks_per_box


def menace_total_boxes(threat: ThreatData) -> int:
    return threat.max_menace_ticks // rules().progress.ticks_per_box


def advance_menace(threat: ThreatData, marks: int) -> int:
    old = threat.menace_ticks
    threat.menace_ticks = min(threat.max_menace_ticks, threat.menace_ticks + menace_per_mark(threat) * marks)
    return threat.menace_ticks - old
