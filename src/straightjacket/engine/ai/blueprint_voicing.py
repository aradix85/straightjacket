from typing import Any
import json

from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics.adventure_crafter import BlueprintSeed
from ..models import EngineConfig, GameState
from ..prompt_blocks import (
    content_boundaries_block,
    get_narration_lang,
)
from ..prompt_loader import get_prompt
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_blueprint_voicing_schema


def _build_voicing_user_msg(game: GameState, seed: BlueprintSeed) -> str:
    parts = [
        f"structure_type:{seed.structure_type}",
        f"themes:{', '.join(seed.themes)}",
        f"genre:{game.setting_genre}",
        f"tone:{game.setting_tone}",
        f"world:{game.setting_description}",
        f"character:{game.player_name} — {game.character_concept}",
    ]
    if game.backstory:
        parts.append(f"backstory:{game.backstory}")
    if game.world.current_location:
        parts.append(f"location:{game.world.current_location}")

    blueprint = eng().adventure_crafter.blueprint
    parts.append(
        f"required_counts: acts={len(seed.acts)} revelations={blueprint.revelations_per_blueprint} "
        f"possible_endings={blueprint.possible_endings_per_blueprint}"
    )
    parts.append("<acts>")
    for i, act_seed in enumerate(seed.acts, start=1):
        line = f"act {i} phase={act_seed.phase} scene_range={act_seed.scene_range[0]}-{act_seed.scene_range[1]}"
        if act_seed.turning_point is not None:
            tp = act_seed.turning_point
            beat_names = "; ".join(h.name for h in tp.plot_points if h.special_range != "none")
            line += f" turning_point_beats=[{beat_names}]"
        parts.append(line)
    parts.append("</acts>")

    if seed.revelation_seeds:
        parts.append("<revelation_seeds>")
        for i, hit in enumerate(seed.revelation_seeds, start=1):
            parts.append(f"revelation {i}: {hit.name} (theme={hit.theme})")
        parts.append("</revelation_seeds>")

    if seed.ending_seeds:
        parts.append("<ending_seeds>")
        for i, plotline in enumerate(seed.ending_seeds, start=1):
            parts.append(f"ending {i}: plotline={plotline.name} status={plotline.status}")
        parts.append("</ending_seeds>")

    if game.campaign.campaign_history:
        parts.append(f"campaign_chapter:{game.campaign.chapter_number}")
        for ch in game.campaign.campaign_history[-eng().recap_limits.recap_campaign_window :]:
            parts.append(f"  prev_chapter_{ch.chapter}: {ch.summary}")

    return "\n".join(parts)


def _count_mismatch(voicing: dict[str, Any], seed: BlueprintSeed) -> list[str]:
    blueprint = eng().adventure_crafter.blueprint
    expected = {
        "acts": len(seed.acts),
        "revelations": blueprint.revelations_per_blueprint,
        "possible_endings": blueprint.possible_endings_per_blueprint,
    }
    return [
        f"{key} {len(voicing[key])} (expected {count})" for key, count in expected.items() if len(voicing[key]) != count
    ]


def call_blueprint_voicing(
    provider: AIProvider,
    game: GameState,
    seed: BlueprintSeed,
    config: EngineConfig | None = None,
) -> dict[str, Any] | None:
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    cb = content_boundaries_block(game)

    system = get_prompt("blueprint_voicing", lang=lang, content_boundaries_block=cb)
    user_msg = _build_voicing_user_msg(game, seed)

    try:
        spec = AICallSpec(
            model=model_for_role("blueprint_voicing"),
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_blueprint_voicing_schema(),
            log_role="blueprint_voicing",
            **sampling_params("blueprint_voicing"),
        )
        for attempt in range(spec.max_retries + 1):
            response = create_with_retry(provider, spec)
            voicing: dict[str, Any] = json.loads(response.content)
            mismatch = _count_mismatch(voicing, seed)
            if not mismatch:
                log(
                    f"[BlueprintVoicing] Succeeded: "
                    f"conflict={voicing['central_conflict'][: eng().truncations.log_medium]}, "
                    f"acts={len(voicing['acts'])}, revelations={len(voicing['revelations'])}"
                )
                return voicing
            log(
                f"[BlueprintVoicing] Wrong counts: {', '.join(mismatch)} (attempt {attempt + 1}/{spec.max_retries + 1})",
                level="warning",
            )
        raise ValueError(f"voicing kept returning wrong counts: {', '.join(mismatch)}")
    except Exception as e:
        log(
            f"[BlueprintVoicing] Failed ({type(e).__name__}: {e}), continuing without blueprint",
            level="warning",
        )
        return None
