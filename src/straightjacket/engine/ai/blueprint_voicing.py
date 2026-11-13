import json
from itertools import starmap
from typing import TYPE_CHECKING, Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, create_with_retry
from straightjacket.engine.ai.schemas import get_blueprint_voicing_schema
from straightjacket.engine.config_loader import model_for_role, narration_language, sampling_params
from straightjacket.engine.crafters.blueprint import ActSeed, BlueprintSeed
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import GameState
from straightjacket.engine.prompt_blocks import content_boundaries_block
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.xml_utils import xe as _xe

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import Message


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
        lines="\n".join(starmap(_revelation_seed_line, enumerate(seed.acts, start=1))),
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
        act_lines="\n".join(starmap(_act_line, enumerate(seed.acts, start=1))),
        revelation_seeds=revelation_seeds,
        ending_seeds=ending_seeds,
        campaign=campaign,
    )


def _ask_voicing(
    provider: AIProvider, spec: AICallSpec, expected: dict[str, int]
) -> tuple[str, dict[str, Any], str, list[str]] | None:
    try:
        content = create_with_retry(provider, spec).content
        voicing: dict[str, Any] = json.loads(content)
        mismatch = [
            f"{key} {len(voicing[key])} (expected {count})"
            for key, count in expected.items()
            if len(voicing[key]) != count
        ]
        conflict: str = voicing["central_conflict"]
    except Exception as e:
        log(
            f"[BlueprintVoicing] Failed ({type(e).__name__}: {e}), continuing without blueprint",
            level="warning",
        )
        return None
    return content, voicing, conflict, mismatch


def call_blueprint_voicing(
    provider: AIProvider,
    game: GameState,
    seed: BlueprintSeed,
) -> dict[str, Any] | None:
    system = get_prompt(
        "blueprint_voicing", lang=narration_language(), content_boundaries_block=content_boundaries_block(game)
    )
    blueprint = crafter().adventure_crafter.blueprint
    expected = {
        "acts": len(seed.acts),
        "revelations": len(seed.acts),
        "possible_endings": blueprint.possible_endings_per_blueprint,
    }
    schema = get_blueprint_voicing_schema(expected["acts"], expected["possible_endings"])
    model = model_for_role("blueprint_voicing")
    params = sampling_params("blueprint_voicing")
    messages: list[Message] = [{"role": "user", "content": _build_voicing_user_msg(game, seed)}]
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
            sampling=params,
        )
        answer = _ask_voicing(provider, spec, expected)
        if answer is None:
            return None
        content, voicing, conflict, mismatch = answer
        if not mismatch:
            log(
                f"[BlueprintVoicing] Succeeded: conflict={conflict[: eng().truncations.log_medium]}, "
                f"acts={expected['acts']}"
            )
            return voicing
        log(f"[BlueprintVoicing] Wrong counts ({', '.join(mismatch)}), asking again")
        messages.extend(
            (
                {"role": "assistant", "content": content},
                {"role": "user", "content": get_prompt("blueprint_voicing_count_retry", mismatch=", ".join(mismatch))},
            )
        )
    log(
        f"[BlueprintVoicing] Wrong counts despite its schema ({', '.join(mismatch)}), continuing without blueprint",
        level="warning",
    )
    return None
