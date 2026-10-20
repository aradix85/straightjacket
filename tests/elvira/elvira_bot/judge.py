from __future__ import annotations

import json
import re
from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec
from straightjacket.engine.models import GameState
from straightjacket.engine.ruleset.moves import get_moves, outcome_text

from .ai_helpers import ELVIRA_ROLE, _p, bot_model, bot_provider

CRITERIA = ("result_integrity", "prompt_elements", "npc_voice", "player_agency", "restraint", "prose")

JUDGE_SCHEMA: dict[str, Any] = {
    "title": "narration_audit",
    "type": "object",
    "additionalProperties": False,
    "required": [*CRITERIA, "overall", "weakness", "revelation_conveyed"],
    "properties": {
        **{c: {"type": "integer"} for c in CRITERIA},
        "overall": {"type": "integer"},
        "weakness": {"type": "string"},
        "revelation_conveyed": {"type": "boolean"},
    },
}

_REVELATION = re.compile(r"<revelation\b[^>]*>(.*?)</revelation>", re.S)


def revelation_in(narrator_prompt: str) -> str:
    found = _REVELATION.search(narrator_prompt)
    return found.group(1).strip() if found else ""


def _move_outcome(game: GameState, move_id: str, result: str | None) -> tuple[str, str]:
    if not move_id or result is None:
        return _p("judge_none_move"), _p("judge_none_move")
    move = get_moves(game.setting_id).get(move_id)
    text = outcome_text(game.setting_id, move_id, result)
    if move is None or not text:
        return move_id, _p("judge_none_move")
    return move.name, text


def judge_turn(
    judge_cfg: dict[str, Any],
    game: GameState,
    action: str,
    narration: str,
    result: str | None,
    match: bool,
    previous: str,
    move_id: str,
    revelation: str,
) -> dict[str, Any]:
    scene = game.narrative.scene_count
    npcs = "\n".join(
        f"- {n.name} ({n.disposition}): {n.description or _p('judge_none_description')}"
        for n in game.npcs
        if any(m.scene == scene and m.type == "observation" for m in n.memory)
    ) or _p("bot_active_none_label")
    outcome = _p("judge_result_dialog") if result is None else result + (_p("judge_match_suffix") if match else "")
    move_name, move_text = _move_outcome(game, move_id, result)
    user = _p(
        "judge_turn",
        action=action,
        result=outcome,
        npcs=npcs,
        narration=narration,
        previous=previous.strip() or _p("judge_none_previous"),
        backstory=game.backstory.strip() or _p("judge_none_backstory"),
        move=move_name,
        move_outcome=move_text,
        revelation=revelation or _p("judge_none_revelation"),
    )
    spec = AICallSpec(
        model=bot_model(),
        system=_p("judge_system"),
        messages=[{"role": "user", "content": user}],
        max_tokens=judge_cfg["max_tokens"],
        json_schema=JUDGE_SCHEMA,
        extra_body=dict(judge_cfg["extra_body"]),
        log_role=ELVIRA_ROLE,
    )
    try:
        verdict: dict[str, Any] = json.loads(bot_provider().create_message(spec).content)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    scored = all(isinstance(verdict.get(key), int) for key in (*CRITERIA, "overall"))
    if not scored or not isinstance(verdict.get("revelation_conveyed"), bool):
        return {"error": f"incomplete verdict: {sorted(verdict)}"}
    if not revelation:
        del verdict["revelation_conveyed"]
    return verdict
