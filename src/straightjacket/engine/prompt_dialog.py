from collections.abc import Sequence

from .gamemaster.moves import asks_the_oracle
from .models import (
    BrainResult,
    ClockFillResult,
    Consequence,
    GameState,
    NpcData,
    RandomEvent,
    ResolvedFact,
    Revelation,
    SceneSetup,
    ThreatEvent,
)
from .prompt_blocks import narrative_direction_block, recent_events_block, story_context_block
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
    _revelation_tag,
    _scene_enrichment,
    _scene_header,
    _threat_events_block,
    _time_ctx,
    _world_add_tag,
)
from .xml_utils import xe as _xe


def build_dialog_prompt(
    game: GameState,
    brain: BrainResult,
    *,
    player_words: str,
    scene_setup: SceneSetup,
    activated_npcs: Sequence[NpcData],
    mentioned_npcs: Sequence[NpcData],
    oracle_answer: str,
    random_events: Sequence[RandomEvent],
    threat_events: Sequence[ThreatEvent],
    consequences: Sequence[Consequence],
    clock_fill_results: Sequence[ClockFillResult],
    npc_agency: Sequence[str],
    facts: Sequence[ResolvedFact],
    revelation: Revelation | None,
) -> str:
    context_text = f"{player_words} {brain.player_intent} {game.world.current_scene_context}"
    move_cat = "social"
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=move_cat)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs, move_category=move_cat)
    agency = _npc_agency_block(npc_agency)

    flags = _flags_block(game)
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    clock_block = _clock_filled_block(clock_fill_results)
    director = _director_block(game)
    oracle_tag = "\n" + get_prompt("block_oracle_answer", answer=_xe(oracle_answer)) if oracle_answer else ""

    is_oracle = asks_the_oracle(brain.move)
    scene_type = "oracle" if is_oracle else "dialog"
    if not is_oracle:
        task = get_prompt("task_dialog")
    elif oracle_answer:
        task = get_prompt("task_oracle")
    else:
        task = get_prompt("task_oracle_facts")

    return get_prompt(
        "block_scene_dialog",
        scene_type=scene_type,
        n=str(game.narrative.scene_count),
        header=_scene_header(game),
        intent=_xe(brain.player_intent),
        player_words=_player_words_tag(player_words),
        oracle=oracle_tag,
        consequences=_consequence_tags(c.label for c in consequences),
        revelation=_revelation_tag(revelation),
        facts=_facts_block(facts),
        threats=_threat_events_block(threat_events),
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
        direction=narrative_direction_block(game, "dialog"),
        story=story_context_block(game),
        recent=recent_events_block(game),
        task=task,
    )
