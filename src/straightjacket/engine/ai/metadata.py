#!/usr/bin/env python3
"""AI metadata processing: apply narrator metadata and NPC death tracking."""

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
    game: GameState, metadata: dict, scene_present_ids: set | None = None, world_addition: str = ""
) -> None:
    """Apply structured metadata from the metadata extractor to game state.

    After step 3: engine handles location, time, scene_context, and memories
    (via apply_brain_location_time, generate_engine_memories, generate_scene_context).
    AI metadata extractor handles only NPC detection from free narrator text:
    new_npcs, npc_renames, npc_details, deceased_npcs, lore_npcs.

    scene_present_ids: set of NPC IDs that were activated/present in the scene.
    world_addition: Brain's world_addition text, passed through to process_npc_details
    as description fallback for rejected identity reveals."""

    # NPC renames
    renames = metadata.get("npc_renames", [])
    if renames:
        process_npc_renames(game, renames)

    # New NPCs
    new_npcs = metadata.get("new_npcs", [])
    if new_npcs:
        process_new_npcs(game, new_npcs)

    # NPC details (sanitize nulls → empty strings before delegation)
    details = metadata.get("npc_details", [])
    if details:
        for d in details:
            if d.get("full_name") is None:
                d["full_name"] = ""
            if d.get("description") is None:
                d["description"] = ""
        process_npc_details(game, details, world_addition=world_addition)

    # Deceased NPCs (process BEFORE lore NPCs)
    deceased = metadata.get("deceased_npcs", [])
    if deceased:
        process_deceased_npcs(game, deceased, scene_present_ids=scene_present_ids)

    # Lore NPCs — historically significant but never physically present
    lore_npcs = metadata.get("lore_npcs", [])
    if lore_npcs:
        _process_lore_npcs(game, lore_npcs)

    # Off-screen death detection via cross-NPC memory voting
    _check_death_corroboration(game)


def process_deceased_npcs(game: GameState, deceased_list: list, scene_present_ids: set | None = None) -> None:
    """Mark NPCs as deceased based on metadata extractor report.
    Sets status='deceased' — this excludes them from all active processing:
    prompts, memories, reflections, sidebar, reactivation.
    If scene_present_ids is provided, only NPCs that were activated in this scene
    (or introduced mid-scene via new_npcs) can be marked deceased. This prevents
    false positives from dialog claims (e.g. an NPC saying 'Leo is dead')."""
    for entry in deceased_list:
        npc_id = entry.get("npc_id", "")
        if not npc_id:
            continue
        npc = find_npc(game, npc_id)
        if not npc:
            log(f"[NPC] Deceased report for unknown NPC: '{npc_id}'", level="warning")
            continue
        if npc.status == "deceased":
            continue  # Already marked
        # Presence guard: NPC must have been in-scene to die on-screen
        if scene_present_ids is not None and npc.id not in scene_present_ids:
            # Allow if NPC was just introduced this scene (walk-in + die edge case)
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
    """Create lore NPCs — historically significant, never physically present.
    Skips duplicates of existing NPCs. Lore NPCs can receive memories
    but are never activated in prompts or shown as present."""
    for entry in lore_list:
        name = entry.get("name", "").strip()
        if not name:
            continue
        # Skip if already known (any status)
        existing = find_npc(game, name)
        if existing:
            continue
        # Also check fuzzy match
        fuzzy, _ = fuzzy_match_existing_npc(game, name)
        if fuzzy:
            continue
        npc_id, _ = next_npc_id(game)
        npc = NpcData(
            id=npc_id,
            name=name,
            description=entry.get("description", ""),
            status="lore",
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)
        log(f"[NPC] Lore figure created: {name} ({npc_id})")


def _death_emotions() -> set[str]:
    """Emotional weights that signal death-level trauma. Loaded from engine.yaml."""
    return set(eng().death_emotions)


def _check_death_corroboration(game: GameState) -> None:
    """Fallback off-screen death detection via cross-NPC memory voting.

    The primary deceased_npcs extractor requires a physically-witnessed death.
    This catches off-screen deaths described as narrative fact — the NPC
    remained active because no one saw it happen.

    Two independent signal types from observation memories written THIS scene:
      1. Cross-NPC vote: another NPC's memory with about_npc=X, importance>=9,
         and emotional_weight in {betrayed, devastated}.
      2. Self-vote: NPC X's own memory with importance>=9 and
         emotional_weight == "devastated".

    Threshold: at least 1 cross-NPC vote AND total votes >= 2.
    This prevents false positives from single traumatic-but-non-lethal events.
    Reflections are excluded — they are Director-generated.
    """
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

        # Scan all OTHER NPCs' memories for cross-votes about this NPC
        for other in game.npcs:
            if other.id == npc_id:
                continue
            for mem in other.memory:
                if mem.type == "reflection":
                    continue  # Exclude Director-generated
                if mem.scene != current_scene:
                    continue
                if (
                    mem.about_npc == npc_id
                    and mem.importance >= min_importance
                    and mem.emotional_weight.lower() in _death_emotions()
                ):
                    cross_votes += 1

        # Scan this NPC's own memories for self-votes
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
