from collections.abc import Sequence

from .gamemaster.questions import answers
from .models import (
    BrainResult,
    ClockFillResult,
    Consequence,
    GameState,
    NpcData,
    RandomEvent,
    ResolvedFact,
    Revelation,
    RollResult,
    SceneSetup,
    ThreatEvent,
    labels_of,
)
from .prompt_blocks import narrative_direction_block, recent_events_block, story_context_block, task_action
from .prompt_loader import get_prompt
from .prompt_shared import (
    _clock_filled_block,
    _consequence_tags,
    _director_block,
    _facts_block,
    _flags_block,
    _generated_place_block,
    _loc_hist,
    _npc_agency_block,
    _npc_block,
    _npcs_section,
    _pacing_block,
    _player_words_tag,
    _random_events_block,
    _resolve_stance_category,
    _revelation_tag,
    _scene_enrichment,
    _scene_header,
    _threat_events_block,
    _time_ctx,
    _world_add_tag,
)
from .ruleset.moves import get_moves, outcome_text
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe

_RESULT_PROMPTS = {
    "success": ("result_success_body", "result_match_hint_success"),
    "partial": ("result_partial_body", "result_match_hint_partial"),
    "failure": ("result_failure_body", "result_match_hint_failure"),
}


def _build_result_constraint(roll: RollResult, outcome: str, consequences: list[Consequence]) -> str:
    body, hint = _RESULT_PROMPTS[outcome]
    cons_attr = (
        get_prompt("block_result_consequences_attr", consequences=_xa(",".join(labels_of(consequences))))
        if consequences
        else ""
    )
    return get_prompt(
        "block_result",
        result=roll.result,
        match=get_prompt("block_result_match_attr") if roll.match else "",
        consequences=cons_attr,
        body=get_prompt(body),
        hint=get_prompt(hint) if roll.match else "",
    )


def _move_outcome_block(game: GameState, brain: BrainResult, roll: RollResult) -> str:
    text = outcome_text(game.setting_id, brain.move, roll.result)
    if not text:
        return ""
    name = get_moves(game.setting_id)[brain.move].name
    return "\n" + get_prompt("block_move_outcome", move=_xa(name), text=_xe(text))


def build_action_prompt(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    consequences: list[Consequence],
    npc_agency: list[str],
    *,
    consequence_sentences: Sequence[str],
    player_words: str,
    scene_setup: SceneSetup,
    activated_npcs: Sequence[NpcData],
    mentioned_npcs: Sequence[NpcData],
    position: str,
    effect: str,
    random_events: Sequence[RandomEvent],
    threat_events: Sequence[ThreatEvent],
    clock_fill_results: Sequence[ClockFillResult],
    facts: Sequence[ResolvedFact],
    revelation: Revelation | None,
) -> str:
    context_text = f"{player_words} {brain.player_intent} {game.world.current_scene_context}"

    outcome = answers().outcome(roll.result)
    miss = outcome == "failure"
    stance_cat = _resolve_stance_category(brain.move)
    npc = _npc_block(
        game, brain.target_npc, context_text=context_text, move_category=stance_cat, miss=miss, hit=not miss
    )
    npcs_sect = _npcs_section(
        game, brain, context_text, activated_npcs, mentioned_npcs, move_category=stance_cat, miss=miss
    )

    constraint = _build_result_constraint(roll, outcome, consequences) + _move_outcome_block(game, brain, roll)
    position_tag = get_prompt("block_position", level=_xa(position), effect=_xa(effect))

    flags = _flags_block(game)
    agency = _npc_agency_block(npc_agency)
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    clock_block = _clock_filled_block(clock_fill_results)
    director = "" if miss else _director_block(game)
    threat_tags = _threat_events_block(threat_events)

    return get_prompt(
        "block_scene_action",
        n=str(game.narrative.scene_count),
        header=_scene_header(game),
        intent=_xe(brain.player_intent),
        approach=_xe(brain.approach),
        player_words=_player_words_tag(player_words),
        result=constraint,
        consequences=_consequence_tags(consequence_sentences),
        revelation=_revelation_tag(revelation),
        threats=threat_tags,
        clocks=f"\n{clock_block}" if clock_block else "",
        facts=_facts_block(facts),
        position=position_tag,
        location=_xe(game.world.current_location),
        generated=_generated_place_block(game),
        previous_locations=_loc_hist(game),
        time=_time_ctx(game),
        thread=_scene_enrichment(game),
        npc=npc,
        npcs=npcs_sect,
        world_add=_world_add_tag(brain.world_addition),
        flags=flags,
        agency=agency,
        pacing=pacing,
        events=events_block,
        director=director,
        direction=narrative_direction_block(game, outcome),
        story=story_context_block(game),
        recent=recent_events_block(game),
        task=task_action(),
    )
