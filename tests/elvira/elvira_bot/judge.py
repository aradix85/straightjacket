from __future__ import annotations

import json
from typing import Any

from straightjacket.engine.config_loader import model_for_role
from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider
from straightjacket.engine.models import GameState

from .ai_helpers import _p

CRITERIA = ("result_integrity", "prompt_elements", "npc_voice", "player_agency", "restraint", "prose")

JUDGE_SCHEMA: dict[str, Any] = {
    "title": "narration_audit",
    "type": "object",
    "additionalProperties": False,
    "required": [*CRITERIA, "overall", "weakness"],
    "properties": {
        **{c: {"type": "integer"} for c in CRITERIA},
        "overall": {"type": "integer"},
        "weakness": {"type": "string"},
    },
}


def judge_turn(
    provider: AIProvider,
    judge_cfg: dict[str, Any],
    game: GameState,
    action: str,
    narration: str,
    result: str | None,
    match: bool,
) -> dict[str, Any]:
    npcs = "; ".join(f"{n.name} ({n.disposition})" for n in game.npcs if n.status == "active") or _p(
        "bot_active_none_label"
    )
    outcome = _p("judge_result_dialog") if result is None else result + (_p("judge_match_suffix") if match else "")
    user = _p("judge_turn", action=action, result=outcome, npcs=npcs, narration=narration)
    spec = AICallSpec(
        model=model_for_role("brain"),
        system=_p("judge_system"),
        messages=[{"role": "user", "content": user}],
        max_tokens=judge_cfg["max_tokens"],
        json_schema=JUDGE_SCHEMA,
        extra_body=dict(judge_cfg["extra_body"]),
        log_role="brain",
    )
    try:
        verdict: dict[str, Any] = json.loads(provider.create_message(spec).content)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    if not all(isinstance(verdict.get(key), int) for key in (*CRITERIA, "overall")):
        return {"error": f"incomplete verdict: {sorted(verdict)}"}
    return verdict
