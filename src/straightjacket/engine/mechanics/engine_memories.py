from __future__ import annotations

from ..engine_loader import eng
from ..models import BrainResult, GameState, RollResult
from .resolvers import is_dialog_memory, move_category


def derive_memory_emotion(move: str, result: str, disposition: str) -> str:
    _e = eng()
    memory_emotions = _e.memory_emotions
    base_map = memory_emotions.base
    suffix_map = memory_emotions.disposition_suffix

    category = move_category(move)
    is_dialog = move == "dialog" or result == "dialog"
    key = "dialog" if is_dialog else f"{category}_{result}"

    base = base_map[key]
    suffix = suffix_map[disposition]
    return base + suffix


def generate_engine_memories(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    activated_npc_ids: set[str],
    consequences: list[str] | None = None,
) -> list[dict]:
    from ..npc.memory import score_importance

    _e = eng()
    templates = _e.memory_templates
    result_text_map = _e.get_raw("memory_result_text")
    verb_map = _e.get_raw("memory_move_verbs")
    scene = game.narrative.scene_count

    move = brain.move
    is_dialog = is_dialog_memory(brain, roll_present=roll is not None)
    result = roll.result if roll else "dialog"
    category = move_category(move)
    intent = brain.player_intent or ""

    result_key = "dialog" if is_dialog else f"{category}_{result}"
    result_text = result_text_map[result_key]
    move_verb = verb_map[move] if move in verb_map else verb_map["_catchall"]

    _pd = eng().prompt_display
    _cons_max = _pd.memory_consequences_max

    if consequences:
        result_text += f" ({', '.join(consequences[:_cons_max])})"

    memories = []
    for npc in game.npcs:
        if npc.id not in activated_npc_ids:
            continue
        if npc.status not in ("active", "background"):
            continue

        is_targeted = brain.target_npc and brain.target_npc == npc.id

        if is_dialog:
            template_key = "dialog" if (is_targeted or brain.target_npc) else "dialog_no_target"
        elif is_targeted:
            template_key = "action_targeted"
        else:
            template_key = "action"

        template: str = getattr(templates, template_key)

        event_text = template.format(
            scene=scene,
            player=game.player_name,
            npc=npc.name,
            intent=intent[: eng().truncations.log_medium] if intent else "general",
            move_verb=move_verb,
            result_text=result_text,
            move=move,
            consequences=", ".join(consequences[:_cons_max]) if consequences else "",
        )

        emotional = derive_memory_emotion(move, result, npc.disposition)
        importance, debug = score_importance(emotional, event_text, debug=True)

        memories.append(
            {
                "npc_id": npc.id,
                "event": event_text,
                "emotional_weight": emotional,
                "importance": importance,
                "about_npc": brain.target_npc if brain.target_npc and brain.target_npc != npc.id else None,
                "_score_debug": f"engine-generated | {debug}",
            }
        )

    return memories


def generate_scene_context(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    activated_npc_names: list[str],
) -> str:
    _e = eng()
    _defaults = _e.ai_text.narrator_defaults
    _npc_max = _e.prompt_display.memory_npcs_max
    move = brain.move
    location = game.world.current_location or _defaults["unknown_location"]
    npc_summary = ", ".join(activated_npc_names[:_npc_max]) if activated_npc_names else _defaults["no_npcs_nearby"]

    if is_dialog_memory(brain, roll_present=roll is not None):
        return _e.scene_context.dialog.format(location=location, npc_summary=npc_summary)

    result = roll.result if roll else "MISS"
    verb_map = _e.get_raw("memory_move_verbs")
    move_label = verb_map[move] if move in verb_map else move
    return _e.scene_context.template.format(
        result=result,
        move_label=move_label,
        location=location,
        npc_summary=npc_summary,
    )
