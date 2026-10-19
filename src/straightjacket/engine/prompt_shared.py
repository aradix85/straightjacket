import json
import random
from collections.abc import Iterable, Sequence

from .engine_loader import eng
from .gamemaster.config import gm
from .gamemaster.generation import current_place
from .gamemaster.npc.matching import find_npc
from .gamemaster.npc.memory import retrieve_memories
from .gamemaster.pacing import get_pacing_hint
from .gamemaster.questions import answers
from .gamemaster.scene import adjustment_descriptions
from .gamemaster.stance_gate import compute_npc_gate, resolve_npc_stance
from .gamemaster.world import locations_match
from .logging_util import log
from .models import (
    BrainResult,
    ClockFillResult,
    GameState,
    MemoryEntry,
    NpcData,
    RandomEvent,
    ResolvedFact,
    SceneSetup,
    ThreatEvent,
)
from .prompt_blocks import character_tag, world_tag
from .prompt_loader import get_prompt
from .ruleset.impacts import get_impacts
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def creativity_seed() -> str:
    return " ".join(random.sample(eng().creativity_seeds, eng().prompt_display.creativity_seed_count))


def _impacts_block(game: GameState) -> str:
    if not game.impacts:
        return ""
    impacts = get_impacts(game.setting_id)
    lines = [
        get_prompt("block_impact_line", impact=_xa(impacts[k].label), description=_xe(impacts[k].description))
        for k in game.impacts
    ]
    labels = ", ".join(impacts[k].label for k in game.impacts)
    return "\n" + get_prompt("block_impacts_wrapper", labels=_xa(labels), lines="\n".join(lines))


def _scene_header(game: GameState) -> str:
    return f"{world_tag(game)}\n{character_tag(game)}{_impacts_block(game)}"


def _time_ctx(game: GameState) -> str:
    return "\n" + get_prompt("block_time", time=_xe(game.world.time_of_day)) if game.world.time_of_day else ""


def _generated_place_block(game: GameState) -> str:
    place = current_place(game)
    if place is None:
        return ""
    lines = [
        get_prompt("block_generated_line", role=_xa(role), value=_xe(value))
        for role, value in place.entity.results.items()
    ]
    return "\n" + get_prompt(
        "block_generated_wrapper",
        category=_xa(place.entity.category),
        place=_xa(place.name),
        lines="\n".join(lines),
    )


def _loc_hist(game: GameState) -> str:
    if not game.world.location_history:
        return ""
    n = gm().location.prompt_history_size
    return "\n" + get_prompt("block_prev_locations", locations=_xe(", ".join(game.world.location_history[-n:])))


def _scene_enrichment(game: GameState) -> str:
    threads = [t for t in game.narrative.threads if t.active]
    if not threads:
        return ""
    threads.sort(key=lambda t: t.weight, reverse=True)
    return "\n" + get_prompt("block_active_thread", thread=_xe(threads[0].name))


def _observed(memories: Sequence[MemoryEntry]) -> str:
    return " | ".join(get_prompt("block_npc_memory", event=m.event, weight=m.emotional_weight) for m in memories)


def _format_memories(
    target: NpcData, context_text: str, gate: int, current_scene: int, include_reflections: bool
) -> str:
    gate_mem_counts = gm().npc.gate_memory_counts
    mem_count = gate_mem_counts[gate]
    memories = retrieve_memories(target, context_text=context_text, max_count=mem_count, current_scene=current_scene)
    observations = [m for m in memories if m.type != "reflection"]

    if not include_reflections:
        if observations:
            return "\n" + get_prompt("block_npc_memories_recent", memories=_xe(_observed(observations)))
        return ""

    reflections = [m for m in memories if m.type == "reflection"]
    parts: list[str] = []
    if reflections:
        parts.append(get_prompt("block_npc_memories_insight", memories=_xe(" | ".join(m.event for m in reflections))))
    if observations:
        parts.append(get_prompt("block_npc_memories_recent", memories=_xe(_observed(observations))))
    return "\n" + "\n".join(parts) if parts else ""


def _npc_block(
    game: GameState,
    target_id: str | None,
    context_text: str,
    move_category: str,
    *,
    miss: bool = False,
    hit: bool = False,
) -> str:
    target = find_npc(game, target_id) if target_id else None
    if not target:
        return ""

    stance = resolve_npc_stance(game, target, move_category, miss=miss, hit=hit)
    gate = compute_npc_gate(game, target, game.narrative.scene_count, stance.stance)
    fact_budget = 0 if miss else gm().information_gate.fact_budget_by_gate[gate]
    log(f"[Gate] {target.name}: gate={gate} (stance={stance.stance}) fact_budget={fact_budget}")

    aliases_attr = get_prompt("block_npc_aliases_attr", aliases=_xa(",".join(target.aliases))) if target.aliases else ""

    if gate == 0:
        return get_prompt(
            "block_target_npc_stranger",
            npc=_xa(target.name),
            aliases=aliases_attr,
            description=_xe(target.description),
        )

    agenda_line = ""
    mem_str = ""
    if gate >= 2:
        agenda_line = get_prompt("block_target_npc_agenda", agenda=_xe(target.agenda))
        mem_str = _format_memories(target, context_text, gate, game.narrative.scene_count, include_reflections=False)

    instinct_line = ""
    arc_attr = ""
    if gate >= 3:
        instinct_line = get_prompt("block_target_npc_instinct", instinct=_xe(target.instinct))
        if target.arc.strip():
            arc_attr = get_prompt("block_npc_arc_attr", arc=_xa(target.arc))
        mem_str = _format_memories(target, context_text, gate, game.narrative.scene_count, include_reflections=True)

    secrets_line = ""
    if gate >= 4 and target.secrets:
        secs = json.dumps(target.secrets, ensure_ascii=False)
        secrets_line = "\n" + get_prompt(
            "block_target_npc_secrets", label=get_prompt("secrets_label"), secrets=_xe(secs)
        )

    if miss:
        body = f"{_xe(target.description)}{instinct_line}"
    elif gate >= 2:
        body = f"{agenda_line}{instinct_line}{mem_str}{secrets_line}"
    else:
        body = _xe(target.description)

    return get_prompt(
        "block_target_npc",
        npc=_xa(target.name),
        stance=get_prompt("block_target_npc_stance_attr", stance=_xa(stance.stance), constraint=_xa(stance.constraint)),
        aliases=aliases_attr,
        arc=arc_attr,
        fact_budget=get_prompt("block_target_npc_fact_budget_attr", budget=str(fact_budget)),
        gate=str(gate),
        body=body,
    )


def _activated_npcs_block(
    activated: Sequence[NpcData],
    target_id: str | None,
    game: GameState,
    context_text: str,
    move_category: str,
    *,
    miss: bool,
) -> str:
    parts = []
    for npc in activated:
        if npc.id == target_id:
            continue
        memories = retrieve_memories(
            npc,
            context_text=context_text,
            max_count=gm().npc.activated_memory_count,
            current_scene=game.narrative.scene_count,
        )
        mem_hint = ""
        if memories and not miss:
            pd = eng().prompt_display
            reflections = [m for m in memories if m.type == "reflection"]
            if reflections:
                insight = _xa(reflections[0].event[: pd.insight_chars])
                mem_hint = get_prompt("block_activated_npc_insight_attr", insight=insight)
            else:
                first = memories[0]
                recent = get_prompt(
                    "block_npc_memory", event=first.event[: pd.recent_event_chars], weight=first.emotional_weight
                )
                mem_hint = get_prompt("block_activated_npc_recent_attr", recent=_xa(recent))

        loc = _npc_location_hint(npc, game.world.current_location)
        loc_hint = get_prompt("block_activated_npc_last_seen_attr", location=_xa(loc)) if loc else ""
        arc_hint = get_prompt("block_npc_arc_attr", arc=_xa(npc.arc)) if npc.arc.strip() else ""
        stance = resolve_npc_stance(game, npc, move_category, miss=miss, hit=False)
        parts.append(
            get_prompt(
                "block_activated_npc",
                npc=_xa(npc.name),
                stance=_xa(stance.stance),
                constraint=_xa(stance.constraint),
                arc=arc_hint,
                memory=mem_hint,
                location=loc_hint,
            )
        )
    return "\n".join(parts)


def _known_npcs_string(mentioned: Sequence[NpcData], game: GameState, exclude_ids: set[str]) -> str:
    player_loc = game.world.current_location
    parts = []

    def _npc_entry(n: NpcData) -> str:
        entry = get_prompt("block_known_npc", npc=_xe(n.name), disposition=_xe(n.disposition))
        if n.status == "background":
            entry += get_prompt("block_known_npc_background")
        loc = _npc_location_hint(n, player_loc)
        if loc:
            entry += get_prompt("block_known_npc_at", location=_xe(loc))
        return entry

    for n in mentioned:
        if n.id in exclude_ids:
            continue
        parts.append(_npc_entry(n))
        exclude_ids.add(n.id)

    for n in game.npcs:
        if n.id in exclude_ids:
            continue
        if n.status not in gm().npc_status_groups.in_play:
            continue
        parts.append(_npc_entry(n))

    return ", ".join(parts) or eng().ai_text.narrator_defaults["no_npcs"]


def _pacing_block(game: GameState, scene_setup: SceneSetup) -> str:
    parts = []
    pacing = get_pacing_hint(game)
    if pacing != "neutral":
        parts.append(get_prompt("block_pacing", pacing=pacing))

    if scene_setup.scene_type == "keyed":
        wrapper = gm().keyed_scenes.prompt_wrapper
        parts.append(wrapper.format(hint=_xe(scene_setup.narrative_hint)))
    elif scene_setup.scene_type == "altered":
        descs = adjustment_descriptions(scene_setup.adjustments)
        parts.append(get_prompt("block_altered_scene", adjustments="; ".join(descs)))
    elif scene_setup.interrupt_event is not None:
        parts.append(_event_tag("block_interrupt_scene", scene_setup.interrupt_event))

    return "\n".join(parts)


def _event_tag(template: str, ev: RandomEvent) -> str:
    target = get_prompt("block_event_target_attr", target=_xa(ev.target)) if ev.target else ""
    return get_prompt(
        template,
        focus=_xa(ev.focus),
        target=target,
        action=_xe(ev.meaning_action),
        subject=_xe(ev.meaning_subject),
    )


def _random_events_block(events: Sequence[RandomEvent]) -> str:
    return "\n".join(_event_tag("block_random_event", ev) for ev in events)


def _player_words_tag(words: str) -> str:
    return "\n" + get_prompt("block_player_words", words=_xe(words)) if words else ""


def _world_add_tag(addition: str | None) -> str:
    return "\n" + get_prompt("block_world_add", addition=_xe(addition)) if addition else ""


def _consequence_tags(texts: Iterable[str]) -> str:
    return "".join("\n" + get_prompt("block_consequence", consequence=_xe(text)) for text in texts)


def _npc_agency_block(npc_agency: Sequence[str]) -> str:
    return "\n" + get_prompt("block_npc_agency", agency=_xe("| ".join(npc_agency))) if npc_agency else ""


def _flags_block(game: GameState) -> str:
    flags = [
        description.flag_at_zero
        for meter, description in eng().narrator_status_descriptions.items()
        if game.resources.meters[meter] <= 0
    ]
    if game.game_over:
        flags.append(get_prompt("flag_final_scene"))
    elif game.crisis_mode:
        flags.append(get_prompt("flag_crisis"))
    return "\n" + get_prompt("block_flags", flags=",".join(flags)) if flags else ""


def _threat_events_block(threat_events: Sequence[ThreatEvent]) -> str:
    parts: list[str] = []
    for te in threat_events:
        if te.source == "forsake_vow":
            parts.append(get_prompt("block_vow_forsaken", threat=_xa(te.threat_name)))
        elif te.source == "overcome_under_pressure":
            parts.append(get_prompt("block_threat_overcome", threat=_xa(te.threat_name)))
        else:
            body = _xe(te.development)
            parts.append(
                get_prompt(
                    "block_threat_advance" if body else "block_threat_advance_bare",
                    threat=_xa(te.threat_name),
                    menace_full=str(te.menace_full),
                    offscreen=get_prompt("block_threat_offscreen_attr") if te.source == "autonomous" else "",
                    development=body,
                )
            )
    return "\n" + "\n".join(parts) if parts else ""


def _clock_filled_block(fill_results: Sequence[ClockFillResult]) -> str:
    return "\n".join(
        get_prompt("block_clock_filled", clock=_xa(fr.clock_name), clock_type=_xa(fr.clock_type), text=_xe(fr.tag_text))
        for fr in fill_results
    )


def _facts_block(facts: Sequence[ResolvedFact]) -> str:
    if not facts:
        return ""
    types = gm().fact_resolution.types
    lines = [
        get_prompt(
            "block_fact_line",
            about=_xa(fact.about_name),
            answer=fact.answer,
            description=_xe(types[fact.fact_type].description),
        )
        for fact in facts
    ]
    return "\n" + get_prompt("block_facts_wrapper", lines="\n".join(lines))


def _lore_figures_block(game: GameState) -> str:
    lore = [n for n in game.npcs if n.status == "lore"]
    if not lore:
        return ""
    parts = []
    pd = eng().prompt_display
    for n in lore:
        entry = _xe(n.name)
        if n.description:
            description = _xe(n.description[: pd.lore_description_chars])
            entry += get_prompt("block_lore_figure_description", description=description)
        if n.aliases:
            entry += get_prompt("block_lore_figure_aliases", aliases=_xe(", ".join(n.aliases[: pd.lore_max_aliases])))
        parts.append(entry)
    return "\n" + get_prompt("block_lore_figures", figures="; ".join(parts))


def _npc_location_hint(npc: NpcData, player_loc: str) -> str:
    npc_loc = npc.last_location
    if npc_loc and player_loc and not locations_match(npc_loc, player_loc):
        return npc_loc
    return ""


def _npcs_section(
    game: GameState,
    brain: BrainResult,
    context_text: str,
    activated_npcs: Sequence[NpcData],
    mentioned_npcs: Sequence[NpcData],
    move_category: str,
    *,
    miss: bool = False,
) -> str:
    target_id = brain.target_npc
    activated_block = _activated_npcs_block(activated_npcs, target_id, game, context_text, move_category, miss=miss)
    exclude_ids = {n.id for n in activated_npcs}
    if target_id:
        exclude_ids.add(target_id)
    known_str = _known_npcs_string(mentioned_npcs, game, exclude_ids)
    section = ""
    if activated_block:
        section += f"\n{activated_block}"
    section += "\n" + get_prompt("block_known_npcs", npcs=known_str)
    section += _lore_figures_block(game)
    return section


def _director_block(game: GameState) -> str:
    dg = game.narrative.director_guidance
    if not dg.narrator_guidance:
        return ""
    block = "\n" + get_prompt("block_director_guidance", guidance=_xe(dg.narrator_guidance))
    for npc_id, guidance in dg.npc_guidance.items():
        npc = find_npc(game, npc_id)
        if npc is None:
            continue
        block += "\n" + get_prompt("block_npc_note", npc=_xa(npc.name), guidance=_xe(guidance))
    return block


def _resolve_stance_category(move: str) -> str:
    move_cat = answers().action_kind(move)
    return gm().stance_move_buckets.mapping[move_cat]
