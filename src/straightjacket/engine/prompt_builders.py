#!/usr/bin/env python3
"""Straightjacket prompt builders: dialog, action, NPC blocks, pacing."""

import json
import random

from ..i18n import E
from .engine_loader import eng
from .logging_util import log
from .mechanics import get_pacing_hint, locations_match
from .models import BrainResult, EngineConfig, GameState, NpcData, RollResult
from .npc import find_npc, retrieve_memories
from .prompt_blocks import (
    narrative_direction_block,
    recent_events_block,
    story_context_block,
)
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def creativity_seed(n: int = 3, rng: random.Random | None = None) -> str:
    """Pick random seed words from engine.yaml for narrator inspiration.
    Pass rng for deterministic output in tests."""
    words = list(eng().creativity_seeds)
    _rng = rng or random
    return " ".join(_rng.sample(words, min(n, len(words))))


# ── Shared prompt fragments ──────────────────────────────────


def _scene_header(game: GameState) -> str:
    """Single source of truth for <world>/<character> opening lines in all narrator prompts."""
    return (
        f'<world genre="{_xa(game.setting_genre)}" tone="{_xa(game.setting_tone)}">'
        f"{_xe(game.setting_description)}</world>\n"
        f'<character name="{_xa(game.player_name)}">'
        f"{_xe(game.character_concept)}</character>"
    )


def _time_ctx(game: GameState) -> str:
    return f"\n<time>{_xe(game.world.time_of_day)}</time>" if game.world.time_of_day else ""


def _loc_hist(game: GameState) -> str:
    if not game.world.location_history:
        return ""
    return f"\n<prev_locations>{_xe(', '.join(game.world.location_history[-3:]))}</prev_locations>"


# PROMPT BUILDERS


def build_new_game_prompt(game: GameState) -> str:
    crisis = "\n<crisis>Character at breaking point.</crisis>" if game.crisis_mode else ""
    story = story_context_block(game)
    seed = creativity_seed()
    log(f"[Narrator] Opening creativity_seed={seed!r}")

    # Character details
    pronouns_tag = f"\n<pronouns>{_xe(game.pronouns)}</pronouns>" if game.pronouns else ""
    paths_tag = f"\n<paths>{_xe(', '.join(game.paths))}</paths>" if game.paths else ""
    vow_tag = f"\n<vow>{_xe(game.background_vow)}</vow>" if game.background_vow else ""

    return f"""<scene type="opening">
{_scene_header(game)}{pronouns_tag}{paths_tag}{vow_tag}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}
<situation>{_xe(game.world.current_scene_context)}</situation>{crisis}
{story}</scene>
<task>
Opening scene. 3-4 paragraphs. The player character arrives, wakes, or sits somewhere.
Describe what they PERCEIVE: light, sounds, smells, the space. Atmosphere first, then one thing that is out of place — a detail that invites curiosity but explains nothing.
One NPC is present and active — doing something, not waiting. A second person is glimpsed or mentioned but not yet met.
The scene ends mid-moment: a sensory detail, an unfinished gesture, a sound from the wrong direction. The player decides what happens next.
IMPORTANT: {game.player_name} is the PLAYER CHARACTER (the "you" in narration). Do NOT include them as an NPC.{f" Use {game.pronouns} pronouns for the player character." if game.pronouns else ""}
If <backstory> exists in system context, treat those facts as established canon — reference naturally, do not retell.
If player_wishes exist, do NOT address them in the opening — save them for later scenes.
creativity_seed: {seed} (loose inspiration for NPC names, locations, scene details — not literal)
Write ONLY narrative prose. No metadata, no JSON.
</task>"""


def _npc_block(game: GameState, target_id: str | None, context_text: str = "") -> str:
    """Build full context block for the target NPC using weighted memory retrieval."""
    target = find_npc(game, target_id) if target_id else None
    if not target:
        return ""
    # Retrieve best memories using weighted scoring
    memories = retrieve_memories(
        target, context_text=context_text, max_count=5, current_scene=game.narrative.scene_count
    )
    # Separate reflections and observations for structured display
    reflections = [m for m in memories if m.type == "reflection"]
    observations = [m for m in memories if m.type != "reflection"]

    # Build memory text
    mem_parts = []
    if reflections:
        ref_text = " | ".join(m.event for m in reflections)
        mem_parts.append(f"insight: {ref_text}")
    if observations:
        obs_text = " | ".join(f"{m.event}({m.emotional_weight})" for m in observations)
        mem_parts.append(f"recent: {obs_text}")

    mem_str = "\n".join(mem_parts) if mem_parts else "(no memories)"

    secs = json.dumps(target.secrets, ensure_ascii=False)
    aliases_attr = f' aliases="{_xa(",".join(target.aliases))}"' if target.aliases else ""
    arc_attr = f' arc="{_xa(target.arc)}"' if target.arc.strip() else ""
    return f"""<target_npc name="{_xa(target.name)}" disposition="{_xa(target.disposition)}" bond="{target.bond}/{target.bond_max}"{aliases_attr}{arc_attr}>
agenda:{_xe(target.agenda)} instinct:{_xe(target.instinct)}
{_xe(mem_str)}
secrets(weave subtly,never reveal):{_xe(secs)}
</target_npc>"""


def _activated_npcs_block(
    activated: list[NpcData], target_id: str | None, game: GameState, context_text: str = ""
) -> str:
    """Build context blocks for activated NPCs (not the target — those get _npc_block).
    Lighter context than target: name, disposition, bond, and 1-2 key memories."""
    parts = []
    for npc in activated:
        # Skip target NPC (handled by _npc_block)
        if target_id and (npc.id == target_id or npc.name.lower() == str(target_id).lower()):
            continue
        memories = retrieve_memories(
            npc, context_text=context_text, max_count=2, current_scene=game.narrative.scene_count
        )
        mem_hint = ""
        if memories:
            reflections = [m for m in memories if m.type == "reflection"]
            if reflections:
                mem_hint = f' insight="{_xa(reflections[0].event[:80])}"'
            else:
                hint_text = f"{memories[0].event[:60]}({memories[0].emotional_weight})"
                mem_hint = f' recent="{_xa(hint_text)}"'

        # Spatial hint: show last location if different from player's current location
        loc_hint = ""
        loc = _npc_location_hint(npc, game.world.current_location or "")
        if loc:
            loc_hint = f' last_seen="{_xa(loc)}"'

        arc_hint = f' arc="{_xa(npc.arc)}"' if npc.arc.strip() else ""
        parts.append(
            f'<activated_npc name="{_xa(npc.name)}" disposition="{_xa(npc.disposition)}" '
            f'bond="{npc.bond}"{arc_hint}{mem_hint}{loc_hint}/>'
        )
    return "\n".join(parts)


def _known_npcs_string(mentioned: list[NpcData], game: GameState, exclude_ids: set | None = None) -> str:
    """Build compact known-NPCs line for name-only mentions.
    Also includes remaining active/background NPCs not in activated or mentioned."""
    exclude_ids = exclude_ids or set()
    player_loc = game.world.current_location or ""
    parts = []

    def _npc_entry(n):
        entry = f"{_xe(n.name)}({_xe(n.disposition)})"
        if n.status == "background":
            entry += "[bg]"
        loc = _npc_location_hint(n, player_loc)
        if loc:
            entry += f"[at:{_xe(loc)}]"
        return entry

    # Mentioned NPCs (scored but below activation threshold)
    for n in mentioned:
        if n.id in exclude_ids:
            continue
        parts.append(_npc_entry(n))
        exclude_ids.add(n.id)

    # Remaining active NPCs not yet included
    for n in game.npcs:
        if n.id in exclude_ids:
            continue
        if n.status not in ("active", "background"):
            continue
        parts.append(_npc_entry(n))

    return ", ".join(parts) or "none"


def _pacing_block(game: GameState, chaos_interrupt: str | None = None, dramatic_question: str = "") -> str:
    """Build pacing/chaos/dramatic_question block for prompts."""
    parts = []
    pacing = get_pacing_hint(game)
    if pacing != "neutral":
        parts.append(f'<pacing type="{pacing}"/>')
    if dramatic_question:
        parts.append(f"<dramatic_question>{_xe(dramatic_question)}</dramatic_question>")
    if chaos_interrupt:
        interrupt_descriptions = {
            "npc_unexpected": "An NPC arrives unexpectedly or acts completely against their established pattern",
            "threat_escalation": "An existing danger escalates dramatically or a new threat emerges from nowhere",
            "twist": "Something believed to be true is revealed as false, or an ally shows hidden motives",
            "discovery": "An unexpected object, clue, or piece of information falls into the player's hands",
            "environment_shift": "The environment changes dramatically — sudden weather, structural collapse, fire, flood, unnatural darkness, or a strange phenomenon alters the scene conditions",
            "remote_event": "News arrives or signs appear that something important happened elsewhere — an ally is in trouble, a faction made a move, or a place the player knows has changed",
            "positive_windfall": "An unexpected piece of good fortune — a hidden cache, an uninvited ally, a lucky coincidence, or a momentary reprieve from danger",
            "callback": "A consequence of a past action catches up — a previous decision backfires or pays off, an old debt is called in, or a forgotten detail becomes suddenly relevant",
            "dilemma": "The scene presents the character with a forced choice between two things they value — there is no clean option, only sacrifice and consequence. Make BOTH options tangible and costly",
            "ticking_clock": "A sudden time pressure or deadline is introduced — something must happen soon or an opportunity is lost, a threat becomes unstoppable, or a situation becomes irreversible",
        }
        desc = interrupt_descriptions.get(chaos_interrupt, "Something unexpected disrupts the scene")
        parts.append(f'<chaos_interrupt type="{chaos_interrupt}">{desc}</chaos_interrupt>')
    return "\n".join(parts)


def _npcs_present_string(game: GameState) -> str:
    """Build <npcs_present> content including aliases so Narrator recognizes known NPCs."""
    player_loc = game.world.current_location or ""
    parts = []
    for n in game.npcs:
        if n.status != "active":
            continue
        entry = f"{_xe(n.name)}:{_xe(n.disposition)}"
        if n.aliases:
            entry += f"(aka {_xe(','.join(n.aliases))})"
        loc = _npc_location_hint(n, player_loc)
        if loc:
            entry += f"[at:{_xe(loc)}]"
        parts.append(entry)
    return ", ".join(parts) or "none"


def _lore_figures_block(game: GameState) -> str:
    """Build a slim context block for lore figures — named persons who are narratively
    significant but never physically present."""
    lore = [n for n in game.npcs if n.status == "lore"]
    if not lore:
        return ""
    parts = []
    for n in lore:
        entry = _xe(n.name)
        if n.description:
            entry += f": {_xe(n.description[:80])}"
        if n.aliases:
            entry += f" (aka {_xe(', '.join(n.aliases[:2]))})"
        parts.append(entry)
    return f"\n<lore_figures>{'; '.join(parts)}</lore_figures>"


def _npc_location_hint(npc: NpcData, player_loc: str) -> str:
    """Spatial hint attribute when NPC is at a different location than the player."""
    npc_loc = npc.last_location
    if npc_loc and player_loc and not locations_match(npc_loc, player_loc):
        return npc_loc
    return ""


def _npcs_section(
    game: GameState,
    brain: BrainResult,
    context_text: str,
    activated_npcs: list[NpcData] | None,
    mentioned_npcs: list[NpcData] | None,
) -> str:
    """Build the three-tier NPC section used by both dialog and action prompts."""
    target_id = brain.target_npc
    if activated_npcs is not None:
        activated_block = _activated_npcs_block(activated_npcs, target_id, game, context_text)
        exclude_ids = {n.id for n in activated_npcs}
        if target_id:
            t = find_npc(game, target_id)
            if t:
                exclude_ids.add(t.id)
        known_str = _known_npcs_string(mentioned_npcs or [], game, exclude_ids)
        section = ""
        if activated_block:
            section += f"\n{activated_block}"
        section += f"\n<known_npcs>{known_str}</known_npcs>"
        section += _lore_figures_block(game)
        return section
    all_npcs = _npcs_present_string(game)
    return f"\n<npcs_present>{all_npcs}</npcs_present>" + _lore_figures_block(game)


def _director_block(game: GameState) -> str:
    """Build director guidance injection block for narrator prompts."""
    dg = game.narrative.director_guidance
    if not dg or not dg.narrator_guidance:
        return ""
    block = f"\n<director_guidance>{_xe(dg.narrator_guidance)}</director_guidance>"
    for npc_id, guidance in dg.npc_guidance.items():
        block += f'\n<npc_note for="{_xa(npc_id)}">{_xe(guidance)}</npc_note>'
    return block


def build_dialog_prompt(
    game: GameState,
    brain: BrainResult,
    player_words: str = "",
    chaos_interrupt: str | None = None,
    activated_npcs: list[NpcData] | None = None,
    mentioned_npcs: list[NpcData] | None = None,
    config: EngineConfig | None = None,
) -> str:
    context_text = f"{player_words} {brain.player_intent or ''} {game.world.current_scene_context or ''}"
    npc = _npc_block(game, brain.target_npc, context_text=context_text)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    crisis = "\n<crisis/>" if game.crisis_mode else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""
    pacing = _pacing_block(game, chaos_interrupt, brain.dramatic_question)
    director = _director_block(game)

    return f"""<scene type="dialog" n="{game.narrative.scene_count}">
{_scene_header(game)}
<intent>{_xe(brain.player_intent)}</intent>{pw}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}
{npc}{npcs_sect}{wl}{crisis}
{pacing}{director}
{narrative_direction_block(game, "dialog")}
{story_context_block(game)}{recent_events_block(game)}</scene>
<task>2-3 paragraphs of immersive narration. Focus entirely on atmosphere, dialog, and character interaction. Even a quiet conversation carries the weight of the surrounding act phase {E["dash"]} let <story_arc> mood shape the texture of the exchange. If <director_guidance> is present, follow its narrative direction while maintaining your creative voice.</task>"""


def build_action_prompt(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    consequences: list[str],
    clock_events: list,
    npc_agency: list[str],
    player_words: str = "",
    chaos_interrupt: str | None = None,
    activated_npcs: list[NpcData] | None = None,
    mentioned_npcs: list[NpcData] | None = None,
    config: EngineConfig | None = None,
) -> str:
    context_text = f"{player_words} {brain.player_intent or ''} {game.world.current_scene_context or ''}"
    npc = _npc_block(game, brain.target_npc, context_text=context_text)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""

    position = brain.position
    effect = brain.effect

    match_tag = ' match="true"' if roll.match else ""
    if roll.result == "MISS":
        clk = "".join(f' clock_triggered="{_xa(e.clock)}:{_xa(e.trigger)}"' for e in clock_events)
        match_hint = (
            " A MATCH \u2014 the situation escalates dramatically, a fateful twist makes everything worse."
            if roll.match
            else ""
        )
        constraint = f'<result type="MISS"{match_tag} consequences="{_xa(",".join(consequences))}"{clk}>Concrete failure. No silver linings. Make it hurt.{match_hint}</r>'
    elif roll.result == "WEAK_HIT":
        match_hint = (
            " A MATCH \u2014 despite the cost, something unexpected and significant happens, a twist of fate."
            if roll.match
            else ""
        )
        cons_attr = f' consequences="{_xa(",".join(consequences))}"' if consequences else ""
        constraint = (
            f'<result type="WEAK_HIT"{match_tag}{cons_attr}>Success with tangible cost or complication.{match_hint}</r>'
        )
    else:
        match_hint = (
            " A MATCH \u2014 an unexpected boon, a fateful revelation, or a dramatic advantage beyond the clean success."
            if roll.match
            else ""
        )
        cons_attr = f' consequences="{_xa(",".join(consequences))}"' if consequences else ""
        constraint = f'<result type="STRONG_HIT"{match_tag}{cons_attr}>Clean success.{match_hint}</r>'

    position_tag = f'<position level="{_xa(position)}" effect="{_xa(effect)}"/>'

    status_flags = []
    if game.resources.health <= 0:
        status_flags.append("WOUNDED")
    if game.resources.spirit <= 0:
        status_flags.append("BROKEN")
    if game.resources.supply <= 0:
        status_flags.append("DEPLETED")
    if game.game_over:
        status_flags.append("FINAL_SCENE:dramatic ending,character falls,make it meaningful")
    elif game.crisis_mode:
        status_flags.append("CRISIS:desperate,world closing in")

    flags = f"\n<flags>{','.join(status_flags)}</flags>" if status_flags else ""
    agency = f"\n<npc_agency>{_xe('| '.join(npc_agency))}</npc_agency>" if npc_agency else ""
    pacing = _pacing_block(game, chaos_interrupt, brain.dramatic_question)
    director = _director_block(game)

    return f"""<scene type="action" n="{game.narrative.scene_count}">
{_scene_header(game)}
<intent>{_xe(brain.player_intent)} ({_xe(brain.approach)})</intent>{pw}
{constraint}
{position_tag}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}
{npc}{npcs_sect}{wl}{flags}{agency}
{pacing}{director}
{narrative_direction_block(game, roll.result)}
{story_context_block(game)}{recent_events_block(game)}</scene>
<task>2-4 paragraphs of immersive narration. Let the current act's mood from <story_arc> shape the texture of the outcome {E["dash"]} a STRONG_HIT in a desperate phase still carries the surrounding darkness. If <director_guidance> is present, follow its narrative direction while maintaining your creative voice.</task>"""


# ── Chapter / epilogue prompts ───────────────────────────────


def build_epilogue_prompt(game: GameState) -> str:
    """Build prompt for generating an epilogue that wraps up the story."""
    from .prompt_blocks import campaign_history_block

    bp = game.narrative.story_blueprint
    endings = bp.possible_endings if bp else []
    endings_text = ", ".join(f"{e.type}: {e.description}" for e in endings) if endings else "open"
    conflict = bp.central_conflict if bp else ""

    npc_block = "\n".join(
        f'<npc name="{_xa(n.name)}" disposition="{_xa(n.disposition)}" bond="{n.bond}/{n.bond_max}">'
        f"{_xe(n.description)}</npc>"
        for n in game.npcs
        if n.status == "active"
    )

    log_text = "; ".join(
        f"S{s.scene}:{_xe(s.rich_summary or s.summary)}({s.result})" for s in game.narrative.session_log[-15:]
    )

    return f"""<scene type="epilogue">
{_scene_header(game)}
<location>{_xe(game.world.current_location)}</location>
<situation>{_xe(game.world.current_scene_context)}</situation>
<conflict>{_xe(conflict)}</conflict>
<possible_endings>{_xe(endings_text)}</possible_endings>
{npc_block}
{campaign_history_block(game)}
<session_log>{log_text}</session_log>
</scene>
<task>
Write a beautiful EPILOGUE for this story (4-6 paragraphs). This is NOT a new scene — no dice, no mechanics.
- PERSPECTIVE: Second person singular ("you") throughout. Do NOT shift to third person.
- Reflect on the character's journey and growth
- Give closure to the most important NPC relationships (reference them by name)
- Resolve or acknowledge the central conflict based on what actually happened
- Match the tone of the story — if it was dark, the ending can be bittersweet; if hopeful, it can be warm
- End with a final image or moment that captures the essence of this adventure
- Do NOT introduce new conflicts or cliffhangers — this is closure
- No metadata blocks, no game_data, no memory_updates — pure narrative prose only
</task>"""


def build_new_chapter_prompt(game: GameState) -> str:
    """Build opening prompt for a new chapter in an ongoing campaign."""
    from .prompt_blocks import campaign_history_block

    npc_block = "\n".join(
        f'<returning_npc id="{_xa(n.id)}" name="{_xa(n.name)}" disposition="{_xa(n.disposition)}" '
        f'bond="{n.bond}/{n.bond_max}"'
        + (f' aliases="{_xa(",".join(n.aliases))}"' if n.aliases else "")
        + f">{_xe(n.description)}</returning_npc>"
        for n in game.npcs
        if n.status == "active"
    )
    bg_npcs = [n for n in game.npcs if n.status == "background"]
    if bg_npcs:
        bg_parts = []
        for n in bg_npcs:
            entry = f"{_xe(n.name)}({_xe(n.disposition)})"
            if n.aliases:
                entry += f"[aka {_xe(','.join(n.aliases))}]"
            bg_parts.append(entry)
        bg_names = ", ".join(bg_parts)
        npc_block += f"\n<background_npcs>Known but not recently active: {bg_names}</background_npcs>"

    evolutions_block = ""
    if game.campaign.campaign_history:
        last_ch = game.campaign.campaign_history[-1]
        evolutions = last_ch.npc_evolutions
        if evolutions:
            evo_lines = "\n".join(
                f"  {_xe(e.name)}: {_xe(e.projection)}" for e in evolutions if e.name and e.projection
            )
            evolutions_block = (
                f'\n<npc_evolutions hint="These are PROJECTIONS of how NPCs may have changed '
                f'during the time skip. Use as inspiration, not as hard facts.">'
                f"\n{evo_lines}\n</npc_evolutions>"
            )

    seed = creativity_seed()
    log(f"[Narrator] Chapter {game.campaign.chapter_number} opening creativity_seed={seed!r}")

    return f"""<scene type="chapter_opening" chapter="{game.campaign.chapter_number}">
{_scene_header(game)}
<location>{_xe(game.world.current_location)}</location>{_time_ctx(game)}
<situation>{_xe(game.world.current_scene_context)}</situation>
{campaign_history_block(game)}
{npc_block}{evolutions_block}
{story_context_block(game)}</scene>
<task>
Chapter {game.campaign.chapter_number} opening: 3-4 paragraphs. This is a NEW chapter in an ongoing campaign.
- Reference the character's history and relationships naturally (don't recap everything, just hint)
- Some time has passed since last chapter. Show how the world/relationships evolved
- Use <npc_evolutions> as hints for how NPCs may have changed — show their evolution through behavior, dialog, and atmosphere rather than exposition
- Introduce a NEW tension or situation that builds on unresolved threads
- Returning NPCs should feel familiar but may have changed
- Introduce 1-2 NEW NPCs alongside returning characters
- Create one new threat clock for this chapter
IMPORTANT: The <character> above is the PLAYER CHARACTER. Do NOT include them as an NPC.
creativity_seed: {seed} (Use as loose inspiration for NPC names, locations, and scene details — not literally, but as creative anchors to avoid generic defaults)
Write ONLY narrative prose. No metadata, no JSON, no game_data blocks.
</task>"""
