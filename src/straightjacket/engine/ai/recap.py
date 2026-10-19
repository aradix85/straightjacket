from ..config_loader import model_for_role, narration_language, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from ..prompt_blocks import (
    content_boundaries_block,
)
from ..prompt_loader import get_prompt
from ..ruleset.bond import get_npc_bond
from ..story_state import get_current_act
from .provider_base import AICallSpec, AIProvider, create_with_retry


def call_recap(provider: AIProvider, game: GameState) -> str:
    lang = narration_language()
    _defaults = eng().ai_text.narrator_defaults
    _limits = eng().recap_limits
    log_text = "; ".join(
        get_prompt("block_session_log_entry", scene=str(s.scene), summary=s.rich_summary or s.summary, result=s.result)
        for s in game.narrative.session_log[-_limits.recap_log_window :]
    )

    npc_text = (
        ", ".join(
            get_prompt("recap_npc", npc=n.name, disposition=n.disposition, bond=str(get_npc_bond(game, n.id)))
            for n in game.npcs
            if n.status == "active" and n.introduced
        )
        or _defaults["no_npcs"]
    )

    recent_narrations = get_prompt("recap_narration_separator").join(
        entry.narration[: _limits.recap_narration_truncate]
        for entry in game.narrative.narration_history[-_limits.recap_narration_window :]
    )

    arc_info = ""
    if game.narrative.story_blueprint is not None:
        act = get_current_act(game)
        arc_info = "\n" + get_prompt(
            "recap_story_arc",
            structure=game.narrative.story_blueprint.structure_type,
            act_number=str(act.act_number),
            total_acts=str(act.total_acts),
            phase=act.phase,
            progress=act.progress,
        )

    campaign_info = ""
    if game.campaign.campaign_history:
        campaign_info = "\n" + get_prompt(
            "recap_campaign",
            chapter=str(game.campaign.chapter_number),
            chapters=str(len(game.campaign.campaign_history) + 1),
        )
        for ch in game.campaign.campaign_history[-_limits.recap_campaign_history_window :]:
            summary = ch.summary[: _limits.recap_campaign_summary_truncate]
            campaign_info += "\n" + get_prompt("recap_campaign_previous", title=ch.title, summary=summary)

    request = get_prompt(
        "recap_request",
        player=game.player_name,
        concept=game.character_concept,
        genre=game.setting_genre,
        tone=game.setting_tone,
        world=game.setting_description,
        location=game.world.current_location,
        log=log_text,
        npcs=npc_text,
        arc=arc_info,
        campaign=campaign_info,
        situation=game.world.current_scene_context,
        narrations=recent_narrations,
    )
    spec = AICallSpec(
        model=model_for_role("recap"),
        system=get_prompt("recap", lang=lang, content_boundaries_block=content_boundaries_block(game)),
        messages=[{"role": "user", "content": request}],
        log_role="recap",
        **sampling_params("recap"),
    )
    try:
        return create_with_retry(provider, spec).content
    except Exception as e:
        log(f"[Recap] Failed: {e}", level="warning")
        result: str = _defaults["recap_fallback"].format(player_name=game.player_name)
        return result
