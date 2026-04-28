from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, NpcData
from ..npc import (
    apply_name_sanitization,
    find_npc,
    fuzzy_match_existing_npc,
    next_npc_id,
    process_new_npcs,
    process_npc_details,
    process_npc_renames,
)


def apply_narrator_metadata(
    game: GameState, metadata: dict, *, scene_present_ids: set[str], world_addition: str
) -> None:
    renames = metadata["npc_renames"]
    if renames:
        process_npc_renames(game, renames)

    new_npcs = metadata["new_npcs"]
    if new_npcs:
        process_new_npcs(game, new_npcs)

    details = metadata["npc_details"]
    if details:
        for d in details:
            if d["full_name"] is None:
                d["full_name"] = ""
            if d["description"] is None:
                d["description"] = ""
        process_npc_details(game, details, world_addition=world_addition)

    deceased = metadata["deceased_npcs"]
    if deceased:
        process_deceased_npcs_with_presence_check(game, deceased, scene_present_ids=scene_present_ids)

    lore_npcs = metadata["lore_npcs"]
    if lore_npcs:
        _process_lore_npcs(game, lore_npcs)

    _check_death_corroboration(game)


def process_deceased_npcs(game: GameState, deceased_list: list) -> None:
    for entry in deceased_list:
        npc_id = entry["npc_id"]
        if not npc_id:
            continue
        npc = find_npc(game, npc_id)
        if not npc:
            log(f"[NPC] Deceased report for unknown NPC: '{npc_id}'", level="warning")
            continue
        if npc.status == "deceased":
            continue
        old_status = npc.status
        npc.status = "deceased"
        log(f"[NPC] Marked as deceased: {npc.name} ({npc.id}, was {old_status})")


def process_deceased_npcs_with_presence_check(
    game: GameState, deceased_list: list, scene_present_ids: set[str]
) -> None:
    for entry in deceased_list:
        npc_id = entry["npc_id"]
        if not npc_id:
            continue
        npc = find_npc(game, npc_id)
        if not npc:
            log(f"[NPC] Deceased report for unknown NPC: '{npc_id}'", level="warning")
            continue
        if npc.status == "deceased":
            continue
        if npc.id not in scene_present_ids:
            has_current_scene_memory = any(m.scene == game.narrative.scene_count for m in npc.memory)
            if not has_current_scene_memory:
                log(
                    f"[NPC] Deceased report REJECTED for '{npc.name}' — "
                    f"not present in scene {game.narrative.scene_count} (likely a dialog claim)",
                    level="warning",
                )
                continue
        old_status = npc.status
        npc.status = "deceased"
        log(f"[NPC] Marked as deceased: {npc.name} ({npc.id}, was {old_status})")


def _process_lore_npcs(game: GameState, lore_list: list) -> None:
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
        npc_id, _ = next_npc_id(game)

        npc = NpcData(
            id=npc_id,
            name=name,
            description=entry["description"],
            disposition="neutral",
            status="lore",
            introduced=False,
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)
        log(f"[NPC] Lore figure created: {name} ({npc_id})")


def _death_emotions() -> set[str]:
    return set(eng().death_emotions)


def _check_death_corroboration(game: GameState) -> None:
    current_scene = game.narrative.scene_count

    for npc in game.npcs:
        if npc.status != "active":
            continue
        npc_id = npc.id
        if not npc_id:
            continue

        cross_votes = 0
        self_votes = 0

        min_importance = eng().npc.death_corroboration_min_importance

        for other in game.npcs:
            if other.id == npc_id:
                continue
            for mem in other.memory:
                if mem.type == "reflection":
                    continue
                if mem.scene != current_scene:
                    continue
                if (
                    mem.about_npc == npc_id
                    and mem.importance >= min_importance
                    and mem.emotional_weight.lower() in _death_emotions()
                ):
                    cross_votes += 1

        for mem in npc.memory:
            if mem.type == "reflection":
                continue
            if mem.scene != current_scene:
                continue
            if mem.importance >= min_importance and mem.emotional_weight.lower() in _death_emotions():
                self_votes += 1

        total = cross_votes + self_votes
        voting = eng().metadata_voting
        if cross_votes >= voting.min_cross_votes and total >= voting.min_total_votes:
            npc.status = "deceased"
            log(
                f"[NPC] Off-screen death detected: {npc.name} ({npc_id}) — "
                f"cv={cross_votes} sv={self_votes} total={total}"
            )
