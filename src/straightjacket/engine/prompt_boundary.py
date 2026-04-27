from .engine_loader import eng
from .logging_util import log
from .models import GameState
from .npc import get_npc_bond
from .prompt_blocks import campaign_history_block, story_context_block
from .prompt_loader import get_prompt
from .prompt_shared import creativity_seed, _loc_hist, _scene_header, _time_ctx
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def build_new_game_prompt(game: GameState) -> str:
    crisis = "\n" + get_prompt("block_crisis") if game.crisis_mode else ""
    story = story_context_block(game)
    seed = creativity_seed()
    log(f"[Narrator] Opening creativity_seed={seed!r}")

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


def build_epilogue_prompt(game: GameState) -> str:
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
        bg_prefix = get_prompt("block_background_npcs_prefix")
        npc_block += f"\n<background_npcs>{bg_prefix}{bg_names}</background_npcs>"

    evolutions_block = ""
    if game.campaign.campaign_history:
        last_ch = game.campaign.campaign_history[-1]
        evolutions = last_ch.npc_evolutions
        if evolutions:
            evo_lines = "\n".join(
                f"  {_xe(e.name)}: {_xe(e.projection)}" for e in evolutions if e.name and e.projection
            )
            evo_hint = get_prompt("block_npc_evolutions_hint")
            evolutions_block = f'\n<npc_evolutions hint="{_xa(evo_hint)}">\n{evo_lines}\n</npc_evolutions>'

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
