from __future__ import annotations

from ..models import ProgressTrack, ThreatData
from .config import rules


def ranks() -> list[str]:
    return list(rules().progress.ticks_per_mark)


def new_track(*, id: str, name: str, track_type: str, rank: str) -> ProgressTrack:
    return ProgressTrack(
        id=id,
        name=name,
        track_type=track_type,
        rank=rank,
        max_ticks=rules().progress.max_ticks,
        bound_impact="",
        vowed_to=None,
        ticks=0,
        status="active",
        completions=0,
    )


def _ticks_per_mark(rank: str) -> int:
    ticks: int = rules().progress.ticks_per_mark[rank]
    return ticks


def _boxes(ticks: int) -> int:
    return ticks // rules().progress.ticks_per_box


def ticks_per_mark(track: ProgressTrack) -> int:
    return _ticks_per_mark(track.rank)


def filled_boxes(track: ProgressTrack) -> int:
    return _boxes(track.ticks)


def ticks_for_filled_boxes(track: ProgressTrack, boxes: int) -> int:
    return min(track.max_ticks, boxes * rules().progress.ticks_per_box)


def mark_progress(track: ProgressTrack) -> int:
    old = track.ticks
    track.ticks = min(track.max_ticks, track.ticks + ticks_per_mark(track))
    return track.ticks - old


def menace_per_mark(threat: ThreatData) -> int:
    return _ticks_per_mark(threat.rank)


def menace_boxes(threat: ThreatData) -> int:
    return _boxes(threat.menace_ticks)


def menace_total_boxes(threat: ThreatData) -> int:
    return _boxes(threat.max_menace_ticks)


def advance_menace(threat: ThreatData, marks: int) -> int:
    old = threat.menace_ticks
    threat.menace_ticks = min(threat.max_menace_ticks, threat.menace_ticks + menace_per_mark(threat) * marks)
    return threat.menace_ticks - old
