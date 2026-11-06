from collections.abc import Sequence

from straightjacket.engine.models import (
    BrainResult,
    GameState,
    ResolvedFact,
)
from straightjacket.engine.prompt_blocks import narrative_direction_block, recent_events_block, story_context_block
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.prompt_shared import (
    PromptScene,
    TurnEvents,
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
    agency = _npc_agency_block(events.npc_agency)

    flags = _flags_block(game)
    pacing = _pacing_block(game, scene.scene_setup)
    events_block = _random_events_block(events.random_events)
    clock_block = _clock_filled_block(events.clock_fill_results)
    director = _director_block(game)
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
        scene_type=result,
        n=str(game.narrative.scene_count),
        header=_scene_header(game),
        intent=_xe(brain.player_intent),
        player_words=_player_words_tag(scene.player_words),
        oracle=oracle_tag,
        consequences=_consequence_tags(consequence_texts),
        revelation=_revelation_tag(events.revelation),
        facts=_facts_block(facts),
        threats=_threat_events_block(events.threat_events),
        clocks=f"\n{clock_block}" if clock_block else "",
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
        direction=narrative_direction_block(game, result if is_move else "dialog"),
        story=story_context_block(game),
        recent=recent_events_block(game),
        task=task,
    )
