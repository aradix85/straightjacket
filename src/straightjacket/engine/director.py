#!/usr/bin/env python3
"""Straightjacket Director agent: story steering, NPC reflections, pacing."""

import html
import json
import re

from .ai.provider_base import AIProvider, create_with_retry
from .ai.schemas import DIRECTOR_OUTPUT_SCHEMA
from .config_loader import cfg, sampling_params
from .engine_loader import eng
from .logging_util import log
from .models import EngineConfig, GameState, MemoryEntry
from .xml_utils import xa as _xa
from .npc import (
    consolidate_memory,
    find_npc,
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
    return get_prompt("director_system")


def _director_system(game: GameState, config: EngineConfig | None = None) -> str:
    """Build Director system prompt with content_boundaries."""
    from .prompt_blocks import content_boundaries_block

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


def build_director_prompt(game: GameState, latest_narration: str, config: EngineConfig | None = None) -> str:
    """Build the Director analysis prompt."""
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)

    # Recent session log
    log_entries = []
    for s in game.narrative.session_log[-8:]:
        entry = f"Scene {s.scene}: {s.summary} → {s.result}"
        if s.dramatic_question:
            entry += f" (Q: {s.dramatic_question})"
        log_entries.append(entry)
    log_text = "\n".join(log_entries) or "(start)"

    # NPCs needing reflection or profile completion (empty agenda/instinct)
    reflection_blocks = []
    for n in game.npcs:
        needs_profile = not n.agenda.strip() or not n.instinct.strip()
        if not n.needs_reflection and not needs_profile:
            continue
        if n.status not in ("active", "background"):
            continue
        recent_obs = [m for m in n.memory if m.type == "observation"][-8:]
        mem_text = "; ".join(f"{m.event}({m.emotional_weight})" for m in recent_obs)
        # Include last reflection so Director can build on it, not repeat it
        prev_reflections = [m for m in n.memory if m.type == "reflection"]
        prev_ref_text = ""
        prev_tone_text = ""
        if prev_reflections:
            prev_ref_text = f' last_reflection="{html.escape(prev_reflections[-1].event[:200], quote=True)}"'
            # last_tone = narrative compound (e.g. "protective_guilt") for arc texture
            # last_tone_key = enum word (e.g. "conflicted") for machine-readable evolution
            prev_tone_compound = prev_reflections[-1].tone or prev_reflections[-1].emotional_weight
            prev_tone_key_val = prev_reflections[-1].tone_key
            if prev_tone_compound:
                prev_tone_text += f' last_tone="{html.escape(prev_tone_compound, quote=True)}"'
            if prev_tone_key_val:
                prev_tone_text += f' last_tone_key="{html.escape(prev_tone_key_val, quote=True)}"'
        npc_desc = html.escape(n.description, quote=True)
        # Expose instinct (stable wiring) and arc (current trajectory) so the
        # Director can evolve arc without rewriting instinct.
        instinct_attr = f' instinct="{_xa(n.instinct)}"' if n.instinct.strip() else ""
        arc_attr = f' arc="{_xa(n.arc)}"' if n.arc.strip() else ""
        # Flag NPCs that lack agenda/instinct so Director can suggest them
        needs_profile_attr = ""
        if not n.agenda.strip() or not n.instinct.strip():
            needs_profile_attr = ' needs_profile="true"'
        reflection_blocks.append(
            f'<reflect npc_id="{html.escape(n.id, quote=True)}" name="{html.escape(n.name, quote=True)}" '
            f'disposition="{html.escape(n.disposition, quote=True)}" bond="{n.bond}" '
            f'description="{npc_desc}"{instinct_attr}{arc_attr}{prev_ref_text}{prev_tone_text}{needs_profile_attr}>'
            f"{html.escape(mem_text)}</reflect>"
        )
    reflection_section = "\n".join(reflection_blocks)

    # Story arc info
    story_info = ""
    transition_trigger = ""
    if game.narrative.story_blueprint and game.narrative.story_blueprint.acts:
        act = get_current_act(game)
        bp = game.narrative.story_blueprint
        transition_trigger = act.transition_trigger
        thematic = bp.thematic_thread
        scene_range = act.scene_range or default_scene_range()
        past_range = game.narrative.scene_count > scene_range[1]
        past_range_attr = ' PAST_RANGE="true"' if past_range else ""
        story_info = (
            f'\n<story_arc structure="{html.escape(bp.structure_type, quote=True)}" '
            f'act="{act.act_number}/{act.total_acts}" phase="{html.escape(act.phase, quote=True)}" '
            f'progress="{act.progress}" '
            f'current_scene="{game.narrative.scene_count}" scene_range="{scene_range[0]}-{scene_range[1]}"'
            f"{past_range_attr} "
            f'conflict="{html.escape(bp.central_conflict, quote=True)}"'
        )
        if thematic:
            story_info += f' thematic_thread="{html.escape(thematic, quote=True)}"'
        story_info += "/>"
        if transition_trigger:
            story_info += (
                f'\n<transition_trigger act="{act.act_number}">{html.escape(transition_trigger)}</transition_trigger>'
            )

    # Active NPC overview (include descriptions and aliases so Director stays consistent)
    npc_overview = (
        "\n".join(
            f"- {n.name}({n.id}) {n.disposition} B{n.bond} "
            f"status={n.status}"
            + (f" aka {','.join(n.aliases)}" if n.aliases else "")
            + (f" | {n.description[:80]}" if n.description else "")
            for n in game.npcs
            if n.status in ("active", "background", "lore")
        )
        or "(none)"
    )

    # Clocks overview for Director context
    clocks_block = ""
    if game.world.clocks:
        active_lines = []
        history_lines = []
        for c in game.world.clocks:
            filled = c.filled
            segments = c.segments
            bar = "█" * filled + "░" * (segments - filled)
            pct = int(filled / segments * 100) if segments > 0 else 0
            line = f"- {c.name} ({c.clock_type}): [{bar}] {filled}/{segments} ({pct}%) trigger: {c.trigger_description}"
            if c.fired:
                history_lines.append(line)
            else:
                active_lines.append(line)
        parts = []
        if active_lines:
            parts.append("<clocks>\n" + "\n".join(active_lines) + "\n</clocks>")
        if history_lines:
            parts.append("<clocks_fired>\n" + "\n".join(history_lines) + "\n</clocks_fired>")
        if parts:
            clocks_block = "\n" + "\n".join(parts)

    return f"""<scene_history>
{log_text}
</scene_history>

<latest_scene>
{latest_narration[:1000]}
</latest_scene>

<npcs>
{npc_overview}
</npcs>{clocks_block}
{story_info}
{reflection_section}

<task>
Analyze the latest scene and provide strategic guidance in {lang}.
LANGUAGE RULE: Every text field MUST be in {lang}. Do not use English for any field value, not even partially. Reflections, guidance, descriptions, summaries — all in {lang}.

Field instructions:
- scene_summary: 2-3 sentence summary of what happened and WHY it matters (in {lang})
- narrator_guidance: Specific direction for the next 1-2 scenes (in {lang}). If <story_arc> has a thematic_thread, occasionally anchor the guidance to the aspect of it most alive in the current moment.
- npc_guidance: Array of {{"npc_id": "npc_1", "guidance": "what this NPC should do/feel next"}} — guidance text in {lang}
- pacing: one of tension_rising, building, climax, breather, resolution
- npc_reflections: Only for NPCs listed in <reflect> tags. Each object has:
  - npc_id: the NPC's ID from the <reflect> tag
  - reflection: 1-2 sentence higher-level insight (in {lang})
  - tone: 1-3 English words capturing the emotional shift (e.g. 'protective_guilt', 'reluctant_trust')
  - tone_key: ONE word from the enum (neutral, curious, wary, suspicious, grateful, terrified, loyal, conflicted, betrayed, devastated, euphoric, defiant, guilty, protective, angry, devoted, impressed, hopeful)
  - updated_description: STRICTLY in {lang}. Max 100 characters. Role + key visual traits + personality. Keep physical details like age, hair, build. Do NOT start with the NPC's name. NO actions, NO posture. Example: 'Grumpy dwarf blacksmith with burn scars, secretly loyal'. null if unchanged.
  - agenda: NPC's hidden goal (max 8 words, only if needs_profile="true"), null otherwise
  - instinct: NPC's psychological signature under real pressure (max 8 words, only if needs_profile="true"), null otherwise. NOT job demeanor or genre convention — the specific human underneath: what they do when their strategy fails, what betrays them, what is slightly irrational but inevitable. BAD: "stays calm under pressure" / "methodical and efficient". GOOD: "goes quiet and hyper-precise when cornered" / "agrees then quietly does what he intended". Instinct is set ONCE (first reflection, needs_profile=true) and never updated — it is the NPC's wiring, not their mood.
  - updated_agenda: If the NPC already HAS an agenda but events have made it stale or obsolete, provide a NEW agenda (max 8 words, in {lang}). null if current agenda is still valid.
  - updated_arc: The NPC's current narrative trajectory — what the story has made of them so far. 1-2 sentences in {lang}, from an inside perspective (their emotional state and what they have become, not what they will do next). Expected to change every reflection as the story develops. The <reflect> tag shows the current arc if set — build on it, deepen it, or shift it based on what just happened. Distinct from instinct (stable wiring) and npc_guidance (scene instruction). null only if the NPC has had zero meaningful story interaction.
- arc_notes: Brief story arc progress observation
- act_transition: Evaluate whether the current act's <transition_trigger> has been fulfilled by recent events. Set to true if:
  (a) the narrative condition described in the trigger has clearly been met, OR
  (b) the story has moved PAST the act's scene_range (PAST_RANGE="true") and the trigger's spirit has been approximately met.
  Set to false only if the trigger condition is clearly unmet AND we are still within scene_range. The scene_range is a fallback — content-driven transitions via this flag produce better pacing.

If a <reflect> tag has a last_reflection attribute, write a NEW insight that builds on, deepens, or contradicts it. Do NOT repeat the same theme or emotional tone. If last_tone is present, evolve the emotion — show how the NPC's feelings have shifted, intensified, or transformed since then.
</task>"""


def call_director(
    provider: AIProvider, game: GameState, latest_narration: str, config: EngineConfig | None = None
) -> dict:
    """Call the Director agent for scene analysis and story guidance.
    Returns a dict with guidance fields, or empty dict on failure."""
    log(f"[Director] Analyzing scene {game.narrative.scene_count}")

    prompt = build_director_prompt(game, latest_narration, config)

    try:
        _c = cfg()
        response = create_with_retry(
            provider,
            max_retries=_c.ai.max_retries.director,
            model=_c.ai.director_model,
            max_tokens=_c.ai.max_tokens.director,
            system=_director_system(game, config),
            messages=[{"role": "user", "content": prompt}],
            json_schema=DIRECTOR_OUTPUT_SCHEMA,
            **sampling_params("director"),
        )
        guidance = json.loads(response.content)

        # Convert npc_guidance from array (schema) to dict (internal format)
        # Array format: [{"npc_id": "npc_1", "guidance": "..."}]
        # Dict format:  {"npc_1": "..."} — used by narrator prompts and savegames
        if isinstance(guidance.get("npc_guidance"), list):
            guidance["npc_guidance"] = {
                item["npc_id"]: item["guidance"]
                for item in guidance["npc_guidance"]
                if item.get("npc_id") and item.get("guidance")
            }

        log(
            f"[Director] Guidance: pacing={guidance.get('pacing', '?')}, "
            f"reflections={len(guidance.get('npc_reflections', []))}, "
            f"summary={guidance.get('scene_summary', '')[:80]}"
        )
        return guidance
    except Exception as e:
        log(
            f"[Director] Structured output failed ({type(e).__name__}: {e}), continuing without guidance",
            level="warning",
        )
        return {}


def _map_pacing_hint(hint: str) -> str:
    """Map engine pacing hint to Director pacing vocabulary."""
    return {"breather": "breather", "action": "tension_rising", "neutral": "building"}.get(hint, "building")


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
    trigger_text = act.transition_trigger or "?"
    log(
        f"[Director] Engine act transition: act {act.act_number} "
        f"'{act.phase}' scene {game.narrative.scene_count} ≥ range end {sr[1]}: '{trigger_text[:80]}'"
    )


def apply_director_guidance(game: GameState, guidance: dict) -> None:
    """Apply Director guidance to game state: store guidance, apply reflections,
    update session log with rich summary."""
    if not guidance:
        # API failure — reset all pending reflection flags to prevent zombie loop
        for npc in game.npcs:
            if npc.needs_reflection:
                npc.needs_reflection = False
                npc.importance_accumulator = 0
                log(f"[Director] Reset reflection for {npc.name} (empty guidance)")
        return

    # Store guidance for next narrator call — pacing computed by engine, not AI
    from .mechanics import get_pacing_hint
    from .models import DirectorGuidance

    engine_pacing = _map_pacing_hint(get_pacing_hint(game))
    ai_pacing = guidance.get("pacing", "")
    if ai_pacing and ai_pacing != engine_pacing:
        log(f"[Director] Pacing override: AI={ai_pacing} → engine={engine_pacing}")

    game.narrative.director_guidance = DirectorGuidance(
        narrator_guidance=guidance.get("narrator_guidance", ""),
        npc_guidance=guidance.get("npc_guidance", {}),
        pacing=engine_pacing,
        arc_notes=guidance.get("arc_notes", ""),
    )

    # Handle act transition: engine checks scene count vs act range.
    # Director's act_transition signal is advisory — engine verifies.
    _check_engine_act_transition(game)

    # Enrich the latest session log entry with Director's summary
    if guidance.get("scene_summary") and game.narrative.session_log:
        game.narrative.session_log[-1].rich_summary = guidance["scene_summary"]

    successfully_reflected_ids = set()  # Only NPCs whose reflections passed all checks
    for ref in guidance.get("npc_reflections", []):
        npc_id = ref.get("npc_id", "")
        ref_npc = find_npc(game, npc_id)
        if not ref_npc:
            continue

        reflection_text = ref.get("reflection", "")
        if not reflection_text:
            continue
        # Reject truncated reflections (max_tokens cutoff)
        if not reflection_text.rstrip().endswith((".", "!", "?", '"', "»", "…", ")", "–", "—")):
            log(
                f"[Director] Rejected truncated reflection for {ref_npc.name}: '{reflection_text[:60]}'",
                level="warning",
            )
            continue

        ref_npc.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=reflection_text,
                emotional_weight=ref.get("tone_key") or "reflective",
                tone=ref.get("tone", ""),
                tone_key=ref.get("tone_key", ""),
                importance=8,
                type="reflection",
                about_npc=resolve_about_npc(game, ref.get("about_npc"), owner_id=ref_npc.id),
            )
        )
        ref_npc.needs_reflection = False
        ref_npc.importance_accumulator = 0
        ref_npc.last_reflection_scene = game.narrative.scene_count

        # Fill empty agenda/instinct if Director suggested them
        suggested_agenda = (ref.get("agenda") or "").strip()
        suggested_instinct = (ref.get("instinct") or "").strip()
        if suggested_agenda and not ref_npc.agenda.strip():
            ref_npc.agenda = suggested_agenda
            log(f"[Director] Agenda set for {ref_npc.name}: '{suggested_agenda}'")
        if suggested_instinct and not ref_npc.instinct.strip():
            ref_npc.instinct = suggested_instinct
            log(f"[Director] Instinct set for {ref_npc.name}: '{suggested_instinct}'")

        # Update stale agenda if Director provided new version; apply arc evolution
        updated_agenda = (ref.get("updated_agenda") or "").strip()
        updated_arc = (ref.get("updated_arc") or "").strip()
        if updated_agenda and ref_npc.agenda.strip():
            old_agenda = ref_npc.agenda
            ref_npc.agenda = updated_agenda
            log(f"[Director] Agenda updated for {ref_npc.name}: '{old_agenda[:40]}' → '{updated_agenda[:40]}'")
        if updated_arc:
            if len(updated_arc) > 300:
                log(f"[Director] Rejected arc for {ref_npc.name}: too long ({len(updated_arc)} chars)", level="warning")
            else:
                old_arc = ref_npc.arc
                ref_npc.arc = updated_arc
                log(f"[Director] Arc updated for {ref_npc.name}: '{old_arc[:60]}' → '{updated_arc[:60]}'")

        # Update description if Director provided a meaningful character description
        new_desc = (ref.get("updated_description") or "").strip()
        # Safety net: strip prompt-leak prefixes the AI may copy literally
        new_desc = re.sub(r"^(?:SIDEBAR\s*(?:LABEL)?[:\-—]\s*)", "", new_desc, flags=re.IGNORECASE).strip()
        # Strip redundant NPC name prefix ("Detective Vance:", "Sarah Vance –", etc.)
        npc_name = ref_npc.name
        if npc_name:
            # Match full name or any single word from the name, followed by : or – or -
            name_parts = [re.escape(npc_name)] + [re.escape(p) for p in npc_name.split() if len(p) > 2]
            name_pattern = "|".join(name_parts)
            new_desc = re.sub(
                rf"^(?:{name_pattern})(?:\s+(?:{name_pattern}))*\s*[:\-—]\s*",
                "",
                new_desc,
                count=1,
                flags=re.IGNORECASE,
            ).strip()
        if new_desc and len(new_desc) > 10:
            # Reject scene snapshots: too long
            if len(new_desc) > 200:
                log(
                    f"[Director] Rejected description for {ref_npc.name}: "
                    f"too long ({len(new_desc)} chars), likely scene snapshot"
                )
            elif not is_complete_description(new_desc) and ref_npc.description:
                log(
                    f"[Director] Rejected truncated description for {ref_npc.name}: "
                    f"'{new_desc[:60]}' — keeping existing"
                )
            else:
                old_desc = ref_npc.description
                ref_npc.description = new_desc
                log(f"[Director] Description updated for {ref_npc.name}: '{old_desc[:60]}' → '{new_desc[:60]}'")

        # Consolidate after adding reflection
        consolidate_memory(ref_npc)
        successfully_reflected_ids.add(npc_id)

        log(f"[Director] Reflection for {ref_npc.name}: {reflection_text[:80]}")

    # Fallback: reset needs_reflection AND accumulator for any NPCs the Director
    # didn't successfully address. Without accumulator reset, the flag re-triggers
    # immediately on the next memory update (zombie-reflection loop).
    for npc in game.npcs:
        if npc.needs_reflection and npc.id not in successfully_reflected_ids:
            npc.needs_reflection = False
            npc.importance_accumulator = 0
            log(f"[Director] Reset stale reflection for {npc.name} (accumulator zeroed)")

    log(f"[Director] Guidance applied: pacing={guidance.get('pacing', '?')}")


def reset_stale_reflection_flags(game: GameState) -> None:
    """Reset needs_reflection and importance_accumulator for all pending NPCs.
    Called by the UI layer when a Director turn is skipped (e.g. burn pending,
    or superseded by a new turn) to prevent indefinite flag accumulation."""
    for npc in game.npcs:
        if npc.needs_reflection and npc.status in ("active", "background"):
            npc.needs_reflection = False
            npc.importance_accumulator = 0
            log(f"[Director] Reset stale reflection for {npc.name} (skipped turn)")
