from typing import Any
import json

from ..config_loader import model_for_role, narration_language, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics.adventure_crafter import BlueprintSeed
from ..models import GameState
from ..prompt_blocks import (
    content_boundaries_block,
)
from ..prompt_loader import get_prompt
from ..xml_utils import xe as _xe
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_blueprint_voicing_schema


def _build_voicing_user_msg(game: GameState, seed: BlueprintSeed) -> str:
    parts = [
        f"structure_type:{seed.structure_type}",
        f"themes:{', '.join(seed.themes)}",
        f"genre:{game.setting_genre}",
        f"tone:{game.setting_tone}",
        f"world:{game.setting_description}",
        f"character:{_xe(game.player_name)} — {_xe(game.character_concept)}",
    ]
    if game.backstory:
        parts.append(f"backstory:{_xe(game.backstory)}")
    if game.world.current_location:
        parts.append(f"location:{_xe(game.world.current_location)}")

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
            parts.append(f"  prev_chapter_{ch.chapter}: {_xe(ch.summary)}")

    return "\n".join(parts)


def call_blueprint_voicing(
    provider: AIProvider,
    game: GameState,
    seed: BlueprintSeed,
) -> dict[str, Any] | None:
    lang = narration_language()
    cb = content_boundaries_block(game)

    system = get_prompt("blueprint_voicing", lang=lang, content_boundaries_block=cb)
    user_msg = _build_voicing_user_msg(game, seed)
    blueprint = eng().adventure_crafter.blueprint

    expected = {
        "acts": len(seed.acts),
        "revelations": blueprint.revelations_per_blueprint,
        "possible_endings": blueprint.possible_endings_per_blueprint,
    }
    schema = get_blueprint_voicing_schema(expected["acts"], expected["revelations"], expected["possible_endings"])
    model = model_for_role("blueprint_voicing")
    params = sampling_params("blueprint_voicing")
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_msg}]
    mismatch: list[str] = []
    for _attempt in range(blueprint.voicing_count_retries + 1):
        spec = AICallSpec(
            model=model,
            system=system,
            messages=list(messages),
            json_schema=schema,
            log_role="blueprint_voicing",
            **params,
        )
        try:
            content = create_with_retry(provider, spec).content
            voicing: dict[str, Any] = json.loads(content)
            mismatch = [
                f"{key} {len(voicing[key])} (expected {count})"
                for key, count in expected.items()
                if len(voicing[key]) != count
            ]
            conflict = voicing["central_conflict"]
        except Exception as e:
            log(
                f"[BlueprintVoicing] Failed ({type(e).__name__}: {e}), continuing without blueprint",
                level="warning",
            )
            return None
        if not mismatch:
            log(
                f"[BlueprintVoicing] Succeeded: conflict={conflict[: eng().truncations.log_medium]}, "
                f"acts={expected['acts']}, revelations={expected['revelations']}"
            )
            return voicing
        log(f"[BlueprintVoicing] Wrong counts ({', '.join(mismatch)}), asking again")
        messages.append({"role": "assistant", "content": content})
        messages.append(
            {"role": "user", "content": get_prompt("blueprint_voicing_count_retry", mismatch=", ".join(mismatch))}
        )
    log(
        f"[BlueprintVoicing] Wrong counts despite its schema ({', '.join(mismatch)}), continuing without blueprint",
        level="warning",
    )
    return None
