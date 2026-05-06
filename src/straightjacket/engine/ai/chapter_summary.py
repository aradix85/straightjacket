import json

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
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_chapter_summary_schema


def call_chapter_summary(
    provider: AIProvider, game: GameState, config: EngineConfig | None = None, epilogue_text: str = ""
) -> dict:
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    _e = eng()
    _defaults = _e.ai_text.narrator_defaults
    _limits = _e.recap_limits
    log_text = "; ".join(
        f"S{s.scene}:{s.summary}({s.result})" for s in game.narrative.session_log[-_limits.chapter_summary_log_window :]
    )
    npc_text = (
        ", ".join(f"{n.name}({n.disposition},B{get_npc_bond(game, n.id)})" for n in game.npcs if n.status == "active")
        or _defaults["no_npcs"]
    )

    bp = game.narrative.story_blueprint
    conflict = bp.central_conflict if bp else ""

    epilogue_block = ""
    if epilogue_text:
        epilogue_block = f"\n<epilogue>\n{epilogue_text}\n</epilogue>"

    try:
        spec = AICallSpec(
            model=model_for_role("chapter_summary"),
            system=get_prompt(
                "chapter_summary",
                lang=lang,
                content_boundaries_block=content_boundaries_block(game),
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"character:{game.player_name} — {game.character_concept}\n"
                    f"genre:{game.setting_genre} tone:{game.setting_tone}\n"
                    f"world:{game.setting_description}\n"
                    f"conflict:{conflict}\n"
                    f"log:{log_text}\nnpcs:{npc_text}\n"
                    f"location:{game.world.current_location}\n"
                    f"situation:{game.world.current_scene_context}"
                    f"{epilogue_block}",
                }
            ],
            json_schema=get_chapter_summary_schema(),
            log_role="chapter_summary",
            **sampling_params("chapter_summary"),
        )
        response = create_with_retry(provider, spec)
        return json.loads(response.content)
    except Exception as e:
        log(f"[ChapterSummary] Structured output failed ({type(e).__name__}: {e}), using fallback", level="warning")
        return {
            "title": _defaults["chapter_summary_fallback_title"].format(chapter=game.campaign.chapter_number),
            "summary": _defaults["chapter_summary_fallback_text"].format(
                player_name=game.player_name, location=game.world.current_location
            ),
            "unresolved_threads": list(_defaults["chapter_summary_fallback_unresolved_threads"]),
            "character_growth": _defaults["chapter_summary_fallback_character_growth"],
            "npc_evolutions": list(_defaults["chapter_summary_fallback_npc_evolutions"]),
            "thematic_question": _defaults["chapter_summary_fallback_thematic_question"],
            "post_story_location": game.world.current_location,
        }
