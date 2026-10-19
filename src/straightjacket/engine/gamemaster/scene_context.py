from __future__ import annotations

from ..engine_loader import eng
from ..models import BrainResult, GameState
from .config import gm
from .moves import is_dialog_branch
from .questions import answers


def generate_scene_context(
    game: GameState,
    brain: BrainResult,
    outcome: str | None,
    activated_npc_names: list[str],
) -> str:
    _defaults = eng().ai_text.narrator_defaults
    _npc_max = eng().prompt_display.memory_npcs_max
    move = brain.move
    location = game.world.current_location or _defaults["unknown_location"]
    npc_summary = ", ".join(activated_npc_names[:_npc_max]) if activated_npc_names else _defaults["no_npcs_nearby"]

    if outcome is None or is_dialog_branch(brain):
        return gm().scene_context.dialog.format(location=location, npc_summary=npc_summary)

    return gm().scene_context.template.format(
        result=outcome,
        move_label=answers().action_phrase(move),
        location=location,
        npc_summary=npc_summary,
    )
