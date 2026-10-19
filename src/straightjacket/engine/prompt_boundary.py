from .engine_loader import eng
from .logging_util import log
from .models import GameState
from .prompt_blocks import campaign_history_block, story_context_block
from .prompt_loader import get_prompt
from .prompt_shared import _loc_hist, _scene_header, _time_ctx, creativity_seed
from .ruleset.bond import get_npc_bond
from .ruleset.config import rules
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def build_new_game_prompt(game: GameState) -> str:
    crisis = "\n" + get_prompt("block_crisis") if game.crisis_mode else ""
    story = story_context_block(game)
    seed = creativity_seed()
    log(f"[Narrator] Opening creativity_seed={seed!r}")

    pronouns_tag = "\n" + get_prompt("block_pronouns", pronouns=_xe(game.pronouns)) if game.pronouns else ""
    paths_tag = "\n" + get_prompt("block_paths", paths=_xe(", ".join(game.paths))) if game.paths else ""
    vow_tag = "\n" + get_prompt("block_vow", vow=_xe(game.background_vow)) if game.background_vow else ""

    pronouns_hint = get_prompt("opening_pronouns_hint", pronouns=game.pronouns) if game.pronouns else ""
    task = get_prompt(
        "task_opening",
        player_name=game.player_name,
        pronouns_hint=pronouns_hint,
        seed=seed,
    )

    return get_prompt(
        "block_scene_opening",
        header=_scene_header(game),
        pronouns=pronouns_tag,
        paths=paths_tag,
        vow=vow_tag,
        location=_xe(game.world.current_location),
        previous_locations=_loc_hist(game),
        time=_time_ctx(game),
        situation=_xe(game.world.current_scene_context),
        crisis=crisis,
        story=story,
        task=task,
    )


def build_epilogue_prompt(game: GameState) -> str:
    bp = game.narrative.story_blueprint
    if bp is None:
        raise ValueError("an epilogue ends the story of a blueprint, and this game has none")
    endings_text = ", ".join(
        get_prompt("block_epilogue_ending", type=e.type, description=e.description) for e in bp.possible_endings
    )

    npc_block = "\n".join(
        get_prompt(
            "block_epilogue_npc",
            npc=_xa(n.name),
            disposition=_xa(n.disposition),
            bond=str(get_npc_bond(game, n.id)),
            boxes=str(rules().progress.boxes),
            description=_xe(n.description),
        )
        for n in game.npcs
        if n.status == "active"
    )

    epilogue_scenes = eng().prompt_display.epilogue_log_scenes
    log_text = "; ".join(
        get_prompt(
            "block_session_log_entry",
            scene=str(s.scene),
            summary=_xe(s.rich_summary or s.summary),
            result=s.result,
        )
        for s in game.narrative.session_log[-epilogue_scenes:]
    )

    return get_prompt(
        "block_scene_epilogue",
        header=_scene_header(game),
        location=_xe(game.world.current_location),
        situation=_xe(game.world.current_scene_context),
        conflict=_xe(bp.central_conflict),
        endings=_xe(endings_text),
        npcs=npc_block,
        history=campaign_history_block(game),
        log=log_text,
        task=get_prompt("task_epilogue"),
    )


def build_new_chapter_prompt(game: GameState) -> str:
    npc_block = "\n".join(
        get_prompt(
            "block_returning_npc",
            id=_xa(n.id),
            npc=_xa(n.name),
            disposition=_xa(n.disposition),
            bond=str(get_npc_bond(game, n.id)),
            boxes=str(rules().progress.boxes),
            aliases=get_prompt("block_npc_aliases_attr", aliases=_xa(",".join(n.aliases))) if n.aliases else "",
            description=_xe(n.description),
        )
        for n in game.npcs
        if n.status == "active"
    )
    bg_npcs = [n for n in game.npcs if n.status == "background"]
    if bg_npcs:
        bg_parts = []
        for n in bg_npcs:
            entry = get_prompt("block_known_npc", npc=_xe(n.name), disposition=_xe(n.disposition))
            if n.aliases:
                entry += get_prompt("block_background_npc_aliases", aliases=_xe(",".join(n.aliases)))
            bg_parts.append(entry)
        npc_block += "\n" + get_prompt("block_background_npcs", npcs=", ".join(bg_parts))

    seed = creativity_seed()
    log(f"[Narrator] Chapter {game.campaign.chapter_number} opening creativity_seed={seed!r}")

    return get_prompt(
        "block_scene_chapter_opening",
        chapter=str(game.campaign.chapter_number),
        header=_scene_header(game),
        location=_xe(game.world.current_location),
        time=_time_ctx(game),
        situation=_xe(game.world.current_scene_context),
        history=campaign_history_block(game),
        npcs=npc_block,
        story=story_context_block(game),
        task=get_prompt("task_chapter_opening", chapter_number=str(game.campaign.chapter_number), seed=seed),
    )
