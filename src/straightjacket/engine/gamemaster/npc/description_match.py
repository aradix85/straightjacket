from ...engine_loader import eng
from ...logging_util import log
from ...models import GameState, NpcData
from ..config import gm
from ..config_types import DescriptionDedupConfig
from ..world import locations_match
from .matching import normalize_for_match


def is_complete_description(desc: str) -> bool:
    if len(desc) < gm().fuzzy_match.description_match_min_length:
        return False
    return desc.rstrip().endswith(tuple(eng().parser.sentence_end_marks))


def _desc_tokens(text: str, min_word_chars: int, stopwords: frozenset[str]) -> set[str]:
    return {
        w.strip(".,;:!?\"'()-").lower() for w in text.split() if len(w.strip(".,;:!?\"'()-")) >= min_word_chars
    } - stopwords


def _desc_substring_overlap(new_words: set[str], existing_words: set[str], dd: DescriptionDedupConfig) -> set[str]:
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
    dd: DescriptionDedupConfig,
) -> tuple[bool, float]:
    exact_overlap = new_words & existing_words
    substring_matches = _desc_substring_overlap(new_words, existing_words, dd)

    long_exact = sum(1 for w in exact_overlap if len(w) >= dd.long_word_chars)
    effective_overlap: float = (
        len(exact_overlap) + long_exact * dd.partial_match_weight + len(substring_matches) * dd.partial_match_weight
    )
    if effective_overlap < dd.effective_overlap_min:
        return False, effective_overlap

    overlap_ratio = effective_overlap / min(len(new_words), len(existing_words))
    has_long_match = any(len(w) >= dd.long_word_chars for w in exact_overlap)
    return overlap_ratio >= dd.min_overlap_ratio or has_long_match, effective_overlap


def _npc_eligible_for_desc_match(npc: NpcData, new_name_norm: str, current_location: str) -> bool:
    if npc.status not in gm().npc_status_groups.description_matchable:
        return False
    if normalize_for_match(npc.name) == new_name_norm:
        return False
    npc_loc = npc.last_location.strip()
    cur = current_location.strip()
    if npc_loc and cur and not locations_match(npc_loc, cur):
        return False
    return bool(npc.description)


def description_match_existing_npc(game: GameState, new_desc: str, new_name_norm: str) -> NpcData | None:
    dd = gm().description_dedup
    stopwords = gm().stopwords.general

    if len(new_desc) < dd.min_desc_chars:
        return None

    new_words = _desc_tokens(new_desc, dd.min_word_chars_for_match, stopwords)

    candidate_name_words = _desc_tokens(new_name_norm, dd.min_word_chars_for_match, stopwords)
    new_words -= candidate_name_words

    if len(new_words) < dd.min_new_word_count:
        return None

    current_location = game.world.current_location
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
            overlap_ratio = effective_overlap / min(len(new_words), len(existing_words))
            log(
                f"[NPC] Description match candidate: new='{new_desc[:50]}' ~ "
                f"existing='{n.name}' desc='{n.description[:50]}' "
                f"(exact={exact_overlap}, substr={substring_matches}, "
                f"effective={effective_overlap:.1f}, ratio={overlap_ratio:.1%})"
            )

    return best_match
