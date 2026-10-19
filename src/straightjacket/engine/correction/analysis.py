from __future__ import annotations

import json
from typing import Any

from ..ai.provider_base import AICallSpec, AIProvider, create_with_retry
from ..ai.schemas import get_correction_output_schema
from ..config_loader import model_for_role, narration_language, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, GameState, NpcData, TurnSnapshot
from ..prompt_loader import get_prompt
from ..xml_utils import xe as _xe


def call_correction_brain(
    provider: AIProvider,
    game: GameState,
    correction_text: str,
    snap: TurnSnapshot,
    brain: BrainResult,
    narration: str,
) -> dict[str, Any]:
    lang = narration_language()

    _defaults = eng().ai_text.narrator_defaults
    _trunc = eng().truncations

    def _npc_line(n: NpcData) -> str:
        aliases = f" aliases:{_xe(','.join(n.aliases))}" if n.aliases else ""
        return (
            f'id:{n.id} name:"{_xe(n.name)}"{aliases} disposition:{n.disposition} '
            f'desc:"{_xe(n.description[: _trunc.log_xlong])}"'
        )

    npc_lines = "\n".join(_npc_line(n) for n in game.npcs) or _defaults["no_npcs"]

    roll = snap.roll
    roll_summary = (
        f"{roll.result} ({roll.move}, {roll.stat_name}={roll.stat_value}, "
        f"action die {roll.d1}, score {roll.action_score} vs c1={roll.c1}/c2={roll.c2})"
        if roll
        else _defaults["no_roll"]
    )

    w = game.world
    user_msg = f"""## correction from player: {_xe(correction_text)}

<last_turn>
player_input: {_xe(snap.player_input)}
brain_interpretation: move={brain.move} stat={brain.stat} intent={_xe(brain.player_intent[: _trunc.prompt_short])}
roll: {roll_summary}
narration (first {_trunc.narration_preview} chars): {_xe(narration[: _trunc.narration_preview])}
</last_turn>

<current_state>
location: {_xe(w.current_location)}
scene_context: {_xe(w.current_scene_context[: _trunc.prompt_short])}
time: {w.time_of_day}
npcs:
{npc_lines}
</current_state>"""

    spec = AICallSpec(
        model=model_for_role("correction"),
        log_role="correction",
        system=get_prompt("correction_brain", lang=lang),
        messages=[{"role": "user", "content": user_msg}],
        json_schema=get_correction_output_schema([n.id for n in game.npcs]),
        **sampling_params("correction"),
    )
    log(f"[Correction] Analysing: {correction_text[: _trunc.log_long]}")
    try:
        response = create_with_retry(provider, spec)
        result: dict[str, Any] = json.loads(response.content)
        log(f"[Correction] source={result['correction_source']} ops={len(result['state_ops'])}")
        return result
    except Exception as e:
        log(f"[Correction] Brain failed ({type(e).__name__}: {e}), falling back to no-op state_error", level="warning")
        return {
            "correction_source": "state_error",
            "corrected_input": "",
            "narrator_guidance": correction_text,
            "director_useful": False,
            "state_ops": [],
        }
