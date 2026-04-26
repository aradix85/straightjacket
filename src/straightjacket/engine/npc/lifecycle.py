from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine_config_dataclasses import DescriptionDedupConfig
    from ..models import GameState


from ..emotions_loader import normalize_disposition
from ..engine_loader import eng
from ..logging_util import log
from ..models import NpcData
from .bond import get_npc_bond
from .matching import (
    normalize_for_match,
    sanitize_npc_name,
)
from .memory import consolidate_memory


def normalize_npc_dispositions(npcs: list) -> None:
    for n in npcs:
        if n.disposition:
            n.disposition = normalize_disposition(n.disposition)


def retire_distant_npcs(game: "GameState", max_active: int | None = None) -> None:
    if max_active is None:
        max_active = eng().npc.max_active
    active = [n for n in game.npcs if n.status == "active"]
    if len(active) <= max_active:
        return

    def relevance(npc: NpcData) -> int:
        last_scene = max((m.scene for m in npc.memory), default=0) or 0

        dd = eng().description_dedup
        score = last_scene + get_npc_bond(game, npc.id) * dd.bond_multiplier
        if not npc.memory or last_scene >= game.narrative.scene_count:
            score += dd.identity_score_delta
        return score

    active.sort(key=relevance)
    to_demote = len(active) - max_active
    for npc in active[:to_demote]:
        npc.status = "background"
        log(f"[NPC] Demoted to background: {npc.name}")


def reactivate_npc(npc: NpcData, reason: str = "", force: bool = False) -> None:
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


def merge_npc_identity(existing: NpcData, new_name: str, new_desc: str = "", game: "GameState | None" = None) -> None:
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

    if game is not None:
        old_name_norm = normalize_for_match(old_name)
        for clock in game.world.clocks:
            if normalize_for_match(clock.owner) == old_name_norm:
                old_owner = clock.owner
                clock.owner = new_name
                log(f"[Clock] Owner updated on NPC rename: '{clock.name}' '{old_owner}' → '{new_name}'")
    log(f"[NPC] Identity merged: '{old_name}' → '{new_name}' (aliases: {existing.aliases})")


def is_complete_description(desc: str) -> bool:
    if not desc or len(desc) < eng().fuzzy_match.description_match_min_length:
        return False
    return desc.rstrip().endswith((".", "!", "?", '"', "»", "«", "…", ")", "–", "—"))


def sanitize_aliases(npc: NpcData) -> None:
    name = npc.name
    aliases = npc.aliases
    if not aliases:
        return
    dd = eng().description_dedup
    seen = set()
    clean = []
    for a in aliases:
        a_stripped = a.strip()
        low = a_stripped.lower()
        if not a_stripped or low in seen or low == name.lower():
            continue
        if len(a_stripped.split()) > dd.max_alias_word_count:
            continue
        seen.add(low)
        clean.append(a_stripped)
    npc.aliases = clean


def _npc_richness(npc: NpcData, game: "GameState") -> int:
    dd = eng().description_dedup
    return (
        len(npc.memory) * dd.richness_memory
        + bool(npc.agenda) * dd.richness_aim
        + bool(npc.instinct) * dd.richness_aim
        + get_npc_bond(game, npc.id) * dd.richness_memory
        + bool(npc.description) * dd.richness_other
    )


def _absorb_richer_duplicate_fields(original: NpcData, dup: NpcData) -> None:
    if dup.description:
        original.description = dup.description
    if dup.agenda:
        original.agenda = dup.agenda
    if dup.instinct:
        original.instinct = dup.instinct
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


def _fill_empty_fields_from_duplicate(original: NpcData, dup: NpcData) -> None:
    if not original.description and dup.description:
        original.description = dup.description
    if not original.agenda and dup.agenda:
        original.agenda = dup.agenda
    if not original.instinct and dup.instinct:
        original.instinct = dup.instinct


def _merge_aliases_and_location(original: NpcData, dup: NpcData, merged_norm: str) -> None:
    existing_norms = {normalize_for_match(a) for a in original.aliases}
    for alias in dup.aliases:
        alias_norm = normalize_for_match(alias)
        if alias_norm not in existing_norms and alias_norm != merged_norm:
            original.aliases.append(alias)
    if dup.last_location and not original.last_location:
        original.last_location = dup.last_location


def absorb_duplicate_npc(game: "GameState", original: NpcData, merged_name: str) -> None:
    merged_norm = normalize_for_match(merged_name)
    for dup in game.npcs:
        if dup is original or dup.id == original.id:
            continue
        dup_name_norm = normalize_for_match(dup.name)
        dup_alias_norms = {normalize_for_match(a) for a in dup.aliases}
        if not (dup_name_norm == merged_norm or merged_norm in dup_alias_norms):
            continue

        dup_id = dup.id
        dup_mem_count = len(dup.memory)

        original.memory.extend(dup.memory)
        original.importance_accumulator = original.importance_accumulator + dup.importance_accumulator

        if _npc_richness(dup, game) > _npc_richness(original, game):
            _absorb_richer_duplicate_fields(original, dup)
            log(
                f"[NPC] Absorb: dup '{dup.name}' ({dup_id}) was richer — "
                f"its fields promoted into original '{original.name}' ({original.id})"
            )
        else:
            _fill_empty_fields_from_duplicate(original, dup)

        _merge_aliases_and_location(original, dup, merged_norm)

        game.npcs.remove(dup)
        log(
            f"[NPC] Absorbed duplicate '{dup.name}' ({dup_id}) "
            f"into '{original.name}' ({original.id}): "
            f"{dup_mem_count} memories transferred"
        )
        sanitize_aliases(original)
        consolidate_memory(original)
        break


def _desc_tokens(text: str, min_word_chars: int, stopwords: "frozenset[str]") -> set[str]:
    return {
        w.strip(".,;:!?\"'()-").lower() for w in text.split() if len(w.strip(".,;:!?\"'()-")) >= min_word_chars
    } - stopwords


def _desc_substring_overlap(new_words: set[str], existing_words: set[str], dd: "DescriptionDedupConfig") -> set[str]:
    exact = new_words & existing_words
    substring: set[str] = set()
    for nw in new_words - exact:
        for ew in existing_words - exact:
            if len(nw) < dd.min_substring_match_len or len(ew) < dd.min_substring_match_len:
                continue
            if nw in ew or ew in nw:
                substring.add(nw)
                break
            nw_parts = {p for p in nw.split("-") if len(p) >= dd.min_word_chars_for_match}
            ew_parts = {p for p in ew.split("-") if len(p) >= dd.min_word_chars_for_match}
            if nw_parts & ew_parts:
                substring.add(nw)
                break
    return substring


def _description_candidate_meets_threshold(
    new_words: set[str],
    existing_words: set[str],
    dd: "DescriptionDedupConfig",
) -> tuple[bool, float]:
    exact_overlap = new_words & existing_words
    substring_matches = _desc_substring_overlap(new_words, existing_words, dd)

    long_exact = sum(1 for w in exact_overlap if len(w) >= dd.long_word_chars)
    effective_overlap: float = (
        len(exact_overlap) + long_exact * dd.partial_match_weight + len(substring_matches) * dd.partial_match_weight
    )
    if effective_overlap < dd.effective_overlap_min:
        return False, effective_overlap

    min_set_size = min(len(new_words), len(existing_words))
    overlap_ratio = effective_overlap / max(min_set_size, 1)
    has_long_match = any(len(w) >= dd.long_word_chars for w in exact_overlap)

    meets = (overlap_ratio >= dd.min_overlap_ratio and effective_overlap >= dd.effective_overlap_min) or (
        has_long_match and effective_overlap >= dd.effective_overlap_min
    )
    return meets, effective_overlap


def _npc_eligible_for_desc_match(npc: NpcData, new_name_norm: str, current_location: str) -> bool:
    if npc.status not in ("active", "background", "lore"):
        return False
    if normalize_for_match(npc.name) == new_name_norm:
        return False
    from ..mechanics import locations_match

    npc_loc = npc.last_location.strip()
    cur = current_location.strip()
    if npc_loc and cur and not locations_match(npc_loc, cur):
        return False
    return bool(npc.description)


def description_match_existing_npc(game: "GameState", new_desc: str, new_name_norm: str) -> NpcData | None:
    dd = eng().description_dedup
    stopwords = eng().stopwords.general

    if not new_desc or len(new_desc) < dd.min_desc_chars:
        return None

    new_words = _desc_tokens(new_desc, dd.min_word_chars_for_match, stopwords)

    candidate_name_words = _desc_tokens(new_name_norm, dd.min_word_chars_for_match, stopwords)
    new_words -= candidate_name_words

    if len(new_words) < dd.min_new_word_count:
        return None

    current_location = game.world.current_location or ""
    best_match: NpcData | None = None
    best_score: float = 0

    for n in game.npcs:
        if not _npc_eligible_for_desc_match(n, new_name_norm, current_location):
            continue

        existing_words = _desc_tokens(n.description, dd.min_word_chars_for_match, stopwords)

        meets, effective_overlap = _description_candidate_meets_threshold(new_words, existing_words, dd)
        if meets and effective_overlap > best_score:
            best_score = effective_overlap
            best_match = n
            exact_overlap = new_words & existing_words
            substring_matches = _desc_substring_overlap(new_words, existing_words, dd)
            min_set_size = min(len(new_words), len(existing_words))
            overlap_ratio = effective_overlap / max(min_set_size, 1)
            log(
                f"[NPC] Description match candidate: new='{new_desc[:50]}' ~ "
                f"existing='{n.name}' desc='{n.description[:50]}' "
                f"(exact={exact_overlap}, substr={substring_matches}, "
                f"effective={effective_overlap:.1f}, ratio={overlap_ratio:.1%})"
            )

    return best_match
