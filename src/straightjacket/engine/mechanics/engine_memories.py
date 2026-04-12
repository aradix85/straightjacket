#!/usr/bin/env python3
"""Engine-side memory generation: emotion derivation, observation memories, scene context."""

from __future__ import annotations

from ..engine_loader import eng
from ..models import BrainResult, GameState, RollResult
from .resolvers import _move_category


def derive_memory_emotion(move: str, result: str, disposition: str = "neutral") -> str:
    """Derive emotional_weight for an NPC memory from mechanical context.

    Uses engine.yaml memory_emotions table: (move_category, result) → base emotion,
    then appends disposition suffix. Falls back to 'neutral' for unknown combinations.
    """
    _e = eng()
    base_map = _e.get_raw("memory_emotions", {}).get("base", {})
    suffix_map = _e.get_raw("memory_emotions", {}).get("disposition_suffix", {})

    # Determine move category
    category = "other"
    move_cats = _e.get_raw("move_categories", {})
    for cat in ("combat", "social", "endure", "recovery"):
        cat_moves = move_cats.get(cat, [])
        if move in cat_moves:
            category = cat
            break

    if move == "dialog" or result == "dialog":
        key = "dialog"
    else:
        key = f"{category}_{result}"

    base = base_map.get(key, "neutral")
    suffix = suffix_map.get(disposition, "")
    return base + suffix


def generate_engine_memories(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    activated_npc_ids: set[str],
    consequences: list[str] | None = None,
) -> list[dict]:
    """Generate observation memories for activated NPCs from mechanical context.

    Replaces AI-generated memory_updates for known events. Engine knows:
    which NPCs were present, what move occurred, what the result was,
    what consequences applied. Templates from engine.yaml produce
    narrative-flavored memories the narrator can build on.
    """
    from ..npc.memory import score_importance

    _e = eng()
    templates = _e.get_raw("memory_templates", {})
    result_text_map = _e.get_raw("memory_result_text", {})
    verb_map = _e.get_raw("memory_move_verbs", {})
    scene = game.narrative.scene_count

    move = brain.move
    result = roll.result if roll else "dialog"
    category = _move_category(move)
    intent = brain.player_intent or ""

    # Resolve template variables
    result_key = "dialog" if move == "dialog" else f"{category}_{result}"
    result_text = result_text_map.get(result_key, result_text_map.get("other_MISS", "something happened"))
    move_verb = verb_map.get(move, verb_map.get("_default", "acted"))

    if consequences:
        result_text += f" ({', '.join(consequences[:3])})"

    memories = []
    for npc in game.npcs:
        if npc.id not in activated_npc_ids:
            continue
        if npc.status not in ("active", "background"):
            continue

        # Choose template
        is_dialog = move == "dialog" or (roll is None)
        is_targeted = brain.target_npc and brain.target_npc == npc.id

        if is_dialog:
            if is_targeted or brain.target_npc:
                template = templates.get("dialog", "scene {scene}: conversation with {npc}")
            else:
                template = templates.get("dialog_no_target", "scene {scene}: conversation — {intent}")
        elif is_targeted:
            template = templates.get(
                "action_targeted", "scene {scene}: {player} {move_verb} involving {npc} — {result_text}"
            )
        else:
            template = templates.get("action", "scene {scene}: {player} {move_verb} — {result_text}")

        event_text = template.format(
            scene=scene,
            player=game.player_name,
            npc=npc.name,
            intent=intent[:80] if intent else "general",
            move_verb=move_verb,
            result_text=result_text,
            move=move,
            consequences=", ".join(consequences[:3]) if consequences else "",
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
    """Engine-generated scene_context from mechanical context. Replaces AI-generated version."""
    _e = eng()
    move = brain.move
    location = game.world.current_location or "unknown"
    npc_summary = ", ".join(activated_npc_names[:3]) if activated_npc_names else "no one nearby"

    if move == "dialog" or roll is None:
        template = _e.get_raw("scene_context_dialog", "conversation at {location} with {npc_summary}")
        return template.format(location=location, npc_summary=npc_summary)

    result = roll.result if roll else "MISS"
    move_label = _e.get_raw("memory_move_verbs", {}).get(move, move)
    template = _e.get_raw("scene_context_template", "{result} on {move_label} at {location} — {npc_summary}")
    return template.format(
        result=result,
        move_label=move_label,
        location=location,
        npc_summary=npc_summary,
    )
