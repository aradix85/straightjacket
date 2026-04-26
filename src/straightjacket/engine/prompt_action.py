"""Action-turn narrator prompt builder.

Assembles the XML prompt for an action scene: scene header, brain intent,
result constraint, position/effect, NPC blocks, pacing, random events,
director guidance, narrative direction, story context, recent events.

The result constraint tag encodes the roll result (MISS/WEAK_HIT/STRONG_HIT)
plus consequences, clock triggers, and match-twist hints. This is the
single strongest signal the narrator receives about what must happen
in the scene.
"""

from collections.abc import Sequence

from .mechanics.scene import SceneSetup
from .models import BrainResult, GameState, NpcData, RandomEvent, RollResult, ThreatEvent
from .prompt_blocks import narrative_direction_block, recent_events_block, story_context_block
from .prompt_loader import get_prompt
from .prompt_shared import (
    _director_block,
    _loc_hist,
    _npc_block,
    _npcs_section,
    _pacing_block,
    _random_events_block,
    _resolve_stance_category,
    _scene_enrichment,
    _scene_header,
    _time_ctx,
)
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def _build_status_flags(game: GameState) -> list[str]:
    """Collect narrator-facing status flags: resource exhaustion, crisis, final scene."""
    flags: list[str] = []
    if game.resources.health <= 0:
        flags.append(get_prompt("flag_wounded"))
    if game.resources.spirit <= 0:
        flags.append(get_prompt("flag_broken"))
    if game.resources.supply <= 0:
        flags.append(get_prompt("flag_depleted"))
    if game.game_over:
        flags.append(get_prompt("flag_final_scene"))
    elif game.crisis_mode:
        flags.append(get_prompt("flag_crisis"))
    return flags


def _build_threat_event_tags(threat_events: Sequence[ThreatEvent]) -> str:
    """Build the XML tag block for threat events: vow_forsaken, threat_overcome,
    or generic threat_advance. Returns empty string if no events.
    """
    parts: list[str] = []
    for te in threat_events:
        if te.source == "forsake_vow":
            parts.append(f'<vow_forsaken threat="{_xa(te.threat_name)}"/>')
        elif te.source == "overcome_under_pressure":
            parts.append(f'<threat_overcome name="{_xa(te.threat_name)}"/>')
        else:
            parts.append(f'<threat_advance name="{_xa(te.threat_name)}" menace_full="{te.menace_full}"/>')
    return "\n" + "\n".join(parts) if parts else ""


def _build_result_constraint(roll: RollResult, consequences: list[str], clock_events: list) -> str:
    """Build the <r> XML tag with outcome-specific constraint text and
    optional match-twist hint. MISS includes clock-triggered attributes;
    WEAK_HIT and STRONG_HIT include consequences when non-empty.
    """
    match_tag = ' match="true"' if roll.match else ""
    cons_attr = f' consequences="{_xa(",".join(consequences))}"' if consequences else ""

    if roll.result == "MISS":
        clk = "".join(f' clock_triggered="{_xa(e.clock)}:{_xa(e.trigger)}"' for e in clock_events)
        match_hint = get_prompt("result_match_hint_miss") if roll.match else ""
        body = get_prompt("result_miss_body")
        return (
            f'<result type="MISS"{match_tag} consequences="{_xa(",".join(consequences))}"{clk}>{body}{match_hint}</r>'
        )

    if roll.result == "WEAK_HIT":
        match_hint = get_prompt("result_match_hint_weak_hit") if roll.match else ""
        body = get_prompt("result_weak_hit_body")
        return f'<result type="WEAK_HIT"{match_tag}{cons_attr}>{body}{match_hint}</r>'

    match_hint = get_prompt("result_match_hint_strong_hit") if roll.match else ""
    body = get_prompt("result_strong_hit_body")
    return f'<result type="STRONG_HIT"{match_tag}{cons_attr}>{body}{match_hint}</r>'


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
    position: str = "risky",
    effect: str = "standard",
    random_events: Sequence[RandomEvent] = (),
    threat_events: Sequence[ThreatEvent] = (),
) -> str:
    context_text = f"{player_words} {brain.player_intent or ''} {game.world.current_scene_context or ''}"

    stance_cat = _resolve_stance_category(brain.move)
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=stance_cat)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs, move_category=stance_cat)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""

    constraint = _build_result_constraint(roll, consequences, clock_events)
    position_tag = f'<position level="{_xa(position)}" effect="{_xa(effect)}"/>'

    status_flags = _build_status_flags(game)
    flags = f"\n<flags>{','.join(status_flags)}</flags>" if status_flags else ""
    agency = f"\n<npc_agency>{_xe('| '.join(npc_agency))}</npc_agency>" if npc_agency else ""
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    director = _director_block(game)

    cons_tags = "\n".join(f"<consequence>{_xe(s)}</consequence>" for s in consequence_sentences)
    if cons_tags:
        cons_tags = f"\n{cons_tags}"

    threat_tags = _build_threat_event_tags(threat_events)

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
<task>{get_prompt("task_action", role="narrator")}</task>"""
