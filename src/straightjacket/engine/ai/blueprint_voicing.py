import json
from typing import Any

from ..config_loader import model_for_role, narration_language, sampling_params
from ..crafters.blueprint import ActSeed, BlueprintSeed
from ..crafters.config import crafter
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from ..prompt_blocks import (
    content_boundaries_block,
)
from ..prompt_loader import get_prompt
from ..xml_utils import xe as _xe
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_blueprint_voicing_schema


def _act_line(n: int, act_seed: ActSeed) -> str:
    tp = act_seed.turning_point
    if tp.opens_plotline:
        turn = get_prompt("blueprint_turn_opens")
    elif tp.concludes_plotline:
        turn = get_prompt("blueprint_turn_concludes")
    else:
        turn = get_prompt("blueprint_turn_advances")
    return get_prompt(
        "blueprint_act",
        n=str(n),
        phase=act_seed.phase,
        first=str(act_seed.scene_range[0]),
        last=str(act_seed.scene_range[1]),
        beats="; ".join(h.name for h in tp.plot_points if h.special_range != "none"),
        plotline=tp.plotline,
        turn=turn,
    )


def _revelation_seed_line(n: int, act_seed: ActSeed) -> str:
    hit = act_seed.revelation_seed
    if hit is None:
        return get_prompt("blueprint_revelation_seed_none", n=str(n))
    return get_prompt("blueprint_revelation_seed", n=str(n), seed=hit.name, theme=hit.theme)


def _build_voicing_user_msg(game: GameState, seed: BlueprintSeed) -> str:
    revelation_seeds = get_prompt(
        "blueprint_revelation_seeds",
        lines="\n".join(_revelation_seed_line(i, act_seed) for i, act_seed in enumerate(seed.acts, start=1)),
    )

    ending_seeds = ""
    if seed.ending_seeds:
        lines = [
            get_prompt("blueprint_ending_seed", n=str(i), plotline=plotline.name, status=plotline.status)
            for i, plotline in enumerate(seed.ending_seeds, start=1)
        ]
        ending_seeds = "\n" + get_prompt("blueprint_ending_seeds", lines="\n".join(lines))

    campaign = ""
    if game.campaign.campaign_history:
        campaign = "\n" + get_prompt("blueprint_campaign_chapter", chapter=str(game.campaign.chapter_number))
        for ch in game.campaign.campaign_history[-eng().recap_limits.recap_campaign_window :]:
            campaign += "\n" + get_prompt(
                "blueprint_previous_chapter", chapter=str(ch.chapter), summary=_xe(ch.summary)
            )

    blueprint = crafter().adventure_crafter.blueprint
    return get_prompt(
        "blueprint_request",
        themes=", ".join(seed.themes),
        genre=game.setting_genre,
        tone=game.setting_tone,
        world=game.setting_description,
        player=_xe(game.player_name),
        concept=_xe(game.character_concept),
        backstory="\n" + get_prompt("blueprint_backstory", backstory=_xe(game.backstory)) if game.backstory else "",
        location="\n" + get_prompt("blueprint_location", location=_xe(game.world.current_location))
        if game.world.current_location
        else "",
        acts=str(len(seed.acts)),
        endings=str(blueprint.possible_endings_per_blueprint),
        act_lines="\n".join(_act_line(i, act_seed) for i, act_seed in enumerate(seed.acts, start=1)),
        revelation_seeds=revelation_seeds,
        ending_seeds=ending_seeds,
        campaign=campaign,
    )


def call_blueprint_voicing(
    provider: AIProvider,
    game: GameState,
    seed: BlueprintSeed,
) -> dict[str, Any] | None:
    lang = narration_language()
    cb = content_boundaries_block(game)

    system = get_prompt("blueprint_voicing", lang=lang, content_boundaries_block=cb)
    user_msg = _build_voicing_user_msg(game, seed)
    blueprint = crafter().adventure_crafter.blueprint

    expected = {
        "acts": len(seed.acts),
        "revelations": len(seed.acts),
        "possible_endings": blueprint.possible_endings_per_blueprint,
    }
    schema = get_blueprint_voicing_schema(expected["acts"], expected["possible_endings"])
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
            tools=None,
            log_role="blueprint_voicing",
            cached_system_prefix="",
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
                f"acts={expected['acts']}"
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
