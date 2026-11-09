from collections.abc import Sequence

from straightjacket.engine.models import (
    BrainResult,
    GameState,
    ResolvedFact,
)
from straightjacket.engine.prompt_blocks import narrative_direction_block
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
from straightjacket.engine.xml_utils import xe as _xe


def build_dialog_prompt(
    game: GameState,
    brain: BrainResult,
    scene: PromptScene,
    events: TurnEvents,
    *,
    result: str,
    oracle_answer: str,
    consequence_texts: Sequence[str],
    facts: Sequence[ResolvedFact],
) -> str:
    context_text = f"{scene.player_words} {brain.player_intent} {game.world.current_scene_context}"
    is_move = result == "unrolled_move"
    move_cat = _resolve_stance_category(brain.move) if is_move else "social"
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=move_cat)
    npcs_sect = _npcs_section(game, brain, context_text, scene, move_category=move_cat)
    oracle_tag = "\n" + get_prompt("block_oracle_answer", answer=_xe(oracle_answer)) if oracle_answer else ""

    if is_move:
        task = get_prompt("task_unrolled_move")
    elif result == "dialog":
        task = get_prompt("task_dialog")
    elif oracle_answer:
        task = get_prompt("task_oracle")
    else:
        task = get_prompt("task_oracle_facts")

    return get_prompt(
        "block_scene_dialog",
        **_scene_fields(game, brain, scene, events),
        scene_type=result,
        oracle=oracle_tag,
        consequences=_consequence_tags(consequence_texts),
        facts=_facts_block(facts),
        npc=npc,
        npcs=npcs_sect,
        director=_director_block(game),
        direction=narrative_direction_block(game, result if is_move else "dialog"),
        task=task,
    )
