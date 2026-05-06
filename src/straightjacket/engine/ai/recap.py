from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import EngineConfig, GameState
from ..npc import get_npc_bond
from ..prompt_blocks import (
    content_boundaries_block,
    get_narration_lang,
)
from ..prompt_loader import get_prompt
from ..story_state import get_current_act
from .provider_base import AICallSpec, AIProvider, create_with_retry


def call_recap(provider: AIProvider, game: GameState, config: EngineConfig | None = None) -> str:
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    _e = eng()
    _defaults = _e.ai_text.narrator_defaults
    _limits = _e.recap_limits
    log_text = "; ".join(
        f"S{s.scene}:{s.rich_summary or s.summary}({s.result})"
        for s in game.narrative.session_log[-_limits.recap_log_window :]
    )

    npc_text = (
        ", ".join(
            f"{n.name}({n.disposition},B{get_npc_bond(game, n.id)})"
            for n in game.npcs
            if n.status == "active" and n.introduced
        )
        or _defaults["no_npcs"]
    )

    recent_narrations = "\n---\n".join(
        entry.narration[: _limits.recap_narration_truncate]
        for entry in game.narrative.narration_history[-_limits.recap_narration_window :]
    )

    arc_info = ""
    if game.narrative.story_blueprint and game.narrative.story_blueprint.acts:
        act = get_current_act(game)
        structure = game.narrative.story_blueprint.structure_type
        arc_info = (
            f"\nstory_arc({structure}): act={act.act_number}/{act.total_acts} phase={act.phase} progress={act.progress}"
        )

    campaign_info = ""
    if game.campaign.campaign_history:
        campaign_info = (
            f"\ncampaign: chapter {game.campaign.chapter_number} of {len(game.campaign.campaign_history) + 1}"
        )
        for ch in game.campaign.campaign_history[-_limits.recap_campaign_history_window :]:
            campaign_info += f"\n  prev: {ch.title}: {ch.summary[: _limits.recap_campaign_summary_truncate]}"

    try:
        spec = AICallSpec(
            model=model_for_role("recap"),
            system=get_prompt("recap", lang=lang, content_boundaries_block=content_boundaries_block(game)),
            messages=[
                {
                    "role": "user",
                    "content": f"{game.player_name}—{game.character_concept}\n"
                    f"genre:{game.setting_genre} tone:{game.setting_tone}\n"
                    f"world:{game.setting_description}\n"
                    f"at:{game.world.current_location}\nlog:{log_text}\nnpcs:{npc_text}"
                    f"{arc_info}{campaign_info}\nnow:{game.world.current_scene_context}\n"
                    f"recent_scenes:\n{recent_narrations}",
                }
            ],
            log_role="recap",
            **sampling_params("recap"),
        )
        response = create_with_retry(provider, spec)
        return response.content
    except Exception as e:
        log(f"[Recap] Failed: {e}", level="warning")
        return _defaults["recap_fallback"].format(player_name=game.player_name)
