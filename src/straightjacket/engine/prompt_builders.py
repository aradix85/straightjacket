#!/usr/bin/env python3
"""Straightjacket prompt builders: dialog, action, NPC blocks, pacing."""

import json
import random

from .engine_loader import eng
from .logging_util import log
from .mechanics import get_pacing_hint, locations_match
from collections.abc import Sequence

from .models import BrainResult, EngineConfig, GameState, NpcData, RandomEvent, RollResult, ThreatEvent
from .mechanics.scene import SceneSetup
from .npc import find_npc, get_npc_bond, retrieve_memories
from .prompt_blocks import (
    narrative_direction_block,
    recent_events_block,
    story_context_block,
)
from .prompt_loader import get_prompt
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
    impacts_tag = ""
    if game.impacts:
        from .mechanics.impacts import impact_label

        labels = ", ".join(impact_label(k) for k in game.impacts)
        impacts_tag = f'\n<character_state impacts="{_xa(labels)}"/>'
    return (
        f'<world genre="{_xa(game.setting_genre)}" tone="{_xa(game.setting_tone)}">'
        f"{_xe(game.setting_description)}</world>\n"
        f'<character name="{_xa(game.player_name)}">'
        f"{_xe(game.character_concept)}</character>"
        f"{impacts_tag}"
    )


def _time_ctx(game: GameState) -> str:
    return f"\n<time>{_xe(game.world.time_of_day)}</time>" if game.world.time_of_day else ""


def _loc_hist(game: GameState) -> str:
    if not game.world.location_history:
        return ""
    n = eng().location.prompt_history_size
    return f"\n<prev_locations>{_xe(', '.join(game.world.location_history[-n:]))}</prev_locations>"


def _scene_enrichment(game: GameState) -> str:
    """Build scene enrichment context: top-weight active thread."""
    threads = [t for t in game.narrative.threads if t.active]
    if not threads:
        return ""
    threads.sort(key=lambda t: t.weight, reverse=True)
    return f"\n<active_thread>{_xe(threads[0].name)}</active_thread>"


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

    pronouns_hint = f" Use {game.pronouns} pronouns for the player character." if game.pronouns else ""
    task = get_prompt(
        "task_opening",
        player_name=game.player_name,
        pronouns_hint=pronouns_hint,
        seed=seed,
    )

    return f"""<scene type="opening">
{_scene_header(game)}{pronouns_tag}{paths_tag}{vow_tag}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}
<situation>{_xe(game.world.current_scene_context)}</situation>{crisis}
{story}</scene>
<task>
{task}
</task>"""


def _npc_block(game: GameState, target_id: str | None, context_text: str = "", move_category: str = "other") -> str:
    """Build context block for the target NPC, filtered by information gate level."""
    from .mechanics import compute_npc_gate, resolve_npc_stance

    target = find_npc(game, target_id) if target_id else None
    if not target:
        return ""

    stance = resolve_npc_stance(game, target, move_category)
    gate = compute_npc_gate(game, target, game.narrative.scene_count, stance.stance)
    log(f"[Gate] {target.name}: gate={gate} (stance={stance.stance})")

    aliases_attr = f' aliases="{_xa(",".join(target.aliases))}"' if target.aliases else ""

    # Gate 0: name + description only
    if gate == 0:
        return f'<target_npc name="{_xa(target.name)}" gate="0"{aliases_attr}>{_xe(target.description)}</target_npc>'

    # Gate 1+: add stance + constraint
    stance_attr = f' stance="{_xa(stance.stance)}" constraint="{_xa(stance.constraint)}"'

    # Gate 2+: add agenda + recent memories
    agenda_line = ""
    mem_str = ""
    gate_mem_counts = eng().npc.gate_memory_counts
    if gate >= 2:
        agenda_line = f"agenda:{_xe(target.agenda)}"
        mem_count = gate_mem_counts.get(gate, gate_mem_counts.get(min(gate, 4), 5))
        memories = retrieve_memories(
            target, context_text=context_text, max_count=mem_count, current_scene=game.narrative.scene_count
        )
        observations = [m for m in memories if m.type != "reflection"]
        if observations:
            obs_text = " | ".join(f"{m.event}({m.emotional_weight})" for m in observations)
            mem_str = f"\nrecent: {obs_text}"

    # Gate 3+: add instinct + arc + reflections
    instinct_line = ""
    arc_attr = ""
    if gate >= 3:
        instinct_line = f" instinct:{_xe(target.instinct)}"
        if target.arc.strip():
            arc_attr = f' arc="{_xa(target.arc)}"'
        mem_count_3 = gate_mem_counts.get(gate, gate_mem_counts.get(min(gate, 4), 5))
        memories = retrieve_memories(
            target, context_text=context_text, max_count=mem_count_3, current_scene=game.narrative.scene_count
        )
        reflections = [m for m in memories if m.type == "reflection"]
        observations = [m for m in memories if m.type != "reflection"]
        mem_parts = []
        if reflections:
            mem_parts.append(f"insight: {' | '.join(m.event for m in reflections)}")
        if observations:
            mem_parts.append(f"recent: {' | '.join(f'{m.event}({m.emotional_weight})' for m in observations)}")
        mem_str = "\n" + "\n".join(mem_parts) if mem_parts else ""

    # Gate 4: add secrets
    secrets_line = ""
    if gate >= 4 and target.secrets:
        secs = json.dumps(target.secrets, ensure_ascii=False)
        secrets_label = get_prompt("secrets_label")
        secrets_line = f"\nsecrets({secrets_label}):{_xe(secs)}"

    body = f"{agenda_line}{instinct_line}{mem_str}{secrets_line}" if gate >= 2 else _xe(target.description)

    return f'<target_npc name="{_xa(target.name)}"{stance_attr}{aliases_attr}{arc_attr} gate="{gate}">\n{body}\n</target_npc>'


def _activated_npcs_block(
    activated: Sequence[NpcData],
    target_id: str | None,
    game: GameState,
    context_text: str = "",
    move_category: str = "other",
) -> str:
    """Build context blocks for activated NPCs (not the target — those get _npc_block).
    Lighter context than target: name, stance, and 1-2 key memories."""
    from .mechanics import resolve_npc_stance

    parts = []
    for npc in activated:
        # Skip target NPC (handled by _npc_block)
        if target_id and (npc.id == target_id or npc.name.lower() == str(target_id).lower()):
            continue
        memories = retrieve_memories(
            npc,
            context_text=context_text,
            max_count=eng().npc.activated_memory_count,
            current_scene=game.narrative.scene_count,
        )
        mem_hint = ""
        if memories:
            pd = eng().prompt_display
            reflections = [m for m in memories if m.type == "reflection"]
            if reflections:
                mem_hint = f' insight="{_xa(reflections[0].event[: pd.insight_chars])}"'
            else:
                hint_text = f"{memories[0].event[: pd.recent_event_chars]}({memories[0].emotional_weight})"
                mem_hint = f' recent="{_xa(hint_text)}"'

        # Spatial hint: show last location if different from player's current location
        loc_hint = ""
        loc = _npc_location_hint(npc, game.world.current_location or "")
        if loc:
            loc_hint = f' last_seen="{_xa(loc)}"'

        arc_hint = f' arc="{_xa(npc.arc)}"' if npc.arc.strip() else ""
        stance = resolve_npc_stance(game, npc, move_category)
        parts.append(
            f'<activated_npc name="{_xa(npc.name)}" stance="{_xa(stance.stance)}" '
            f'constraint="{_xa(stance.constraint)}"{arc_hint}{mem_hint}{loc_hint}/>'
        )
    return "\n".join(parts)


def _known_npcs_string(mentioned: Sequence[NpcData], game: GameState, exclude_ids: set | None = None) -> str:
    """Build compact known-NPCs line for name-only mentions.
    Also includes remaining active/background NPCs not in activated or mentioned."""
    exclude_ids = exclude_ids or set()
    player_loc = game.world.current_location or ""
    parts = []

    def _npc_entry(n: NpcData) -> str:
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

    return ", ".join(parts) or eng().ai_text.narrator_defaults["no_npcs"]


def _pacing_block(game: GameState, scene_setup: SceneSetup | None = None) -> str:
    """Build pacing and scene modification block for prompts."""
    from .mechanics.scene import adjustment_descriptions

    parts = []
    pacing = get_pacing_hint(game)
    if pacing != "neutral":
        parts.append(f'<pacing type="{pacing}"/>')

    if scene_setup and scene_setup.scene_type == "altered":
        descs = adjustment_descriptions(scene_setup.adjustments)
        adj_text = "; ".join(descs)
        parts.append(f"<altered_scene>{adj_text}</altered_scene>")
    elif scene_setup and scene_setup.scene_type == "interrupt" and scene_setup.interrupt_event:
        ev = scene_setup.interrupt_event
        target_attr = f' target="{_xa(ev.target)}"' if ev.target else ""
        parts.append(
            f'<interrupt_scene focus="{_xa(ev.focus)}"{target_attr}>'
            f"{_xe(ev.meaning_action)} / {_xe(ev.meaning_subject)}"
            f"</interrupt_scene>"
        )

    return "\n".join(parts)


def _random_events_block(events: Sequence[RandomEvent]) -> str:
    """Build <random_event> tags for narrator prompt injection."""
    if not events:
        return ""
    parts = []
    for ev in events:
        target_attr = f' target="{_xa(ev.target)}"' if ev.target else ""
        parts.append(
            f'<random_event focus="{_xa(ev.focus)}"{target_attr}>'
            f"{_xe(ev.meaning_action)} / {_xe(ev.meaning_subject)}"
            f"</random_event>"
        )
    return "\n".join(parts)


def _lore_figures_block(game: GameState) -> str:
    """Build a slim context block for lore figures — named persons who are narratively
    significant but never physically present."""
    lore = [n for n in game.npcs if n.status == "lore"]
    if not lore:
        return ""
    parts = []
    pd = eng().prompt_display
    for n in lore:
        entry = _xe(n.name)
        if n.description:
            entry += f": {_xe(n.description[: pd.lore_description_chars])}"
        if n.aliases:
            entry += f" (aka {_xe(', '.join(n.aliases[: pd.lore_max_aliases]))})"
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
    activated_npcs: Sequence[NpcData] = (),
    mentioned_npcs: Sequence[NpcData] = (),
    move_category: str = "other",
) -> str:
    """Build the three-tier NPC section used by both dialog and action prompts."""
    target_id = brain.target_npc
    activated_block = _activated_npcs_block(activated_npcs, target_id, game, context_text, move_category)
    exclude_ids = {n.id for n in activated_npcs}
    if target_id:
        t = find_npc(game, target_id)
        if t:
            exclude_ids.add(t.id)
    known_str = _known_npcs_string(mentioned_npcs, game, exclude_ids)
    section = ""
    if activated_block:
        section += f"\n{activated_block}"
    section += f"\n<known_npcs>{known_str}</known_npcs>"
    section += _lore_figures_block(game)
    return section


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
    scene_setup: SceneSetup | None = None,
    activated_npcs: Sequence[NpcData] = (),
    mentioned_npcs: Sequence[NpcData] = (),
    config: EngineConfig | None = None,
    oracle_answer: str = "",
    random_events: Sequence[RandomEvent] = (),
) -> str:
    context_text = f"{player_words} {brain.player_intent or ''} {game.world.current_scene_context or ''}"
    move_cat = "social"  # Dialog is always social context
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=move_cat)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs, move_category=move_cat)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    crisis = "\n<crisis/>" if game.crisis_mode else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    director = _director_block(game)
    oracle_tag = f"\n<oracle_answer>{_xe(oracle_answer)}</oracle_answer>" if oracle_answer else ""

    scene_type = "oracle" if oracle_answer else "dialog"
    task = get_prompt("task_oracle") if oracle_answer else get_prompt("task_dialog")

    return f"""<scene type="{scene_type}" n="{game.narrative.scene_count}">
{_scene_header(game)}
<intent>{_xe(brain.player_intent)}</intent>{pw}{oracle_tag}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}{_scene_enrichment(game)}
{npc}{npcs_sect}{wl}{crisis}
{pacing}
{events_block}{director}
{narrative_direction_block(game, "dialog")}
{story_context_block(game)}{recent_events_block(game)}</scene>
<task>{task}</task>"""


def build_action_prompt(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    consequences: list[str],
    clock_events: list,
    npc_agency: list[str],
    *,
    consequence_sentences: Sequence[str],
    player_words: str = "",
    scene_setup: SceneSetup | None = None,
    activated_npcs: Sequence[NpcData] = (),
    mentioned_npcs: Sequence[NpcData] = (),
    config: EngineConfig | None = None,
    position: str = "risky",
    effect: str = "standard",
    random_events: Sequence[RandomEvent] = (),
    threat_events: Sequence[ThreatEvent] = (),
) -> str:
    context_text = f"{player_words} {brain.player_intent or ''} {game.world.current_scene_context or ''}"
    from .mechanics import move_category

    move_cat = move_category(brain.move)
    # Map engine categories to stance matrix categories
    stance_cat = {"combat": "combat", "social": "social"}.get(move_cat, "other")
    if brain.move == "adventure/gather_information":
        stance_cat = "gather_information"
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=stance_cat)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs, move_category=stance_cat)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""

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
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    director = _director_block(game)

    cons_tags = "\n".join(f"<consequence>{_xe(s)}</consequence>" for s in consequence_sentences)
    if cons_tags:
        cons_tags = f"\n{cons_tags}"

    threat_tag_parts = []
    for te in threat_events:
        if te.source == "forsake_vow":
            threat_tag_parts.append(f'<vow_forsaken threat="{_xa(te.threat_name)}"/>')
        elif te.source == "overcome_under_pressure":
            threat_tag_parts.append(f'<threat_overcome name="{_xa(te.threat_name)}"/>')
        else:
            threat_tag_parts.append(f'<threat_advance name="{_xa(te.threat_name)}" menace_full="{te.menace_full}"/>')
    threat_tags = "\n".join(threat_tag_parts)
    if threat_tags:
        threat_tags = f"\n{threat_tags}"

    return f"""<scene type="action" n="{game.narrative.scene_count}">
{_scene_header(game)}
<intent>{_xe(brain.player_intent)} ({_xe(brain.approach)})</intent>{pw}
{constraint}{cons_tags}{threat_tags}
{position_tag}
<location>{_xe(game.world.current_location)}</location>{_loc_hist(game)}{_time_ctx(game)}{_scene_enrichment(game)}
{npc}{npcs_sect}{wl}{flags}{agency}
{pacing}
{events_block}{director}
{narrative_direction_block(game, roll.result)}
{story_context_block(game)}{recent_events_block(game)}</scene>
<task>{get_prompt("task_action")}</task>"""


# ── Chapter / epilogue prompts ───────────────────────────────


def build_epilogue_prompt(game: GameState) -> str:
    """Build prompt for generating an epilogue that wraps up the story."""
    from .prompt_blocks import campaign_history_block

    bp = game.narrative.story_blueprint
    endings = bp.possible_endings if bp else []
    endings_text = ", ".join(f"{e.type}: {e.description}" for e in endings) if endings else "open"
    conflict = bp.central_conflict if bp else ""

    npc_block = "\n".join(
        f'<npc name="{_xa(n.name)}" disposition="{_xa(n.disposition)}" bond="{get_npc_bond(game, n.id)}/10">'
        f"{_xe(n.description)}</npc>"
        for n in game.npcs
        if n.status == "active"
    )

    epilogue_scenes = eng().prompt_display.epilogue_log_scenes
    log_text = "; ".join(
        f"S{s.scene}:{_xe(s.rich_summary or s.summary)}({s.result})"
        for s in game.narrative.session_log[-epilogue_scenes:]
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
{get_prompt("task_epilogue")}
</task>"""


def build_new_chapter_prompt(game: GameState) -> str:
    """Build opening prompt for a new chapter in an ongoing campaign."""
    from .prompt_blocks import campaign_history_block

    npc_block = "\n".join(
        f'<returning_npc id="{_xa(n.id)}" name="{_xa(n.name)}" disposition="{_xa(n.disposition)}" '
        f'bond="{get_npc_bond(game, n.id)}/10"'
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
{get_prompt("task_chapter_opening", chapter_number=str(game.campaign.chapter_number), seed=seed)}
</task>"""
