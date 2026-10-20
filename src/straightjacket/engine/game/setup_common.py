from typing import Any

from ..gamemaster.npc.lifecycle import new_npc
from ..gamemaster.npc.matching import (
    apply_name_sanitization,
    find_npc,
    fuzzy_match_existing_npc,
    named_in,
    next_npc_id,
)
from ..gamemaster.npc.memory import score_importance
from ..gamemaster.pacing import record_scene_intensity
from ..gamemaster.world import update_location
from ..logging_util import log
from ..models import GameState, MemoryEntry, NarrationEntry, SceneLogEntry


def register_extracted_npcs(game: GameState, npc_dicts: list[dict[str, Any]]) -> None:
    player_lower = game.player_name.lower().strip()

    for nd in npc_dicts:
        name = nd["name"].lower().strip()
        if not name or name == player_lower:
            continue
        known = find_npc(game, nd["name"]) or fuzzy_match_existing_npc(game, nd["name"])[0]
        if known is not None:
            log(f"[NPC] Extracted '{nd['name']}' is the known '{known.name}', not a new NPC")
            continue
        npc = new_npc(
            id=next_npc_id(game),
            name=nd["name"],
            disposition=nd["disposition"],
            status="active",
            name_rolled=False,
            description=nd["description"],
            agenda=nd["agenda"],
            instinct=nd["instinct"],
            secrets=list(nd["secrets"]),
            aliases=[],
            last_location=game.world.current_location,
            introduced=False,
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)

    game.npcs = [n for n in game.npcs if n.name.lower().strip() != player_lower]


def seed_opening_memories(game: GameState, memory_updates: list[dict[str, Any]]) -> None:
    for mu in memory_updates:
        target = find_npc(game, mu["npc_name"]) or next((n for n in game.npcs if named_in(n, mu["npc_name"])), None)
        if not target:
            continue
        event = mu["event"]
        emotional = mu["emotional_weight"]
        imp = score_importance(emotional, event)
        target.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=event,
                emotional_weight=emotional,
                importance=imp,
                type="observation",
                tone="",
                tone_key="",
                about_npc=None,
            )
        )
        target.importance_accumulator = target.importance_accumulator + imp


def apply_opening_setup(game: GameState, data: dict[str, Any], *, label: str) -> None:
    if data["npcs"]:
        known_ids = {n.id for n in game.npcs}
        register_extracted_npcs(game, data["npcs"])
        new_names = [n.name for n in game.npcs if n.id not in known_ids]
        log(f"[{label}] Registered {len(new_names)} new NPCs: {new_names}")

    seed_opening_memories(game, data["memory_updates"])

    if data["location"]:
        update_location(game, data["location"])

    if data["scene_context"]:
        game.world.current_scene_context = data["scene_context"]


def record_opening(game: GameState, narration: str, history_summary: str, log_summary: str) -> None:
    record_scene_intensity(game, "action")
    game.narrative.narration_history.append(
        NarrationEntry(scene=1, prompt_summary=history_summary, narration=narration)
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary=log_summary,
            move="",
            result="opening",
            position="",
            effect="",
            rich_summary="",
            oracle_answer="",
        )
    )
