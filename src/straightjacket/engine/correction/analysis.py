from __future__ import annotations

import json

from ..ai.brain import BrainResult
from ..ai.provider_base import AICallSpec, AIProvider, create_with_retry
from ..ai.schemas import get_correction_output_schema
from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import EngineConfig, GameState, NpcData
from ..prompt_blocks import get_narration_lang
from ..prompt_loader import get_prompt


def call_correction_brain(
    provider: AIProvider, game: GameState, correction_text: str, config: EngineConfig | None = None
) -> dict:
    snap = game.last_turn_snapshot
    if not snap:
        raise ValueError("No last_turn_snapshot available for correction")

    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)

    _defaults = eng().ai_text.narrator_defaults
    _trunc = eng().truncations

    def _npc_line(n: NpcData) -> str:
        aliases = f" aliases:{','.join(n.aliases)}" if n.aliases else ""
        return (
            f'id:{n.id} name:"{n.name}"{aliases} disposition:{n.disposition} desc:"{n.description[: _trunc.log_xlong]}"'
        )

    npc_lines = "\n".join(_npc_line(n) for n in game.npcs) or _defaults["no_npcs"]

    brain = snap.brain or BrainResult(type="none", move="none", stat="none")
    roll = snap.roll
    roll_summary = (
        f"{roll.result} ({roll.move}, {roll.stat_name}={roll.stat_value}, "
        f"d1={roll.d1}+d2={roll.d2} vs c1={roll.c1}/c2={roll.c2})"
        if roll
        else _defaults["no_roll"]
    )

    system = get_prompt("correction_brain", lang=lang)
    w = game.world

    user_msg = f"""## correction from player: {correction_text}

<last_turn>
player_input: {(snap.player_input or "")}
brain_interpretation: move={brain.move} stat={brain.stat} intent={brain.player_intent[: _trunc.prompt_short]}
roll: {roll_summary}
narration (first {_trunc.narration_preview} chars): {(snap.narration or "")[: _trunc.narration_preview]}
</last_turn>

<current_state>
location: {w.current_location}
scene_context: {w.current_scene_context[: _trunc.prompt_short]}
time: {w.time_of_day}
npcs:
{npc_lines}
</current_state>"""

    log(f"[Correction] Analysing: {correction_text[: _trunc.log_long]}")
    try:
        spec = AICallSpec(
            model=model_for_role("correction"),
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_correction_output_schema(),
            **sampling_params("correction"),
        )
        response = create_with_retry(provider, spec)
        result = json.loads(response.content)
        log(
            f"[Correction] source={result['correction_source']} "
            f"reroll={result['reroll_needed']} ops={len(result['state_ops'])}"
        )
        return result
    except Exception as e:
        log(f"[Correction] Brain failed ({type(e).__name__}: {e}), falling back to no-op state_error", level="warning")
        return {
            "correction_source": "state_error",
            "corrected_input": "",
            "reroll_needed": False,
            "corrected_stat": "none",
            "narrator_guidance": correction_text,
            "director_useful": False,
            "state_ops": [],
        }
