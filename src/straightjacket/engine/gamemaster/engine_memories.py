from __future__ import annotations

from collections.abc import Sequence

from ..engine_loader import eng
from ..models import BrainResult, GameState, MemoryEntry, NpcData
from .config import gm
from .moves import is_dialog_memory
from .questions import answers


def derive_memory_emotion(move: str, outcome: str, disposition: str) -> str:
    memory_emotions = gm().memory_emotions
    base_map = memory_emotions.base
    suffix_map = memory_emotions.disposition_suffix

    kind = answers().action_kind(move)
    is_dialog = move == "dialog" or outcome == "dialog"
    key = "dialog" if is_dialog else f"{kind}_{outcome}"

    base = base_map[key]
    suffix = suffix_map[disposition]
    return base + suffix


def generate_engine_memories(
    game: GameState,
    brain: BrainResult,
    outcome: str | None,
    activated_npc_ids: set[str],
    consequences: Sequence[str],
) -> list[tuple[NpcData, MemoryEntry]]:
    from .npc.memory import score_importance

    templates = gm().memory_templates
    result_text_map = gm().get_raw("memory_result_text")
    scene = game.narrative.scene_count

    move = brain.move
    is_dialog = is_dialog_memory(brain, roll_present=outcome is not None)
    told_outcome = outcome or "dialog"
    kind = answers().action_kind(move)
    intent = brain.player_intent

    result_key = "dialog" if is_dialog else f"{kind}_{told_outcome}"
    result_text = result_text_map[result_key]
    move_verb = answers().action_phrase(move)

    _pd = eng().prompt_display
    _cons_max = _pd.memory_consequences_max

    if consequences:
        result_text += f" ({', '.join(consequences[:_cons_max])})"

    memories: list[tuple[NpcData, MemoryEntry]] = []
    for npc in game.npcs:
        if npc.id not in activated_npc_ids:
            continue
        if npc.status not in gm().npc_status_groups.in_play:
            continue

        if is_dialog:
            template_key = "dialog" if brain.target_npc else "dialog_no_target"
        elif brain.target_npc == npc.id:
            template_key = "action_targeted"
        else:
            template_key = "action"

        template: str = getattr(templates, template_key)

        event_text = template.format(
            scene=scene,
            player=game.player_name,
            npc=npc.name,
            intent=intent[: eng().truncations.log_medium]
            if intent
            else eng().ai_text.narrator_defaults["unknown_intent"],
            move_verb=move_verb,
            result_text=result_text,
            move=move,
            consequences=", ".join(consequences[:_cons_max]),
        )

        emotional = derive_memory_emotion(move, told_outcome, npc.disposition)
        importance = score_importance(emotional, event_text)

        memories.append(
            (
                npc,
                MemoryEntry(
                    scene=scene,
                    event=event_text,
                    emotional_weight=emotional,
                    importance=importance,
                    type="observation",
                    tone="",
                    tone_key="",
                    about_npc=brain.target_npc if brain.target_npc != npc.id else None,
                ),
            )
        )

    return memories
