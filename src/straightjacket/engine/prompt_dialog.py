from collections.abc import Sequence

from .mechanics.scene import SceneSetup
from .models import BrainResult, FateResult, GameState, NpcData, RandomEvent
from .prompt_blocks import narrative_direction_block, recent_events_block, story_context_block
from .prompt_loader import get_prompt
from .prompt_shared import (
    _director_block,
    _fate_answer_block,
    _loc_hist,
    _npc_block,
    _npcs_section,
    _pacing_block,
    _random_events_block,
    _scene_enrichment,
    _scene_header,
    _time_ctx,
)
from .xml_utils import xe as _xe


def build_dialog_prompt(
    game: GameState,
    brain: BrainResult,
    player_words: str = "",
    scene_setup: SceneSetup | None = None,
    activated_npcs: Sequence[NpcData] = (),
    mentioned_npcs: Sequence[NpcData] = (),
    oracle_answer: str = "",
    random_events: Sequence[RandomEvent] = (),
    fate_result: FateResult | None = None,
) -> str:
    context_text = f"{player_words} {brain.player_intent} {game.world.current_scene_context}"
    move_cat = "social"
    npc = _npc_block(game, brain.target_npc, context_text=context_text, move_category=move_cat)
    npcs_sect = _npcs_section(game, brain, context_text, activated_npcs, mentioned_npcs, move_category=move_cat)

    wa = brain.world_addition
    wl = f"\n<world_add>{_xe(wa)}</world_add>" if wa else ""
    crisis = "\n<crisis/>" if game.crisis_mode else ""
    pw = f"\n<player_words>{_xe(player_words)}</player_words>" if player_words else ""
    pacing = _pacing_block(game, scene_setup)
    events_block = _random_events_block(random_events)
    fate_block = _fate_answer_block(fate_result)
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
{events_block}{fate_block}{director}
{narrative_direction_block(game, "dialog")}
{story_context_block(game)}{recent_events_block(game)}</scene>
<task>{task}</task>"""
