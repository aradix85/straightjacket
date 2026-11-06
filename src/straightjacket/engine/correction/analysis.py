from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from straightjacket.engine.ai.provider_base import AICallSpec, create_with_retry
from straightjacket.engine.ai.schemas import get_correction_output_schema
from straightjacket.engine.config_loader import model_for_role, narration_language, sampling_params
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.logging_util import log
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.xml_utils import xe as _xe

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import AIProvider
    from straightjacket.engine.models import BrainResult, GameState, NpcData, TurnSnapshot


def call_correction_brain(
    provider: AIProvider,
    game: GameState,
    correction_text: str,
    snap: TurnSnapshot,
    brain: BrainResult,
    narration: str,
) -> dict[str, Any]:
    lang = narration_language()

    defaults = eng().ai_text.narrator_defaults
    trunc = eng().truncations

    def _npc_line(n: NpcData) -> str:
        return get_prompt(
            "correction_npc_line",
            id=n.id,
            npc=_xe(n.name),
            aliases=get_prompt("correction_npc_aliases", aliases=_xe(",".join(n.aliases))) if n.aliases else "",
            disposition=n.disposition,
            description=_xe(n.description[: trunc.log_xlong]),
        )

    npc_lines = "\n".join(_npc_line(n) for n in game.npcs) or defaults["no_npcs"]

    roll = snap.roll
    roll_summary = (
        get_prompt(
            "correction_roll",
            result=roll.result,
            move=roll.move,
            stat=roll.stat_name,
            value=str(roll.stat_value),
            die=str(roll.d1),
            score=str(roll.action_score),
            c1=str(roll.c1),
            c2=str(roll.c2),
        )
        if roll
        else defaults["no_roll"].format(result=game.narrative.session_log[-1].result)
    )

    w = game.world
    user_msg = get_prompt(
        "correction_request",
        header=get_prompt("correction_request_header", correction=_xe(correction_text)),
        input=_xe(snap.player_input),
        move=brain.move,
        stat=brain.stat,
        intent=_xe(brain.player_intent[: trunc.prompt_short]),
        roll=roll_summary,
        preview=str(trunc.narration_preview),
        narration=_xe(narration[: trunc.narration_preview]),
        location=_xe(w.current_location),
        context=_xe(w.current_scene_context[: trunc.prompt_short]),
        time=w.time_of_day,
        npcs=npc_lines,
    )

    spec = AICallSpec(
        model=model_for_role("correction"),
        log_role="correction",
        system=get_prompt("correction_brain", lang=lang),
        messages=[{"role": "user", "content": user_msg}],
        json_schema=get_correction_output_schema([n.id for n in game.npcs]),
        tools=None,
        cached_system_prefix="",
        **sampling_params("correction"),
    )
    log(f"[Correction] Analysing: {correction_text[: trunc.log_long]}")
    try:
        response = create_with_retry(provider, spec)
        result: dict[str, Any] = json.loads(response.content)
        summary = f"source={result['correction_source']} ops={len(result['state_ops'])}"
    except Exception as e:
        log(f"[Correction] Brain failed ({type(e).__name__}: {e}), falling back to no-op state_error", level="warning")
        return {
            "correction_source": "state_error",
            "corrected_input": "",
            "narrator_guidance": correction_text,
            "director_useful": False,
            "state_ops": [],
        }
    log(f"[Correction] {summary}")
    return result
