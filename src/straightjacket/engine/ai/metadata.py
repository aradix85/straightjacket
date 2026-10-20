from typing import Any

from ..gamemaster.config import gm
from ..gamemaster.npc.lifecycle import new_npc
from ..gamemaster.npc.matching import apply_name_sanitization, find_npc, fuzzy_match_existing_npc, next_npc_id
from ..gamemaster.npc.processing import process_new_npcs, process_npc_details, process_npc_renames
from ..logging_util import log
from ..models import GameState, NpcData


def apply_narrator_metadata(
    game: GameState, metadata: dict[str, Any], *, scene_present_ids: set[str], world_addition: str
) -> None:
    process_npc_renames(game, metadata["npc_renames"])
    if metadata["new_npcs"]:
        process_new_npcs(game, metadata["new_npcs"])
    process_npc_details(game, metadata["npc_details"], world_addition=world_addition)
    process_deceased_npcs_with_presence_check(game, metadata["deceased_npcs"], scene_present_ids=scene_present_ids)
    _process_lore_npcs(game, metadata["lore_npcs"])


def _reported_dead(game: GameState, entry: dict[str, Any]) -> NpcData | None:
    npc_id = entry["npc_id"]
    if not npc_id:
        return None
    npc = find_npc(game, npc_id)
    if not npc:
        log(f"[NPC] Deceased report for unknown NPC: '{npc_id}'", level="warning")
        return None
    if npc.status == "deceased":
        return None
    return npc


def _mark_deceased(npc: NpcData) -> None:
    old_status = npc.status
    npc.status = "deceased"
    log(f"[NPC] Marked as deceased: {npc.name} ({npc.id}, was {old_status})")


def process_deceased_npcs(game: GameState, deceased_list: list[Any]) -> None:
    for entry in deceased_list:
        npc = _reported_dead(game, entry)
        if npc is not None:
            _mark_deceased(npc)


def process_deceased_npcs_with_presence_check(
    game: GameState, deceased_list: list[Any], scene_present_ids: set[str]
) -> None:
    for entry in deceased_list:
        npc = _reported_dead(game, entry)
        if npc is None:
            continue
        if npc.id not in scene_present_ids and not any(m.scene == game.narrative.scene_count for m in npc.memory):
            log(
                f"[NPC] Deceased report REJECTED for '{npc.name}' — "
                f"not present in scene {game.narrative.scene_count} (likely a dialog claim)",
                level="warning",
            )
            continue
        _mark_deceased(npc)


def _process_lore_npcs(game: GameState, lore_list: list[Any]) -> None:
    for entry in lore_list:
        name = entry["name"].strip()
        if not name:
            continue

        existing = find_npc(game, name)
        if existing:
            continue

        fuzzy, _ = fuzzy_match_existing_npc(game, name)
        if fuzzy:
            continue
        npc_id = next_npc_id(game)

        npc = new_npc(
            id=npc_id,
            name=name,
            disposition=gm().npc.default_new_npc_disposition,
            status="lore",
            name_rolled=False,
            description=entry["description"],
            agenda="",
            instinct="",
            secrets=[],
            aliases=[],
            last_location="",
            introduced=False,
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)
        log(f"[NPC] Lore figure created: {name} ({npc_id})")
