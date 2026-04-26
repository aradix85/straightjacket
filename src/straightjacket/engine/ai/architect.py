"""AI Story Architect, Recap, and Chapter Summary calls."""

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
from ..story_state import get_current_act
from .provider_base import AIProvider, create_with_retry
from .schemas import get_chapter_summary_schema, get_story_architect_output_schema


def call_recap(provider: AIProvider, game: GameState, config: EngineConfig | None = None) -> str:
    """Generate a 'previously on...' recap from the PLAYER'S perspective only."""
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    _e = eng()
    _defaults = _e.ai_text.narrator_defaults
    _limits = _e.architect_limits
    log_text = "; ".join(
        f"S{s.scene}:{s.rich_summary or s.summary}({s.result})"
        for s in game.narrative.session_log[-_limits.recap_log_window :]
    )
    # NPC text: Only player-visible info (no agenda, no secrets) and only introduced NPCs
    npc_text = (
        ", ".join(
            f"{n.name}({n.disposition},B{get_npc_bond(game, n.id)})"
            for n in game.npcs
            if n.status == "active" and n.introduced
        )
        or _defaults["no_npcs"]
    )
    # Last narrations for tone/content reference -- these ARE what the player saw
    recent_narrations = "\n---\n".join(
        entry.narration[: _limits.recap_narration_truncate]
        for entry in game.narrative.narration_history[-_limits.recap_narration_window :]
    )
    # Story arc info: only act/phase, no central_conflict (that's director-level meta)
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
        response = create_with_retry(
            provider,
            model=model_for_role("recap"),
            system=get_prompt(
                "recap", role="recap", lang=lang, content_boundaries_block=content_boundaries_block(game)
            ),
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
            **sampling_params("recap"),
            log_role="recap",
        )
        return response.content
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(f"[Recap] Failed: {e}", level="warning")
        return _defaults["recap_fallback"].format(player_name=game.player_name)


def _build_architect_user_msg(game: GameState) -> str:
    """Construct the architect's user message: genre, tone, world, character,
    location, situation, NPCs, campaign history, backstory.
    """
    _defaults = eng().ai_text.narrator_defaults
    _limits = eng().architect_limits

    npc_text = ", ".join(n.name for n in game.npcs) if game.npcs else _defaults["no_npcs_yet"]

    campaign_ctx = ""
    if game.campaign.campaign_history:
        campaign_ctx = f"\ncampaign_chapter:{game.campaign.chapter_number}"
        for ch in game.campaign.campaign_history[-_limits.architect_campaign_window :]:
            campaign_ctx += f"\n  prev_chapter_{ch.chapter}: {ch.summary}"
            if ch.unresolved_threads:
                campaign_ctx += f" [threads: {'; '.join(ch.unresolved_threads)}]"
            if ch.character_growth:
                campaign_ctx += f" [growth: {ch.character_growth}]"
            if ch.thematic_question:
                campaign_ctx += f" [thematic_question: {ch.thematic_question}]"

    backstory_text = f"\nbackstory(canon past):{game.backstory}" if game.backstory else ""

    return (
        f"genre:{game.setting_genre} tone:{game.setting_tone}\n"
        f"world:{game.setting_description}\n"
        f"character:{game.player_name} — {game.character_concept}\n"
        f"location:{game.world.current_location}\n"
        f"situation:{game.world.current_scene_context}\n"
        f"npcs:{npc_text}{campaign_ctx}{backstory_text}"
    )


def _clean_act_moods(blueprint: dict) -> None:
    """Strip forbidden mood terms from each act. If all terms are stripped,
    fall back to the default_act_mood list. Mutates blueprint in place.
    """
    _e = eng()
    forbidden = set(_e.architect.forbidden_moods)
    fallback = list(_e.ai_text.narrator_defaults["default_act_mood"])

    for act in blueprint.get("acts", []):
        mood = act.get("mood", "")
        if not mood:
            continue
        mood_words = [w.strip() for w in mood.split(",")]
        cleaned = [w for w in mood_words if w.lower() not in forbidden]
        if len(cleaned) == len(mood_words):
            continue
        stripped_words = [w for w in mood_words if w.lower() in forbidden]
        if not cleaned:
            cleaned = list(fallback)
        act["mood"] = ", ".join(cleaned)
        log(
            f"[Story] Stripped forbidden mood(s) {stripped_words} from act "
            f"'{act.get('phase', '?')}', now: '{act['mood']}'"
        )


def _validate_scene_ranges(blueprint: dict) -> None:
    """Ensure every act's scene_range is exactly [start, end]. Replace malformed
    ranges with engine-default. Mutates blueprint in place.
    """
    default_range = list(eng().scene_range_default)
    for act in blueprint.get("acts", []):
        sr = act.get("scene_range", [])
        if not isinstance(sr, list) or len(sr) != 2:
            log(
                f"[Story] Invalid scene_range {sr!r} in act '{act.get('phase', '?')}', "
                f"replacing with default {default_range}",
                level="warning",
            )
            act["scene_range"] = list(default_range)


def call_story_architect(
    provider: AIProvider, game: GameState, structure_type: str = "3act", config: EngineConfig | None = None
) -> dict | None:
    """Generate a story blueprint. Supports 3-act and Kishōtenketsu (4-act).

    Builds the user message from game state, calls the architect model with the
    structure-appropriate system prompt, then post-processes the blueprint:
    initialize tracking fields, strip forbidden-mood terms from acts, validate
    scene ranges.
    """
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    cb = content_boundaries_block(game)

    prompt_vars = dict(lang=lang, content_boundaries_block=cb)
    system = get_prompt(
        "architect_kishotenketsu" if structure_type == "kishotenketsu" else "architect_3act",
        role="architect",
        **prompt_vars,
    )
    user_msg = _build_architect_user_msg(game)

    try:
        response = create_with_retry(
            provider,
            model=model_for_role("architect"),
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_story_architect_output_schema(),
            **sampling_params("architect"),
            log_role="architect",
        )
        blueprint = json.loads(response.content)
        blueprint["revealed"] = []
        blueprint["triggered_transitions"] = []
        blueprint["story_complete"] = False
        blueprint["structure_type"] = structure_type

        _clean_act_moods(blueprint)
        _validate_scene_ranges(blueprint)

        log(
            f"[Story] Architect succeeded: "
            f"conflict={blueprint['central_conflict'][: eng().truncations.log_medium]}, "
            f"acts={len(blueprint['acts'])}, "
            f"revelations={len(blueprint.get('revelations', []))}"
        )
        return blueprint

    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(f"[Story] Architect failed ({type(e).__name__}: {e}), continuing without story blueprint", level="warning")
        return None


def call_chapter_summary(
    provider: AIProvider, game: GameState, config: EngineConfig | None = None, epilogue_text: str = ""
) -> dict:
    """Generate the narrative summary of a completed chapter.

    Returns a dict with the AI-written narrative fields only (title, summary,
    unresolved_threads, character_growth, npc_evolutions, thematic_question,
    post_story_location). The caller (`_close_previous_chapter` in
    `game/chapters.py`) combines this with engine-captured mechanical state
    (chapter, scenes, progress_tracks, threats, impacts, assets, threads) to
    construct the final ChapterSummary. This keeps narrative interpretation
    (AI-side) and mechanical snapshot (engine-side) cleanly separated — the
    AI never sees nor writes the canonical chapter-end state.
    """
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    _e = eng()
    _defaults = _e.ai_text.narrator_defaults
    _limits = _e.architect_limits
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
        response = create_with_retry(
            provider,
            model=model_for_role("chapter_summary"),
            system=get_prompt(
                "chapter_summary",
                role="chapter_summary",
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
            **sampling_params("chapter_summary"),
            log_role="chapter_summary",
        )
        return json.loads(response.content)
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
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
