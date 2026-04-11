#!/usr/bin/env python3
"""NPC metadata processing: create, rename, and update NPCs from narrator output."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import GameState

from ..engine_loader import eng
from ..logging_util import log
from ..models import MemoryEntry, NpcData
from .lifecycle import (
    absorb_duplicate_npc,
    description_match_existing_npc,
    is_complete_description,
    merge_npc_identity,
    normalize_disposition,
    reactivate_npc,
    retire_distant_npcs,
)
from .matching import (
    find_npc,
    fuzzy_match_existing_npc,
    next_npc_id,
    normalize_for_match,
    sanitize_npc_name,
)
from .memory import score_importance


def process_npc_renames(game: "GameState", renames: list) -> None:
    """Process NPC rename/identity-reveal metadata."""
    for r in renames:
        if not isinstance(r, dict) or not r.get("new_name"):
            continue
        npc = find_npc(game, r.get("npc_id", ""))
        if not npc and r.get("old_name"):
            npc = find_npc(game, r["old_name"])
        if not npc:
            log(
                f"[NPC] Rename failed: could not find NPC '{r.get('npc_id', '')}' / '{r.get('old_name', '')}'",
                level="warning",
            )
            continue
        if npc.status == "deceased":
            log(f"[NPC] Rename skipped for deceased NPC: {npc.name}")
            continue
        new_name = r["new_name"].strip()
        new_norm = normalize_for_match(new_name)
        player_norm = normalize_for_match(game.player_name)
        if new_norm == player_norm or (set(new_norm.split()) & set(player_norm.split())):
            log(f"[NPC] Rename rejected: '{new_name}' matches player character")
            continue
        merge_npc_identity(npc, new_name, r.get("description", ""), game=game)
        absorb_duplicate_npc(game, npc, new_name)


def process_npc_details(game: "GameState", details: list, world_addition: str = "") -> None:
    """Process NPC detail updates from narrator metadata.
    Captures invented surnames, description changes, or other facts the narrator
    established for known NPCs.
    world_addition: Brain's world_addition text, used as description fallback when
    the guard rejects an identity reveal and creates a stub with no description."""
    for d in details:
        if not isinstance(d, dict):
            continue
        npc = find_npc(game, d.get("npc_id", ""))
        if not npc:
            log(f"[NPC] npc_details: could not find NPC '{d.get('npc_id', '')}'", level="warning")
            continue

        new_name = d.get("full_name", "").strip()
        if new_name:
            new_name, paren_aliases = sanitize_npc_name(new_name)
        else:
            paren_aliases = []
        if new_name and new_name != npc.name:
            old_name = npc.name
            old_norm = normalize_for_match(old_name)
            new_norm_d = normalize_for_match(new_name)
            if old_norm in new_norm_d or new_norm_d in old_norm:
                existing_norms = {normalize_for_match(a) for a in npc.aliases}
                if old_name and normalize_for_match(old_name) not in existing_norms:
                    npc.aliases.append(old_name)
                npc.name = new_name
                npc.aliases = [a for a in npc.aliases if normalize_for_match(a) != new_norm_d]
                for alias in paren_aliases:
                    if (
                        normalize_for_match(alias) not in {normalize_for_match(a) for a in npc.aliases}
                        and normalize_for_match(alias) != new_norm_d
                    ):
                        npc.aliases.append(alias)
                log(f"[NPC] Details update: '{old_name}' -> '{new_name}' (surname established)")
            else:
                # Memory guard: an NPC with memories is an established character.
                # If zero word overlap between old name+aliases and new name,
                # the Brain has almost certainly confused two distinct characters.
                has_memories = bool(npc.memory)
                if has_memories:
                    known_words = set(normalize_for_match(old_name).split())
                    for a in npc.aliases:
                        known_words |= set(normalize_for_match(a).split())
                    new_name_words = set(normalize_for_match(new_name).split())
                    if not (new_name_words & known_words):
                        log(
                            f"[NPC] npc_details: REJECTED identity reveal "
                            f"'{old_name}' → '{new_name}': NPC has memories and "
                            f"zero word overlap — creating stub instead",
                            level="warning",
                        )
                        if not find_npc(game, new_name):
                            stub_desc = d.get("description", "").strip()
                            if not stub_desc and world_addition:
                                stub_desc = world_addition.strip()
                            npc_id, _ = next_npc_id(game)
                            stub = NpcData(
                                id=npc_id,
                                name=new_name,
                                description=stub_desc,
                                disposition=normalize_disposition("neutral"),
                                bond=eng().bonds.start,
                                bond_max=eng().bonds.max,
                                aliases=paren_aliases,
                                last_location=game.world.current_location or "",
                            )
                            game.npcs.append(stub)
                            log(f"[NPC] Created stub for rejected reveal: {new_name} ({npc_id})")
                        continue
                log(f"[NPC] npc_details: treating '{old_name}' -> '{new_name}' as identity reveal")
                merge_npc_identity(npc, new_name, game=game)
                absorb_duplicate_npc(game, npc, new_name)

        new_desc = d.get("description", "").strip()
        if new_desc:
            old_desc = npc.description
            if is_complete_description(new_desc) or not old_desc:
                npc.description = new_desc
                log(f"[NPC] Description updated for {npc.name}: '{old_desc[:50]}' -> '{new_desc[:50]}'")
            else:
                log(f"[NPC] Rejected truncated description for {npc.name}: '{new_desc[:60]}' -- keeping existing")
        extra = d.get("details", "").strip()
        if extra and extra not in (npc.description or ""):
            existing = npc.description
            if existing:
                npc.description = f"{existing}. {extra}"
            else:
                npc.description = extra
            log(f"[NPC] Details enriched for {npc.name}: {extra[:80]}")


def process_new_npcs(game: "GameState", new_npcs: list) -> None:
    """Add newly discovered NPCs from narrator metadata."""
    player_norm = normalize_for_match(game.player_name)
    player_parts = set(player_norm.split())
    existing_names = {normalize_for_match(n.name) for n in game.npcs}

    for nd in new_npcs:
        if not isinstance(nd, dict) or not nd.get("name"):
            continue
        name_norm = normalize_for_match(nd["name"])

        name_parts = set(name_norm.split())
        if name_norm == player_norm or (name_parts & player_parts):
            log(f"[NPC] Skipping player character from new_npcs: '{nd['name']}'")
            continue

        if name_norm in existing_names:
            existing = next((n for n in game.npcs if normalize_for_match(n.name) == name_norm), None)
            if existing and existing.status in ("background", "lore"):
                reactivate_npc(existing, reason="reappeared in new_npcs")
            elif existing and existing.status == "deceased":
                reactivate_npc(existing, reason="resurrected -- exact name in new_npcs", force=True)
            continue

        fuzzy_hit, match_type = fuzzy_match_existing_npc(game, nd["name"])
        if fuzzy_hit:
            if fuzzy_hit.status == "deceased":
                log(f"[NPC] Fuzzy matched '{nd['name']}' to deceased '{fuzzy_hit.name}' -- creating new NPC instead")
                fuzzy_hit = None
            else:
                if match_type == "stt_variant":
                    variant = nd["name"].strip()
                    if normalize_for_match(variant) not in {normalize_for_match(a) for a in fuzzy_hit.aliases}:
                        fuzzy_hit.aliases.append(variant)
                        log(f"[NPC] Added STT variant as alias: '{variant}' -> '{fuzzy_hit.name}'")
                    if fuzzy_hit.status in ("background", "lore"):
                        reactivate_npc(fuzzy_hit, reason="STT variant reappeared")
                else:
                    merge_npc_identity(fuzzy_hit, nd["name"], nd.get("description", ""), game=game)
                existing_names.add(name_norm)
                continue

        new_desc = nd.get("description", "")
        if new_desc and len(new_desc) >= 10:
            desc_hit = description_match_existing_npc(game, new_desc, name_norm)
            if desc_hit:
                if desc_hit.status == "deceased":
                    log(
                        f"[NPC] Description matched '{nd['name']}' to deceased "
                        f"'{desc_hit.name}' -- creating new NPC instead"
                    )
                else:
                    log(
                        f"[NPC] Description-based dedup: '{nd['name']}' matches "
                        f"'{desc_hit.name}' -- treating as identity reveal"
                    )
                    merge_npc_identity(desc_hit, nd["name"], new_desc, game=game)
                    existing_names.add(name_norm)
                    continue

        npc_id, _ = next_npc_id(game)
        clean_name, paren_aliases = sanitize_npc_name(nd["name"].strip())

        npc = NpcData(
            id=npc_id,
            name=clean_name,
            description=nd.get("description", "").strip(),
            disposition=normalize_disposition(nd.get("disposition", "neutral")),
            bond=eng().bonds.start,
            bond_max=eng().bonds.max,
            aliases=paren_aliases,
            last_location=game.world.current_location or "",
        )

        game.npcs.append(npc)
        existing_names.add(name_norm)
        log(f"[NPC] New mid-game NPC: {npc.name} ({npc_id}, {npc.disposition})")

        seed_event = nd.get("description", "") or f"{npc.name} appeared"
        seed_emotion = normalize_disposition(nd.get("disposition", "neutral"))
        disp_to_emotion = dict(eng().disposition_to_seed_emotion.items())
        seed_emotion = disp_to_emotion.get(seed_emotion, "neutral")
        seed_imp, seed_debug = score_importance(seed_emotion, seed_event, debug=True)
        seed_imp = max(seed_imp, eng().npc.seed_importance_floor)
        npc.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=seed_event,
                emotional_weight=seed_emotion,
                importance=seed_imp,
                type="observation",
                _score_debug=f"auto-seed from new_npcs | {seed_debug}",
            )
        )

    retire_distant_npcs(game)
