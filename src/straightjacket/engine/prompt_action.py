from collections.abc import Sequence

from straightjacket.engine.gamemaster.questions import answers
from straightjacket.engine.models import (
    BrainResult,
    Consequence,
    GameState,
    ResolvedFact,
    RollResult,
    labels_of,
)
from straightjacket.engine.prompt_blocks import narrative_direction_block, task_action
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.prompt_shared import (
    PromptScene,
    TurnEvents,
    _consequence_tags,
    _director_block,
    _facts_block,
    _npc_block,
    _npcs_section,
    _resolve_stance_category,
    _scene_fields,
)
from straightjacket.engine.ruleset.moves import get_moves, outcome_text
from straightjacket.engine.xml_utils import xa as _xa
from straightjacket.engine.xml_utils import xe as _xe

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
    scene: PromptScene,
    events: TurnEvents,
    *,
    consequences: list[Consequence],
    consequence_sentences: Sequence[str],
    position: str,
    effect: str,
    facts: Sequence[ResolvedFact],
) -> str:
    context_text = f"{scene.player_words} {brain.player_intent} {game.world.current_scene_context}"

    outcome = answers().outcome(roll.result)
    miss = outcome == "failure"
    stance_cat = _resolve_stance_category(brain.move)
    npc = _npc_block(
        game, brain.target_npc, context_text=context_text, move_category=stance_cat, miss=miss, hit=not miss
    )
    npcs_sect = _npcs_section(game, brain, context_text, scene, move_category=stance_cat, miss=miss)

    constraint = _build_result_constraint(roll, outcome, consequences) + _move_outcome_block(game, brain, roll)
    position_tag = get_prompt("block_position", level=_xa(position), effect=_xa(effect))

    return get_prompt(
        "block_scene_action",
        **_scene_fields(game, brain, scene, events),
        approach=_xe(brain.approach),
        result=constraint,
        consequences=_consequence_tags(consequence_sentences),
        facts=_facts_block(facts),
        position=position_tag,
        npc=npc,
        npcs=npcs_sect,
        director="" if miss else _director_block(game),
        direction=narrative_direction_block(game, outcome),
        task=task_action(),
    )
