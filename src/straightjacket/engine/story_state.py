from __future__ import annotations

from .engine_loader import eng
from .gamemaster.config import gm
from .gamemaster.keyed_scenes import has_keyed_scene_from
from .logging_util import log
from .models import CurrentAct, GameState, Revelation


def get_current_act(game: GameState) -> CurrentAct:
    bp = game.narrative.story_blueprint
    if bp is None:
        raise ValueError("get_current_act needs a story blueprint")

    if bp.story_complete and game.campaign.epilogue_dismissed:
        last = bp.acts[-1]
        defaults = eng().ai_text.narrator_defaults
        return CurrentAct(
            phase="aftermath",
            title=defaults["aftermath_act_title"],
            goal=defaults["aftermath_act_goal"],
            scene_range=list(last.scene_range),
            mood=last.mood,
            transition_trigger="",
            act_number=len(bp.acts),
            total_acts=len(bp.acts),
            progress="late",
            approaching_end=False,
        )

    acts = bp.acts
    scene = game.narrative.scene_count
    triggered = set(bp.triggered_transitions)

    current = acts[0]
    act_number = 1

    for i, act in enumerate(acts[:-1]):
        if f"act_{i}" in triggered or scene > act.scene_range[1]:
            current = acts[i + 1]
            act_number = i + 2
        else:
            current = act
            act_number = i + 1
            break

    sr = current.scene_range
    act_len = max(sr[1] - sr[0] + 1, 1)
    scenes_in = scene - sr[0] + 1
    cfg = gm().story_state
    if scenes_in <= act_len * cfg.act_early_share:
        progress = "early"
    elif scenes_in <= act_len * cfg.act_mid_share:
        progress = "mid"
    else:
        progress = "late"

    approaching_end = act_number == len(acts) and progress in cfg.approaching_end_progress

    return CurrentAct(
        phase=current.phase,
        title=current.title,
        goal=current.goal,
        scene_range=list(current.scene_range),
        mood=current.mood,
        transition_trigger=current.transition_trigger,
        act_number=act_number,
        total_acts=len(acts),
        progress=progress,
        approaching_end=approaching_end,
    )


def check_act_transition(game: GameState) -> None:
    bp = game.narrative.story_blueprint
    if bp is None:
        return
    act = get_current_act(game)
    if act.act_number >= len(bp.acts):
        return
    act_idx = act.act_number - 1
    act_id = f"act_{act_idx}"
    if game.narrative.scene_count < act.scene_range[1] or act_id in bp.triggered_transitions:
        return
    for i in range(act_idx):
        fill_id = f"act_{i}"
        if fill_id not in bp.triggered_transitions:
            bp.triggered_transitions.append(fill_id)
            log(f"[Story] Back-filled skipped act transition: {fill_id}")
    bp.triggered_transitions.append(act_id)
    log(
        f"[Story] Act transition: act {act.act_number} '{act.phase}' ends at scene "
        f"{game.narrative.scene_count}: '{act.transition_trigger[: eng().truncations.log_medium]}'"
    )


def _revelation_ready(game: GameState, act: CurrentAct, revelation: Revelation) -> bool:
    if act.act_number != revelation.act_number:
        return act.act_number > revelation.act_number
    if revelation.keyed_scene_source and not has_keyed_scene_from(game.narrative, revelation.keyed_scene_source):
        return True
    return game.narrative.scene_count >= act.scene_range[1]


def land_revelation(game: GameState, outcome: str) -> Revelation | None:
    bp = game.narrative.story_blueprint
    if bp is None or outcome not in gm().story_state.revelation_outcomes:
        return None
    act = get_current_act(game)
    for revelation in bp.revelations:
        if revelation.id not in bp.revealed and _revelation_ready(game, act, revelation):
            bp.revealed.append(revelation.id)
            log(
                f"[Story] Revelation '{revelation.id}' of act {revelation.act_number} lands in scene "
                f"{game.narrative.scene_count}"
            )
            return revelation
    return None


def check_story_completion(game: GameState) -> None:
    bp = game.narrative.story_blueprint
    if bp is None or bp.story_complete:
        return
    acts = bp.acts
    final_end = acts[-1].scene_range[1]
    sc = game.narrative.scene_count

    triggered = set(bp.triggered_transitions)
    penultimate_id = f"act_{len(acts) - 2}"
    final_act_entered = len(acts) >= 2 and penultimate_id in triggered

    if final_act_entered and sc >= final_end:
        bp.story_complete = True
        log(f"[Story] Complete: final act entered ('{penultimate_id}' triggered) + scene {sc} >= range end {final_end}")
        return

    if sc >= final_end and not final_act_entered:
        for i, act in enumerate(acts[:-1]):
            act_id = f"act_{i}"
            if act_id not in bp.triggered_transitions and sc > act.scene_range[1]:
                bp.triggered_transitions.append(act_id)
                log(f"[Story] Back-filled transition: {act_id} (scene {sc} > range end {act.scene_range[1]})")
        triggered = set(bp.triggered_transitions)
        if len(acts) >= 2 and penultimate_id in triggered:
            bp.story_complete = True
            log(
                f"[Story] Complete (back-fill): '{penultimate_id}' triggered after "
                f"scene-range back-fill, scene {sc} >= {final_end}"
            )
            return

    offset = gm().story_state.completion_overrun_scenes
    if sc >= final_end + offset:
        bp.story_complete = True
        log(f"[Story] Complete (fallback): scene {sc} >= final_end+{offset} ({final_end + offset})")
