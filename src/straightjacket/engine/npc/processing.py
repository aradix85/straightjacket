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
from .naming import roll_oracle_name


def process_npc_renames(game: "GameState", renames: list) -> None:
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


def _apply_surname_update(npc: NpcData, new_name: str, paren_aliases: list[str]) -> None:
    old_name = npc.name
    new_norm = normalize_for_match(new_name)
    existing_norms = {normalize_for_match(a) for a in npc.aliases}
    if old_name and normalize_for_match(old_name) not in existing_norms:
        npc.aliases.append(old_name)
    npc.name = new_name
    npc.aliases = [a for a in npc.aliases if normalize_for_match(a) != new_norm]
    for alias in paren_aliases:
        alias_norm = normalize_for_match(alias)
        if alias_norm not in {normalize_for_match(a) for a in npc.aliases} and alias_norm != new_norm:
            npc.aliases.append(alias)
    log(f"[NPC] Details update: '{old_name}' -> '{new_name}' (surname established)")


def _should_reject_identity_reveal(npc: NpcData, new_name: str) -> bool:
    if not npc.memory:
        return False
    known_words: set[str] = set(normalize_for_match(npc.name).split())
    for a in npc.aliases:
        known_words |= set(normalize_for_match(a).split())
    new_name_words = set(normalize_for_match(new_name).split())
    return not (new_name_words & known_words)


def _create_stub_for_rejected_reveal(
    game: "GameState", new_name: str, d: dict, world_addition: str, paren_aliases: list[str]
) -> None:
    if find_npc(game, new_name):
        return
    stub_desc = d.get("description", "").strip() or world_addition.strip()
    npc_id, _ = next_npc_id(game)
    stub = NpcData(
        id=npc_id,
        name=new_name,
        description=stub_desc,
        disposition=normalize_disposition("neutral"),
        status="active",
        aliases=paren_aliases,
        last_location=game.world.current_location or "",
        introduced=False,
    )
    game.npcs.append(stub)
    log(f"[NPC] Created stub for rejected reveal: {new_name} ({npc_id})")


def _apply_name_update(game: "GameState", npc: NpcData, d: dict, world_addition: str) -> bool:
    raw_name = d.get("full_name", "").strip()
    if not raw_name:
        return False
    new_name, paren_aliases = sanitize_npc_name(raw_name)
    if not new_name or new_name == npc.name:
        return False

    old_norm = normalize_for_match(npc.name)
    new_norm = normalize_for_match(new_name)

    if old_norm in new_norm or new_norm in old_norm:
        _apply_surname_update(npc, new_name, paren_aliases)
        return False

    if _should_reject_identity_reveal(npc, new_name):
        log(
            f"[NPC] npc_details: REJECTED identity reveal "
            f"'{npc.name}' → '{new_name}': NPC has memories and "
            f"zero word overlap — creating stub instead",
            level="warning",
        )
        _create_stub_for_rejected_reveal(game, new_name, d, world_addition, paren_aliases)
        return True

    log(f"[NPC] npc_details: treating '{npc.name}' -> '{new_name}' as identity reveal")
    merge_npc_identity(npc, new_name, game=game)
    absorb_duplicate_npc(game, npc, new_name)
    return False


def _apply_description_updates(npc: NpcData, d: dict) -> None:
    new_desc = d.get("description", "").strip()
    if new_desc:
        old_desc = npc.description
        if is_complete_description(new_desc) or not old_desc:
            npc.description = new_desc
            log(f"[NPC] Description updated for {npc.name}: '{old_desc[:50]}' -> '{new_desc[:50]}'")
        else:
            log(
                f"[NPC] Rejected truncated description for {npc.name}: "
                f"'{new_desc[: eng().truncations.log_short]}' -- keeping existing"
            )

    extra = d.get("details", "").strip()
    if extra and extra not in (npc.description or ""):
        existing = npc.description
        npc.description = f"{existing}. {extra}" if existing else extra
        log(f"[NPC] Details enriched for {npc.name}: {extra[: eng().truncations.log_medium]}")


def _process_one_npc_detail(game: "GameState", d: dict, world_addition: str) -> None:
    npc = find_npc(game, d.get("npc_id", ""))
    if not npc:
        log(f"[NPC] npc_details: could not find NPC '{d.get('npc_id', '')}'", level="warning")
        return

    skip_desc = _apply_name_update(game, npc, d, world_addition)
    if not skip_desc:
        _apply_description_updates(npc, d)


def process_npc_details(game: "GameState", details: list, world_addition: str = "") -> None:
    for d in details:
        if isinstance(d, dict):
            _process_one_npc_detail(game, d, world_addition)


def _normalize_new_npc_input(raw_nd: dict, default_disp: str) -> dict | None:
    if not isinstance(raw_nd, dict) or not raw_nd.get("name"):
        return None
    return {
        "name": raw_nd["name"],
        "description": (raw_nd.get("description") or "").strip(),
        "disposition": raw_nd.get("disposition") or default_disp,
    }


def _is_player_collision(name_norm: str, player_norm: str, player_parts: set[str]) -> bool:
    return name_norm == player_norm or bool(set(name_norm.split()) & player_parts)


def _handle_exact_name_match(game: "GameState", name_norm: str) -> bool:
    existing = next((n for n in game.npcs if normalize_for_match(n.name) == name_norm), None)
    if not existing:
        return False
    if existing.status in ("background", "lore"):
        reactivate_npc(existing, reason="reappeared in new_npcs")
    elif existing.status == "deceased":
        reactivate_npc(existing, reason="resurrected -- exact name in new_npcs", force=True)
    return True


def _handle_fuzzy_match(game: "GameState", nd: dict) -> bool:
    fuzzy_hit, match_type = fuzzy_match_existing_npc(game, nd["name"])
    if not fuzzy_hit:
        return False
    if fuzzy_hit.status == "deceased":
        log(f"[NPC] Fuzzy matched '{nd['name']}' to deceased '{fuzzy_hit.name}' -- creating new NPC instead")
        return False

    if match_type == "stt_variant":
        variant = nd["name"].strip()
        if normalize_for_match(variant) not in {normalize_for_match(a) for a in fuzzy_hit.aliases}:
            fuzzy_hit.aliases.append(variant)
            log(f"[NPC] Added STT variant as alias: '{variant}' -> '{fuzzy_hit.name}'")
        if fuzzy_hit.status in ("background", "lore"):
            reactivate_npc(fuzzy_hit, reason="STT variant reappeared")
    else:
        merge_npc_identity(fuzzy_hit, nd["name"], nd["description"], game=game)
    return True


def _handle_description_match(game: "GameState", nd: dict, name_norm: str) -> bool:
    new_desc = nd["description"]
    if not new_desc or len(new_desc) < 10:
        return False
    desc_hit = description_match_existing_npc(game, new_desc, name_norm)
    if not desc_hit:
        return False
    if desc_hit.status == "deceased":
        log(f"[NPC] Description matched '{nd['name']}' to deceased '{desc_hit.name}' -- creating new NPC instead")
        return False
    log(f"[NPC] Description-based dedup: '{nd['name']}' matches '{desc_hit.name}' -- treating as identity reveal")
    merge_npc_identity(desc_hit, nd["name"], new_desc, game=game)
    return True


def _create_new_npc(game: "GameState", nd: dict) -> NpcData:
    npc_id, _ = next_npc_id(game)
    clean_name, paren_aliases = sanitize_npc_name(nd["name"].strip())

    oracle_name = roll_oracle_name(game)
    if oracle_name:
        ai_name = clean_name
        clean_name = oracle_name
        if ai_name and ai_name.lower() != oracle_name.lower():
            paren_aliases.append(ai_name)
        log(f"[NPC name] Oracle rolled '{oracle_name}' (AI: '{ai_name}')")

    npc = NpcData(
        id=npc_id,
        name=clean_name,
        description=nd["description"],
        disposition=normalize_disposition(nd["disposition"]),
        status="active",
        aliases=paren_aliases,
        last_location=game.world.current_location or "",
        introduced=True,
    )
    game.npcs.append(npc)
    log(f"[NPC] New mid-game NPC: {npc.name} ({npc_id}, {npc.disposition})")
    return npc


def _seed_initial_memory(game: "GameState", npc: NpcData, nd: dict) -> None:
    seed_event = nd["description"] or eng().ai_text.narrator_defaults["npc_appeared_event"].format(npc_name=npc.name)
    seed_disposition = normalize_disposition(nd["disposition"])
    disp_to_emotion = eng().get_raw("disposition_to_seed_emotion")
    seed_emotion = disp_to_emotion[seed_disposition]
    seed_imp, seed_debug = score_importance(seed_emotion, seed_event, debug=True)
    seed_imp = max(seed_imp, eng().npc.seed_importance_floor)
    npc.memory.append(
        MemoryEntry(
            scene=game.narrative.scene_count,
            event=seed_event,
            emotional_weight=seed_emotion,
            importance=seed_imp,
            type="observation",
            tone="",
            tone_key="",
            _score_debug=f"auto-seed from new_npcs | {seed_debug}",
        )
    )


def process_new_npcs(game: "GameState", new_npcs: list) -> None:
    player_norm = normalize_for_match(game.player_name)
    player_parts = set(player_norm.split())
    existing_names = {normalize_for_match(n.name) for n in game.npcs}
    default_disp = eng().npc.default_new_npc_disposition

    for raw_nd in new_npcs:
        nd = _normalize_new_npc_input(raw_nd, default_disp)
        if nd is None:
            continue

        name_norm = normalize_for_match(nd["name"])
        if _is_player_collision(name_norm, player_norm, player_parts):
            log(f"[NPC] Skipping player character from new_npcs: '{nd['name']}'")
            continue

        if name_norm in existing_names:
            _handle_exact_name_match(game, name_norm)
            continue

        if _handle_fuzzy_match(game, nd):
            existing_names.add(name_norm)
            continue

        if _handle_description_match(game, nd, name_norm):
            existing_names.add(name_norm)
            continue

        npc = _create_new_npc(game, nd)
        existing_names.add(name_norm)
        _seed_initial_memory(game, npc, nd)

    retire_distant_npcs(game)
