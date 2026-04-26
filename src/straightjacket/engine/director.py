"""Straightjacket Director agent: story steering, NPC reflections, pacing."""

import html
import json
import re

from .ai.provider_base import AIProvider, create_with_retry
from .ai.schemas import get_director_output_schema
from .config_loader import model_for_role, sampling_params
from .engine_loader import eng
from .logging_util import log
from .models import DirectorGuidance, EngineConfig, GameState, MemoryEntry, NpcData
from .prompt_blocks import content_boundaries_block
from .tools import get_tools, run_tool_loop
from .xml_utils import xa as _xa
from .npc import (
    consolidate_memory,
    find_npc,
    get_npc_bond,
    is_complete_description,
    resolve_about_npc,
)
from .prompt_blocks import get_narration_lang
from .prompt_loader import get_prompt
from .story_state import get_current_act, default_scene_range

# DIRECTOR AGENT — Lazy story steering, summaries, reflections


def _get_director_system_base() -> str:
    """Load director system prompt fresh from prompt_loader each time.
    prompt_loader caches internally; reload_prompts() clears that cache.
    No module-level cache here — avoids stale prompts after reload."""
    return get_prompt("director_system", role="director")


def _director_system(game: GameState) -> str:
    """Build Director system prompt with content_boundaries."""

    cb = content_boundaries_block(game)
    base = _get_director_system_base()
    return f"{base}\n{cb}" if cb else base


def should_call_director(
    game: GameState,
    roll_result: str = "",
    chaos_used: bool = False,
    new_npcs_found: bool = False,
    revelation_used: bool = False,
) -> str | None:
    """Decide whether to call the Director after this scene.
    Director runs lazily — not every turn, only when valuable.
    Returns a reason string if Director should run, None otherwise."""
    # 1. Post-epilogue aftermath: first scene after dismissal always triggers Director
    if game.campaign.epilogue_dismissed and not game.post_epilogue_director_done:
        game.post_epilogue_director_done = True
        return "post_epilogue_aftermath"

    # 2. Significant game events → always
    if roll_result == "MISS":
        return "miss"
    if chaos_used:
        return "chaos"
    if new_npcs_found:
        return "new_npcs"
    if revelation_used:
        return "revelation"

    # 2. Any NPC needs reflection
    for npc in game.npcs:
        if npc.needs_reflection and npc.status in ("active", "background"):
            return f"reflection:{npc.name}"

    # 3. Act phase change — fire at most once per phase per chapter
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        if (
            act.phase in ("climax", "resolution", "ten_twist", "ketsu_resolution")
            and act.phase not in bp.triggered_director_phases
        ):
            return f"phase:{act.phase}"

    # 4. Regular interval
    if game.narrative.scene_count > 0 and game.narrative.scene_count % eng().pacing.director_interval == 0:
        return "interval"

    return None


def _build_reflection_block(game: GameState, npc: NpcData) -> str:
    """Build one <reflect> XML block for an NPC that needs reflection or a profile completion."""
    recent_obs = [m for m in npc.memory if m.type == "observation"][-8:]
    mem_text = "; ".join(f"{m.event}({m.emotional_weight})" for m in recent_obs)

    # Include last reflection so Director can build on it, not repeat it
    prev_reflections = [m for m in npc.memory if m.type == "reflection"]
    prev_ref_text = ""
    prev_tone_text = ""
    if prev_reflections:
        prev_ref_text = (
            f' last_reflection="'
            f"{html.escape(prev_reflections[-1].event[: eng().truncations.prompt_short], quote=True)}"
            f'"'
        )
        prev_tone_compound = prev_reflections[-1].tone or prev_reflections[-1].emotional_weight
        prev_tone_key_val = prev_reflections[-1].tone_key
        if prev_tone_compound:
            prev_tone_text += f' last_tone="{html.escape(prev_tone_compound, quote=True)}"'
        if prev_tone_key_val:
            prev_tone_text += f' last_tone_key="{html.escape(prev_tone_key_val, quote=True)}"'

    npc_desc = html.escape(npc.description, quote=True)
    instinct_attr = f' instinct="{_xa(npc.instinct)}"' if npc.instinct.strip() else ""
    arc_attr = f' arc="{_xa(npc.arc)}"' if npc.arc.strip() else ""
    needs_profile_attr = ""
    if not npc.agenda.strip() or not npc.instinct.strip():
        needs_profile_attr = ' needs_profile="true"'

    return (
        f'<reflect npc_id="{html.escape(npc.id, quote=True)}" name="{html.escape(npc.name, quote=True)}" '
        f'disposition="{html.escape(npc.disposition, quote=True)}" bond="{get_npc_bond(game, npc.id)}" '
        f'description="{npc_desc}"{instinct_attr}{arc_attr}{prev_ref_text}{prev_tone_text}{needs_profile_attr}>'
        f"{html.escape(mem_text)}</reflect>"
    )


def _collect_reflection_blocks(game: GameState) -> str:
    """Gather <reflect> blocks for every NPC that needs reflection or profile completion."""
    blocks = []
    for npc in game.npcs:
        needs_profile = not npc.agenda.strip() or not npc.instinct.strip()
        if not npc.needs_reflection and not needs_profile:
            continue
        if npc.status not in ("active", "background"):
            continue
        blocks.append(_build_reflection_block(game, npc))
    return "\n".join(blocks)


def _build_story_arc_block(game: GameState) -> str:
    """Build <story_arc> and optional <transition_trigger> XML for the director prompt."""
    if not game.narrative.story_blueprint or not game.narrative.story_blueprint.acts:
        return ""

    act = get_current_act(game)
    bp = game.narrative.story_blueprint
    thematic = bp.thematic_thread
    scene_range = act.scene_range or default_scene_range()
    past_range = game.narrative.scene_count > scene_range[1]
    past_range_attr = ' PAST_RANGE="true"' if past_range else ""

    info = (
        f'\n<story_arc structure="{html.escape(bp.structure_type, quote=True)}" '
        f'act="{act.act_number}/{act.total_acts}" phase="{html.escape(act.phase, quote=True)}" '
        f'progress="{act.progress}" '
        f'current_scene="{game.narrative.scene_count}" scene_range="{scene_range[0]}-{scene_range[1]}"'
        f"{past_range_attr} "
        f'conflict="{html.escape(bp.central_conflict, quote=True)}"'
    )
    if thematic:
        info += f' thematic_thread="{html.escape(thematic, quote=True)}"'
    info += "/>"
    if act.transition_trigger:
        info += (
            f'\n<transition_trigger act="{act.act_number}">{html.escape(act.transition_trigger)}</transition_trigger>'
        )
    return info


def build_director_prompt(game: GameState, latest_narration: str, config: EngineConfig | None = None) -> str:
    """Build the Director analysis prompt.

    Slim prompt: reflection blocks, story arc, latest narration, task.
    NPC overview, clocks, and session history available via tools.
    """
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)

    reflection_section = _collect_reflection_blocks(game)
    story_info = _build_story_arc_block(game)

    task = get_prompt("director_task", role="director", lang=lang)
    return f"""<latest_scene>
{latest_narration[: eng().truncations.prompt_xlong]}
</latest_scene>
{story_info}
{reflection_section}

{task}"""


def call_director(
    provider: AIProvider, game: GameState, latest_narration: str, config: EngineConfig | None = None
) -> dict:
    """Call the Director agent for scene analysis and story guidance.

    Two-phase call:
    1. Tool loop: Director queries NPCs, threads, clocks as needed.
    2. json_schema call: Director produces structured guidance with full schema enforcement.

    Phase 1 is skipped if no tools are available or the model doesn't call any.
    """
    log(f"[Director] Analyzing scene {game.narrative.scene_count}")

    prompt = build_director_prompt(game, latest_narration, config)
    tools = get_tools("director")
    system = _director_system(game)

    try:
        _dp = sampling_params("director")
        _director_model = model_for_role("director")

        # Phase 1: tool loop for context gathering
        tool_context = ""
        if tools:
            _dp1 = dict(_dp)
            _dp1["max_retries"] = 1  # Single attempt for tool phase
            response = create_with_retry(
                provider,
                model=_director_model,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
                log_role="director",
                **_dp1,
            )

            if response.stop_reason == "tool_use":
                final_content, tool_log = run_tool_loop(
                    provider,
                    response,
                    role="director",
                    game=game,
                    model=_director_model,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=_dp["max_tokens"],
                    max_tool_rounds=eng().pacing.max_tool_rounds,
                    temperature=_dp.get("temperature"),
                    top_p=_dp.get("top_p"),
                    extra_body=_dp.get("extra_body"),
                    log_role="director",
                )
                if final_content.strip():
                    tool_context = (
                        f"\n<tool_results>\n{final_content[: eng().truncations.prompt_xxlong]}\n</tool_results>"
                    )
                log(f"[Director] Phase 1: {len(tool_log)} tool calls")
            else:
                log("[Director] Phase 1: no tools called")

        # Phase 2: json_schema call for structured output
        phase2_prompt = prompt
        if tool_context:
            phase2_prompt = prompt + tool_context

        response2 = create_with_retry(
            provider,
            model=_director_model,
            system=system,
            messages=[{"role": "user", "content": phase2_prompt}],
            json_schema=get_director_output_schema(),
            log_role="director",
            **_dp,
        )

        guidance = json.loads(response2.content)

        # Convert npc_guidance from array (schema) to dict (internal format)
        if isinstance(guidance.get("npc_guidance"), list):
            guidance["npc_guidance"] = {
                item["npc_id"]: item["guidance"]
                for item in guidance["npc_guidance"]
                if item.get("npc_id") and item.get("guidance")
            }

        log(
            f"[Director] Guidance: "
            f"reflections={len(guidance.get('npc_reflections', []))}, "
            f"summary={guidance.get('scene_summary', '')[: eng().truncations.log_medium]}"
        )
        return guidance
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(
            f"[Director] Failed ({type(e).__name__}: {e}), continuing without guidance",
            level="warning",
        )
        return {}


def _check_engine_act_transition(game: GameState) -> None:
    """Engine-deterministic act transition: fires when scene count exceeds act range."""
    bp = game.narrative.story_blueprint
    if not bp or not bp.acts:
        return
    act = get_current_act(game)
    act_idx = act.act_number - 1
    act_id = f"act_{act_idx}"
    total_acts = len(bp.acts)
    if act.act_number >= total_acts:
        return
    sr = act.scene_range or default_scene_range()
    if game.narrative.scene_count < sr[1]:
        return
    if act_id in bp.triggered_transitions:
        return
    for i in range(act_idx):
        fill_id = f"act_{i}"
        if fill_id not in bp.triggered_transitions:
            bp.triggered_transitions.append(fill_id)
            log(f"[Director] Back-filled skipped act transition: {fill_id}")
    bp.triggered_transitions.append(act_id)
    trigger_text = act.transition_trigger or eng().ai_text.narrator_defaults["unknown_transition_trigger"]
    log(
        f"[Director] Engine act transition: act {act.act_number} "
        f"'{act.phase}' scene {game.narrative.scene_count} ≥ range end {sr[1]}: "
        f"'{trigger_text[: eng().truncations.log_medium]}'"
    )


def _reset_all_reflection_flags(game: GameState, reason: str) -> None:
    """Clear pending reflection flags. Used on API failure and at the end of
    apply_director_guidance for NPCs the director didn't address.
    """
    for npc in game.npcs:
        if npc.needs_reflection:
            npc.needs_reflection = False
            npc.importance_accumulator = 0
            log(f"[Director] Reset reflection for {npc.name} ({reason})")


def _reflection_is_truncated(text: str) -> bool:
    """A reflection without terminal punctuation is almost always a max_tokens cutoff."""
    return not text.rstrip().endswith((".", "!", "?", '"', "»", "…", ")", "–", "—"))


def _append_reflection_memory(npc: NpcData, ref: dict, game: GameState) -> None:
    """Add the reflection as a MemoryEntry on the NPC and reset reflection state."""
    npc.memory.append(
        MemoryEntry(
            scene=game.narrative.scene_count,
            event=ref.get("reflection", ""),
            emotional_weight=ref.get("tone_key") or eng().ai_text.narrator_defaults["reflection_tone_fallback"],
            tone=ref.get("tone", ""),
            tone_key=ref.get("tone_key", ""),
            importance=eng().npc.reflection_importance,
            type="reflection",
            about_npc=resolve_about_npc(game, ref.get("about_npc"), owner_id=npc.id),
        )
    )
    npc.needs_reflection = False
    npc.importance_accumulator = 0
    npc.last_reflection_scene = game.narrative.scene_count


def _apply_agenda_and_instinct_updates(npc: NpcData, ref: dict) -> None:
    """Fill empty agenda/instinct from Director suggestions; update stale agenda/arc
    if Director supplied new versions.
    """
    suggested_agenda = (ref.get("agenda") or "").strip()
    suggested_instinct = (ref.get("instinct") or "").strip()
    if suggested_agenda and not npc.agenda.strip():
        npc.agenda = suggested_agenda
        log(f"[Director] Agenda set for {npc.name}: '{suggested_agenda}'")
    if suggested_instinct and not npc.instinct.strip():
        npc.instinct = suggested_instinct
        log(f"[Director] Instinct set for {npc.name}: '{suggested_instinct}'")

    updated_agenda = (ref.get("updated_agenda") or "").strip()
    updated_arc = (ref.get("updated_arc") or "").strip()
    if updated_agenda and npc.agenda.strip():
        old_agenda = npc.agenda
        npc.agenda = updated_agenda
        _trunc = eng().truncations
        log(
            f"[Director] Agenda updated for {npc.name}: "
            f"'{old_agenda[: _trunc.log_xshort]}' → '{updated_agenda[: _trunc.log_xshort]}'"
        )
    if updated_arc:
        old_arc = npc.arc
        npc.arc = updated_arc
        _trunc = eng().truncations
        log(
            f"[Director] Arc updated for {npc.name}: "
            f"'{old_arc[: _trunc.log_short]}' → '{updated_arc[: _trunc.log_short]}'"
        )


def _clean_director_description(new_desc: str, npc_name: str) -> str:
    """Strip prompt-leak prefixes (SIDEBAR:) and redundant NPC-name prefixes
    ("Sarah Vance —", "Detective:") that the director sometimes copies literally.
    """
    new_desc = re.sub(r"^(?:SIDEBAR\s*(?:LABEL)?[:\-—]\s*)", "", new_desc, flags=re.IGNORECASE).strip()
    if npc_name:
        name_parts = [re.escape(npc_name)] + [re.escape(p) for p in npc_name.split() if len(p) > 2]
        name_pattern = "|".join(name_parts)
        new_desc = re.sub(
            rf"^(?:{name_pattern})(?:\s+(?:{name_pattern}))*\s*[:\-—]\s*",
            "",
            new_desc,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
    return new_desc


def _apply_description_update(npc: NpcData, ref: dict) -> None:
    """Apply updated_description if it's meaningful, not truncated, and cleanable."""
    new_desc = _clean_director_description((ref.get("updated_description") or "").strip(), npc.name)
    if not new_desc or len(new_desc) <= 10:
        return
    _trunc = eng().truncations
    if not is_complete_description(new_desc) and npc.description:
        log(
            f"[Director] Rejected truncated description for {npc.name}: "
            f"'{new_desc[: _trunc.log_short]}' — keeping existing"
        )
        return
    old_desc = npc.description
    npc.description = new_desc
    log(
        f"[Director] Description updated for {npc.name}: "
        f"'{old_desc[: _trunc.log_short]}' → '{new_desc[: _trunc.log_short]}'"
    )


def _process_npc_reflection(game: GameState, ref: dict) -> str | None:
    """Process a single NPC reflection from Director guidance. Returns the NPC's
    id if reflection succeeded, None on skip (NPC missing, empty text, truncated).
    """
    npc_id = ref.get("npc_id", "")
    npc = find_npc(game, npc_id)
    if not npc:
        return None

    reflection_text = ref.get("reflection", "")
    if not reflection_text:
        return None
    if _reflection_is_truncated(reflection_text):
        log(
            f"[Director] Rejected truncated reflection for {npc.name}: "
            f"'{reflection_text[: eng().truncations.log_short]}'",
            level="warning",
        )
        return None

    _append_reflection_memory(npc, ref, game)
    _apply_agenda_and_instinct_updates(npc, ref)
    _apply_description_update(npc, ref)
    consolidate_memory(npc)

    log(f"[Director] Reflection for {npc.name}: {reflection_text[: eng().truncations.log_medium]}")
    return npc_id


def apply_director_guidance(game: GameState, guidance: dict) -> None:
    """Apply Director guidance to game state: store guidance, apply reflections,
    update session log with rich summary.
    """
    if not guidance:
        # API failure — clear all pending reflection flags to prevent zombie loop
        _reset_all_reflection_flags(game, reason="empty guidance")
        return

    game.narrative.director_guidance = DirectorGuidance(
        narrator_guidance=guidance.get("narrator_guidance", ""),
        npc_guidance=guidance.get("npc_guidance", {}),
        arc_notes=guidance.get("arc_notes", ""),
    )

    # Act transition: engine verifies based on scene count vs act range.
    # Director's act_transition signal is advisory — engine owns the call.
    _check_engine_act_transition(game)

    if guidance.get("scene_summary") and game.narrative.session_log:
        game.narrative.session_log[-1].rich_summary = guidance["scene_summary"]

    successfully_reflected: set[str] = set()
    for ref in guidance.get("npc_reflections", []):
        reflected_id = _process_npc_reflection(game, ref)
        if reflected_id is not None:
            successfully_reflected.add(reflected_id)

    # Fallback: reset needs_reflection flag for any NPCs the Director didn't
    # successfully address. Preserve accumulator so they can reach threshold
    # again on the next Director call.
    for npc in game.npcs:
        if npc.needs_reflection and npc.id not in successfully_reflected:
            npc.needs_reflection = False
            log(
                f"[Director] Reset stale reflection flag for {npc.name} "
                f"(accumulator preserved at {npc.importance_accumulator})"
            )

    log("[Director] Guidance applied")


def reset_stale_reflection_flags(game: GameState) -> None:
    """Reset needs_reflection for all pending NPCs.
    Called by the UI layer when a Director turn is skipped (e.g. burn pending,
    or superseded by a new turn). Preserves accumulator."""
    for npc in game.npcs:
        if npc.needs_reflection and npc.status in ("active", "background"):
            npc.needs_reflection = False
            log(f"[Director] Reset stale reflection flag for {npc.name} (skipped turn, accumulator preserved)")
