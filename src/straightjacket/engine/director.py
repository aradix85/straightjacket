import json
from typing import Any

from .ai.provider_base import AICallSpec, AIProvider, create_with_retry
from .ai.schemas import get_director_output_schema
from .config_loader import model_for_role, narration_language, sampling_params
from .engine_loader import eng
from .gamemaster.config import gm
from .gamemaster.npc.matching import resolve_about_npc
from .gamemaster.npc.memory import consolidate_memory, recent_observations
from .gamemaster.questions import outcome_of
from .logging_util import log
from .models import DirectorGuidance, GameState, MemoryEntry, NpcData
from .prompt_blocks import character_tag, content_boundaries_block, world_tag
from .prompt_loader import get_prompt
from .ruleset.bond import get_npc_bond
from .story_state import get_current_act
from .tools import execute_tool_call, get_tools
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def _director_system(game: GameState) -> str:
    cb = content_boundaries_block(game)
    base = f"{get_prompt('director_system')}\n{world_tag(game)}\n{character_tag(game)}"
    return f"{base}\n{cb}" if cb else base


def should_call_director(
    game: GameState,
    roll_result: str,
    chaos_used: bool,
    new_npcs_found: bool,
    revelation_used: bool,
) -> str | None:
    if game.campaign.epilogue_dismissed and not game.post_epilogue_director_done:
        game.post_epilogue_director_done = True
        return "post_epilogue_aftermath"

    if outcome_of(roll_result) == "failure":
        return "miss"
    if chaos_used:
        return "chaos"
    if new_npcs_found:
        return "new_npcs"
    if revelation_used:
        return "revelation"

    for npc in game.npcs:
        if npc.needs_reflection and npc.status in gm().npc_status_groups.in_play:
            return f"reflection:{npc.name}"

    bp = game.narrative.story_blueprint
    if bp is not None:
        act = get_current_act(game)
        if act.phase in gm().pacing.director_phases and act.phase not in bp.triggered_director_phases:
            bp.triggered_director_phases.append(act.phase)
            return f"phase:{act.phase}"

    if game.narrative.scene_count % gm().pacing.director_interval == 0:
        return "interval"

    return None


def _needs_profile(npc: NpcData) -> bool:
    return not npc.agenda.strip() or not npc.instinct.strip()


def _reflection_eligible(npc: NpcData) -> bool:
    return (npc.needs_reflection or _needs_profile(npc)) and npc.status in gm().npc_status_groups.in_play


def _build_reflection_block(game: GameState, npc: NpcData) -> str:
    mem_text = "; ".join(f"{m.event}({m.emotional_weight})" for m in recent_observations(npc))

    last_reflection_attrs = ""
    reflections = [m for m in npc.memory if m.type == "reflection"]
    if reflections:
        last = reflections[-1]
        last_reflection_attrs = f' last_reflection="{_xa(last.event[: eng().truncations.prompt_short])}"'
        if last.tone:
            last_reflection_attrs += f' last_tone="{_xa(last.tone)}"'
        last_reflection_attrs += f' last_tone_key="{_xa(last.tone_key)}"'

    instinct_attr = f' instinct="{_xa(npc.instinct)}"' if npc.instinct.strip() else ""
    arc_attr = f' arc="{_xa(npc.arc)}"' if npc.arc.strip() else ""
    needs_profile_attr = ' needs_profile="true"' if _needs_profile(npc) else ""

    return (
        f'<reflect npc_id="{_xa(npc.id)}" name="{_xa(npc.name)}" '
        f'disposition="{_xa(npc.disposition)}" bond="{get_npc_bond(game, npc.id)}" '
        f'description="{_xa(npc.description)}"{instinct_attr}{arc_attr}{last_reflection_attrs}{needs_profile_attr}>'
        f"{_xe(mem_text)}</reflect>"
    )


def _build_story_arc_block(game: GameState) -> str:
    bp = game.narrative.story_blueprint
    if bp is None:
        return ""

    act = get_current_act(game)
    scene_range = act.scene_range
    past_range_attr = ' PAST_RANGE="true"' if game.narrative.scene_count > scene_range[1] else ""

    info = (
        f'\n<story_arc structure="{_xa(bp.structure_type)}" '
        f'act="{act.act_number}/{act.total_acts}" phase="{_xa(act.phase)}" '
        f'progress="{act.progress}" '
        f'current_scene="{game.narrative.scene_count}" scene_range="{scene_range[0]}-{scene_range[1]}"'
        f"{past_range_attr} "
        f'conflict="{_xa(bp.central_conflict)}" antagonist="{_xa(bp.antagonist_force)}"'
    )
    if bp.thematic_thread:
        info += f' thematic_thread="{_xa(bp.thematic_thread)}"'
    info += "/>"
    if act.transition_trigger:
        info += f'\n<transition_trigger act="{act.act_number}">{_xe(act.transition_trigger)}</transition_trigger>'
    return info


def build_director_prompt(game: GameState, latest_narration: str) -> str:
    reflection_section = "\n".join(_build_reflection_block(game, npc) for npc in game.npcs if _reflection_eligible(npc))
    task = get_prompt("director_task", lang=narration_language())
    notes = game.narrative.director_guidance.arc_notes
    notes_block = f"\n<arc_notes>{_xe(notes)}</arc_notes>" if notes else ""
    return f"""{task}

<latest_scene>
{latest_narration[: eng().truncations.prompt_xlong]}
</latest_scene>
{_build_story_arc_block(game)}{notes_block}
{reflection_section}"""


def _no_guidance(error: Exception) -> dict[str, Any]:
    log(f"[Director] Failed ({type(error).__name__}: {error}), continuing without guidance", level="warning")
    return {}


def call_director(provider: AIProvider, game: GameState, latest_narration: str) -> dict[str, Any]:
    log(f"[Director] Analyzing scene {game.narrative.scene_count}")

    prompt = build_director_prompt(game, latest_narration)
    system = _director_system(game)
    params = sampling_params("director")
    model = model_for_role("director")

    tool_spec = AICallSpec(
        model=model,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        tools=get_tools(),
        log_role="director",
        **{**params, "max_retries": 1},
    )
    try:
        tool_response = create_with_retry(provider, tool_spec)
    except Exception as e:
        return _no_guidance(e)

    if tool_response.stop_reason == "tool_use" and tool_response.tool_calls:
        results = [execute_tool_call(call.name, call.arguments, game) for call in tool_response.tool_calls]
        prompt += f"\n<tool_results>\n{chr(10).join(results)[: eng().truncations.prompt_xxlong]}\n</tool_results>"
        log(f"[Director] Phase 1: {len(results)} tool calls")
    else:
        log("[Director] Phase 1: no tools called")

    answer_spec = AICallSpec(
        model=model,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_director_output_schema([npc.id for npc in game.npcs if _reflection_eligible(npc)]),
        log_role="director",
        **params,
    )
    try:
        answer = create_with_retry(provider, answer_spec)
        try:
            guidance: dict[str, Any] = json.loads(answer.content)
        except json.JSONDecodeError as e:
            usage = answer.usage or {}
            reasoning_tail = " ".join(answer.reasoning[-eng().truncations.log_xlong :].split())
            raise ValueError(
                f"{e}; the answer stopped as {answer.stop_reason} after {usage.get('output_tokens')} output tokens, "
                f"{usage.get('reasoning_tokens')} of them reasoning, with {len(answer.content)} characters of JSON, "
                f"which began: {answer.content[: eng().truncations.log_xlong]!r}, "
                f"and {len(answer.reasoning)} of reasoning text, which ended: {reasoning_tail!r}"
            ) from e
    except Exception as e:
        return _no_guidance(e)

    guidance["npc_guidance"] = {
        item["npc_id"]: item["guidance"] for item in guidance["npc_guidance"] if item["npc_id"] and item["guidance"]
    }
    log(
        f"[Director] Guidance: "
        f"reflections={len(guidance['npc_reflections'])}, "
        f"summary={guidance['scene_summary'][: eng().truncations.log_medium]}"
    )
    return guidance


def _apply_profile_updates(npc: NpcData, ref: dict[str, Any]) -> None:
    _trunc = eng().truncations
    agenda = ref["agenda"].strip()
    instinct = ref["instinct"].strip()
    if agenda and not npc.agenda.strip():
        npc.agenda = agenda
        log(f"[Director] Agenda set for {npc.name}: '{agenda}'")
    if instinct and not npc.instinct.strip():
        npc.instinct = instinct
        log(f"[Director] Instinct set for {npc.name}: '{instinct}'")

    updated_agenda = ref["updated_agenda"].strip()
    if updated_agenda and npc.agenda.strip():
        log(
            f"[Director] Agenda updated for {npc.name}: "
            f"'{npc.agenda[: _trunc.log_xshort]}' → '{updated_agenda[: _trunc.log_xshort]}'"
        )
        npc.agenda = updated_agenda
    updated_arc = ref["updated_arc"].strip()
    if updated_arc:
        log(
            f"[Director] Arc updated for {npc.name}: '{npc.arc[: _trunc.log_short]}' → '{updated_arc[: _trunc.log_short]}'"
        )
        npc.arc = updated_arc
    updated_description = ref["updated_description"].strip()
    if updated_description:
        log(
            f"[Director] Description updated for {npc.name}: "
            f"'{npc.description[: _trunc.log_short]}' → '{updated_description[: _trunc.log_short]}'"
        )
        npc.description = updated_description


def _apply_reflection(game: GameState, npc: NpcData, ref: dict[str, Any]) -> None:
    npc.memory.append(
        MemoryEntry(
            scene=game.narrative.scene_count,
            event=ref["reflection"],
            emotional_weight=ref["tone_key"],
            tone=ref["tone"],
            tone_key=ref["tone_key"],
            importance=gm().npc.reflection_importance,
            type="reflection",
            about_npc=resolve_about_npc(game, ref["about_npc"], owner_id=npc.id),
        )
    )
    npc.needs_reflection = False
    npc.importance_accumulator = 0
    npc.last_reflection_scene = game.narrative.scene_count
    _apply_profile_updates(npc, ref)
    consolidate_memory(npc)
    log(f"[Director] Reflection for {npc.name}: {ref['reflection'][: eng().truncations.log_medium]}")


def _clear_reflection_flags(game: GameState, reason: str) -> None:
    for npc in game.npcs:
        if npc.needs_reflection:
            npc.needs_reflection = False
            log(
                f"[Director] Reset reflection flag for {npc.name} "
                f"({reason}, accumulator preserved at {npc.importance_accumulator})"
            )


def new_guidance() -> DirectorGuidance:
    return DirectorGuidance(narrator_guidance="", arc_notes="")


def apply_director_guidance(game: GameState, guidance: dict[str, Any]) -> None:
    if not guidance:
        _clear_reflection_flags(game, "no guidance")
        return

    game.narrative.director_guidance = DirectorGuidance(
        narrator_guidance=guidance["narrator_guidance"],
        npc_guidance=guidance["npc_guidance"],
        arc_notes=guidance["arc_notes"],
    )
    if guidance["scene_summary"]:
        game.narrative.session_log[-1].rich_summary = guidance["scene_summary"]

    selected = {npc.id: npc for npc in game.npcs if _reflection_eligible(npc)}
    for npc_id, ref in guidance["npc_reflections"].items():
        if npc_id not in selected:
            log(f"[Director] Rejected reflection for {npc_id!r}: not selected for reflection", level="warning")
        elif ref["reflection"]:
            _apply_reflection(game, selected[npc_id], ref)

    _clear_reflection_flags(game, "not reflected")
    log("[Director] Guidance applied")


def reset_stale_reflection_flags(game: GameState) -> None:
    for npc in game.npcs:
        if npc.needs_reflection and npc.status in gm().npc_status_groups.in_play:
            npc.needs_reflection = False
            log(f"[Director] Reset stale reflection flag for {npc.name} (skipped turn, accumulator preserved)")
