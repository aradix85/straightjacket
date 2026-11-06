from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.moves import is_dialog_branch
from straightjacket.engine.gamemaster.questions import answers

if TYPE_CHECKING:
    from straightjacket.engine.models import BrainResult, GameState


def generate_scene_context(
    game: GameState,
    brain: BrainResult,
    outcome: str,
    activated_npc_names: list[str],
) -> str:
    defaults = eng().ai_text.narrator_defaults
    npc_max = eng().prompt_display.memory_npcs_max
    move = brain.move
    location = game.world.current_location or defaults["unknown_location"]
    npc_summary = ", ".join(activated_npc_names[:npc_max]) if activated_npc_names else defaults["no_npcs_nearby"]

    if is_dialog_branch(brain):
        return gm().scene_context.dialog.format(location=location, npc_summary=npc_summary)
    if outcome in gm().outcomes.unrolled:
        return gm().scene_context.unrolled_move.format(
            move_label=answers().action_phrase(move), location=location, npc_summary=npc_summary
        )

    return gm().scene_context.template.format(
        result=outcome,
        move_label=answers().action_phrase(move),
        location=location,
        npc_summary=npc_summary,
    )
