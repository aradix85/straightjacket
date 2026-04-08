#!/usr/bin/env python3
"""NPC lifecycle: creation, identity merging, renaming, retiring, reactivating,
description-based dedup, duplicate absorption."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import GameState


from ..emotions_loader import normalize_disposition as _yaml_normalize_disposition
from ..engine_loader import eng
from ..logging_util import log
from ..models import NpcData
from .matching import (
    normalize_for_match,
    sanitize_npc_name,
)

# DISPOSITION NORMALIZATION


def normalize_disposition(raw: str) -> str:
    """Normalize any AI-generated disposition to one of the 5 canonical values."""
    return _yaml_normalize_disposition(raw)


def normalize_npc_dispositions(npcs: list) -> None:
    """Normalize all NPC dispositions in-place to canonical values."""
    for n in npcs:
        if n.disposition:
            n.disposition = normalize_disposition(n.disposition)


_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "was",
        "are",
        "has",
        "had",
        "not",
        "but",
        "his",
        "her",
        "its",
        "who",
        "whom",
        "will",
        "can",
        "may",
        "been",
        "were",
        "into",
        "than",
        "then",
    }
)

# RETIRE / REACTIVATE


def retire_distant_npcs(game: "GameState", max_active: int | None = None):
    """Demote NPCs to 'background' if the active list exceeds the threshold.
    Background NPCs remain visible in the sidebar but are excluded from
    AI prompts and NPC agency checks to keep token budgets manageable."""
    if max_active is None:
        max_active = eng().npc.max_active
    active = [n for n in game.npcs if n.status == "active"]
    if len(active) <= max_active:
        return

    def relevance(npc):
        last_scene = max((m.scene for m in npc.memory), default=0) or 0
        score = last_scene + npc.bond * 3
        if not npc.memory or last_scene >= game.narrative.scene_count:
            score += 1000
        return score

    active.sort(key=relevance)
    to_demote = len(active) - max_active
    for npc in active[:to_demote]:
        npc.status = "background"
        log(f"[NPC] Demoted to background: {npc.name}")


def reactivate_npc(npc: NpcData, reason: str = "", force: bool = False):
    """Promote a background (or deceased with force=True) NPC back to active status.
    force=True enables resurrection of deceased NPCs (exact name match in narration)."""
    if npc.status == "deceased":
        if force:
            npc.status = "active"
            log(f"[NPC] Resurrected deceased NPC: {npc.name} (reason: {reason})")
        else:
            log(f"[NPC] Refused reactivation of deceased NPC: {npc.name}")
        return
    if npc.status == "background":
        npc.status = "active"
        log(f"[NPC] Reactivated: {npc.name} (reason: {reason})")


# IDENTITY MERGING


def merge_npc_identity(existing: NpcData, new_name: str, new_desc: str = "", game: "GameState | None" = None) -> None:
    """Merge a new identity into an existing NPC (identity reveal).
    Old name becomes an alias, new name becomes primary.
    Pass game to also update any clock whose owner string matches the old name."""
    old_name = existing.name
    new_name = new_name.strip()
    clean_name, extra_aliases = sanitize_npc_name(new_name)
    new_name = clean_name
    if normalize_for_match(old_name) == normalize_for_match(new_name):
        log(f"[NPC] Identity merge skipped: '{old_name}' → '{new_name}' (same name)")
        return
    old_norm = normalize_for_match(old_name)
    if old_name and old_norm not in {normalize_for_match(a) for a in existing.aliases}:
        existing.aliases.append(old_name)
    existing.name = new_name
    new_norm = normalize_for_match(new_name)
    existing.aliases = [a for a in existing.aliases if normalize_for_match(a) != new_norm]
    for alias in extra_aliases:
        if (
            normalize_for_match(alias) not in {normalize_for_match(a) for a in existing.aliases}
            and normalize_for_match(alias) != new_norm
        ):
            existing.aliases.append(alias)
    if new_desc and not existing.description:
        existing.description = new_desc
    if existing.status in ("background", "lore"):
        reactivate_npc(existing, reason=f"identity revealed as {new_name}")
    # Update any clock whose owner string still carries the old name
    if game is not None:
        old_name_norm = normalize_for_match(old_name)
        for clock in game.world.clocks:
            if normalize_for_match(clock.owner) == old_name_norm:
                old_owner = clock.owner
                clock.owner = new_name
                log(f"[Clock] Owner updated on NPC rename: '{clock.name}' '{old_owner}' → '{new_name}'")
    log(f"[NPC] Identity merged: '{old_name}' → '{new_name}' (aliases: {existing.aliases})")


def is_complete_description(desc: str) -> bool:
    """Check if a description looks complete (not truncated mid-sentence)."""
    if not desc or len(desc) < 10:
        return False
    return desc.rstrip().endswith((".", "!", "?", '"', "»", "«", "…", ")", "–", "—"))


def sanitize_aliases(npc: NpcData) -> None:
    """Remove duplicate and descriptor-style aliases from an NPC."""
    name = npc.name
    aliases = npc.aliases
    if not aliases:
        return
    seen = set()
    clean = []
    for a in aliases:
        a_stripped = a.strip()
        low = a_stripped.lower()
        if not a_stripped or low in seen or low == name.lower():
            continue
        if len(a_stripped.split()) > 4:
            continue
        seen.add(low)
        clean.append(a_stripped)
    npc.aliases = clean


def absorb_duplicate_npc(game: "GameState", original: NpcData, merged_name: str):
    """After an identity reveal renames an NPC, check if a duplicate with the
    new name was already created by process_new_npcs earlier in the same
    metadata cycle. If found, absorb its data and remove the duplicate.

    Matches by both primary name and aliases. If dup is richer (more memories,
    agenda, instinct, bond), its substantive fields overwrite original's."""
    merged_norm = normalize_for_match(merged_name)
    for dup in game.npcs:
        if dup is original or dup.id == original.id:
            continue
        dup_name_norm = normalize_for_match(dup.name)
        dup_alias_norms = {normalize_for_match(a) for a in dup.aliases}
        if not (dup_name_norm == merged_norm or merged_norm in dup_alias_norms):
            continue

        dup_id = dup.id
        dup_mems = dup.memory

        # Determine which is the richer, more established character.
        def _richness(n):
            return len(n.memory) * 2 + bool(n.agenda) * 3 + bool(n.instinct) * 3 + n.bond * 2 + bool(n.description) * 1

        dup_richer = _richness(dup) > _richness(original)

        # Transfer memories (always combine both sets)
        original.memory.extend(dup_mems)
        original.importance_accumulator = original.importance_accumulator + dup.importance_accumulator

        if dup_richer:
            # Dup is established — its substantive fields win
            if dup.description:
                original.description = dup.description
            if dup.agenda:
                original.agenda = dup.agenda
            if dup.instinct:
                original.instinct = dup.instinct
            if dup.bond > original.bond:
                original.bond = dup.bond
            if dup.disposition and dup.disposition != "neutral":
                original.disposition = dup.disposition
            if dup.last_location:
                original.last_location = dup.last_location
            if dup.secrets:
                original.secrets.extend(s for s in dup.secrets if s not in original.secrets)
            if dup.last_reflection_scene > original.last_reflection_scene:
                original.last_reflection_scene = dup.last_reflection_scene
            if dup.needs_reflection:
                original.needs_reflection = True
            log(
                f"[NPC] Absorb: dup '{dup.name}' ({dup_id}) was richer — "
                f"its fields promoted into original '{original.name}' ({original.id})"
            )
        else:
            # Original is established — only fill empty fields from dup
            if not original.description and dup.description:
                original.description = dup.description
            if not original.agenda and dup.agenda:
                original.agenda = dup.agenda
            if not original.instinct and dup.instinct:
                original.instinct = dup.instinct

        existing_norms = {normalize_for_match(a) for a in original.aliases}
        for alias in dup.aliases:
            if normalize_for_match(alias) not in existing_norms and normalize_for_match(alias) != merged_norm:
                original.aliases.append(alias)
        if dup.last_location and not original.last_location:
            original.last_location = dup.last_location

        game.npcs.remove(dup)
        log(
            f"[NPC] Absorbed duplicate '{dup.name}' ({dup_id}) "
            f"into '{original.name}' ({original.id}): "
            f"{len(dup_mems)} memories transferred"
        )
        sanitize_aliases(original)
        from .memory import consolidate_memory

        consolidate_memory(original)
        break


# DESCRIPTION-BASED MATCHING


def description_match_existing_npc(game: "GameState", new_desc: str, new_name_norm: str) -> NpcData | None:
    """Check if a new NPC's description closely matches an existing NPC's description.
    Catches identity reveals where names share zero words but the character
    is clearly the same. Returns the matching NPC dict or None.
    new_name_norm should be pre-normalized via normalize_for_match."""
    from ..mechanics import locations_match

    if not new_desc or len(new_desc) < 10:
        return None

    new_words = {w.strip(".,;:!?\"'()-").lower() for w in new_desc.split() if len(w.strip(".,;:!?\"'()-")) >= 4}
    new_words -= _STOPWORDS

    # Name-Reference Guard: strip words from the candidate NPC's own
    # name/aliases out of the new description's word set.
    candidate_name_words = {
        w.strip(".,;:!?\"'()-").lower() for w in new_name_norm.split() if len(w.strip(".,;:!?\"'()-")) >= 4
    }
    new_words -= candidate_name_words

    if len(new_words) < 2:
        return None

    best_match = None
    best_score: float = 0

    for n in game.npcs:
        if n.status not in ("active", "background", "lore"):
            continue
        if normalize_for_match(n.name) == new_name_norm:
            continue
        # Spatial guard: different location = can't be the same person
        npc_loc = n.last_location.strip()
        current_loc = (game.world.current_location or "").strip()
        if npc_loc and current_loc and not locations_match(npc_loc, current_loc):
            continue

        existing_desc = n.description
        if not existing_desc:
            continue

        existing_words = {
            w.strip(".,;:!?\"'()-").lower() for w in existing_desc.split() if len(w.strip(".,;:!?\"'()-")) >= 4
        }
        existing_words -= _STOPWORDS

        exact_overlap = new_words & existing_words
        substring_matches = set()
        for nw in new_words - exact_overlap:
            for ew in existing_words - exact_overlap:
                if len(nw) >= 5 and len(ew) >= 5:
                    if nw in ew or ew in nw:
                        substring_matches.add(nw)
                        break
                    nw_parts = set(p for p in nw.split("-") if len(p) >= 4)
                    ew_parts = set(p for p in ew.split("-") if len(p) >= 4)
                    if nw_parts & ew_parts:
                        substring_matches.add(nw)
                        break

        long_exact = sum(1 for w in exact_overlap if len(w) >= 12)
        effective_overlap: float = len(exact_overlap) + long_exact * 0.5 + len(substring_matches) * 0.5
        if effective_overlap < 2.0:
            continue

        min_set_size = min(len(new_words), len(existing_words))
        overlap_ratio = effective_overlap / max(min_set_size, 1)
        has_long_match = any(len(w) >= 12 for w in exact_overlap)

        meets_threshold = (overlap_ratio >= 0.25 and effective_overlap >= 2.0) or (
            has_long_match and effective_overlap >= 2.0
        )

        if meets_threshold and effective_overlap > best_score:
            best_score = effective_overlap
            best_match = n
            log(
                f"[NPC] Description match candidate: new='{new_desc[:50]}' ~ "
                f"existing='{n.name}' desc='{existing_desc[:50]}' "
                f"(exact={exact_overlap}, substr={substring_matches}, "
                f"effective={effective_overlap:.1f}, ratio={overlap_ratio:.1%})"
            )

    return best_match
