import json
import random
from collections.abc import Sequence

from .engine_loader import eng
from .logging_util import log
from .mechanics import (
    compute_npc_gate,
    get_pacing_hint,
    locations_match,
    move_category,
    resolve_npc_stance,
)
from .mechanics.impacts import impact_label
from .mechanics.scene import SceneSetup, adjustment_descriptions
from .models import BrainResult, GameState, NpcData, RandomEvent
from .npc import find_npc, retrieve_memories
from .prompt_loader import get_prompt
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def creativity_seed(n: int = 3, rng: random.Random | None = None) -> str:
    words = list(eng().creativity_seeds)
    _rng = rng or random
    return " ".join(_rng.sample(words, min(n, len(words))))


def _scene_header(game: GameState) -> str:
    impacts_tag = ""
    if game.impacts:
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
    threads = [t for t in game.narrative.threads if t.active]
    if not threads:
        return ""
    threads.sort(key=lambda t: t.weight, reverse=True)
    return f"\n<active_thread>{_xe(threads[0].name)}</active_thread>"


def _format_memories(
    target: NpcData, context_text: str, gate: int, current_scene: int, include_reflections: bool
) -> str:
    gate_mem_counts = eng().npc.gate_memory_counts
    mem_count = gate_mem_counts[gate]
    memories = retrieve_memories(target, context_text=context_text, max_count=mem_count, current_scene=current_scene)
    observations = [m for m in memories if m.type != "reflection"]

    if not include_reflections:
        if observations:
            obs_text = " | ".join(f"{m.event}({m.emotional_weight})" for m in observations)
            return f"\nrecent: {obs_text}"
        return ""

    reflections = [m for m in memories if m.type == "reflection"]
    parts: list[str] = []
    if reflections:
        parts.append(f"insight: {' | '.join(m.event for m in reflections)}")
    if observations:
        parts.append(f"recent: {' | '.join(f'{m.event}({m.emotional_weight})' for m in observations)}")
    return "\n" + "\n".join(parts) if parts else ""


def _build_gate0_target(target: NpcData, aliases_attr: str) -> str:
    return f'<target_npc name="{_xa(target.name)}" gate="0"{aliases_attr}>{_xe(target.description)}</target_npc>'


def _npc_block(game: GameState, target_id: str | None, context_text: str = "", move_category: str = "other") -> str:
    target = find_npc(game, target_id) if target_id else None
    if not target:
        return ""

    stance = resolve_npc_stance(game, target, move_category)
    gate = compute_npc_gate(game, target, game.narrative.scene_count, stance.stance)
    fact_budget = eng().information_gate.fact_budget_by_gate[gate]
    log(f"[Gate] {target.name}: gate={gate} (stance={stance.stance}) fact_budget={fact_budget}")

    aliases_attr = f' aliases="{_xa(",".join(target.aliases))}"' if target.aliases else ""

    if gate == 0:
        return _build_gate0_target(target, aliases_attr)

    stance_attr = f' stance="{_xa(stance.stance)}" constraint="{_xa(stance.constraint)}"'
    fact_budget_attr = f' fact_budget="{fact_budget}"'

    agenda_line = ""
    mem_str = ""
    if gate >= 2:
        agenda_line = f"agenda:{_xe(target.agenda)}"
        mem_str = _format_memories(target, context_text, gate, game.narrative.scene_count, include_reflections=False)

    instinct_line = ""
    arc_attr = ""
    if gate >= 3:
        instinct_line = f" instinct:{_xe(target.instinct)}"
        if target.arc.strip():
            arc_attr = f' arc="{_xa(target.arc)}"'
        mem_str = _format_memories(target, context_text, gate, game.narrative.scene_count, include_reflections=True)

    secrets_line = ""
    if gate >= 4 and target.secrets:
        secs = json.dumps(target.secrets, ensure_ascii=False)
        secrets_label = get_prompt("secrets_label")
        secrets_line = f"\nsecrets({secrets_label}):{_xe(secs)}"

    body = f"{agenda_line}{instinct_line}{mem_str}{secrets_line}" if gate >= 2 else _xe(target.description)

    return f'<target_npc name="{_xa(target.name)}"{stance_attr}{aliases_attr}{arc_attr}{fact_budget_attr} gate="{gate}">\n{body}\n</target_npc>'


def _activated_npcs_block(
    activated: Sequence[NpcData],
    target_id: str | None,
    game: GameState,
    context_text: str = "",
    move_category: str = "other",
) -> str:
    parts = []
    for npc in activated:
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

    for n in mentioned:
        if n.id in exclude_ids:
            continue
        parts.append(_npc_entry(n))
        exclude_ids.add(n.id)

    for n in game.npcs:
        if n.id in exclude_ids:
            continue
        if n.status not in ("active", "background"):
            continue
        parts.append(_npc_entry(n))

    return ", ".join(parts) or eng().ai_text.narrator_defaults["no_npcs"]


def _pacing_block(game: GameState, scene_setup: SceneSetup | None = None) -> str:
    parts = []
    pacing = get_pacing_hint(game)
    if pacing != "neutral":
        parts.append(f'<pacing type="{pacing}"/>')

    if scene_setup and scene_setup.scene_type == "keyed":
        wrapper = eng().keyed_scenes.prompt_wrapper
        parts.append(wrapper.format(hint=_xe(scene_setup.narrative_hint)))
    elif scene_setup and scene_setup.scene_type == "altered":
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
    dg = game.narrative.director_guidance
    if not dg or not dg.narrator_guidance:
        return ""
    block = f"\n<director_guidance>{_xe(dg.narrator_guidance)}</director_guidance>"
    for npc_id, guidance in dg.npc_guidance.items():
        block += f'\n<npc_note for="{_xa(npc_id)}">{_xe(guidance)}</npc_note>'
    return block


def _resolve_stance_category(move: str) -> str:
    move_cat = move_category(move)
    return eng().stance_move_buckets.mapping[move_cat]
