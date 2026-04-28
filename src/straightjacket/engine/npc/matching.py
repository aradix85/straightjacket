import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import GameState

from ..engine_loader import eng
from ..logging_util import log
from ..models import NpcData


_ALIAS_HINT_RE = re.compile(
    r"\b(?:also\s+known\s+as|aka|called)\s+",
    re.IGNORECASE,
)


def normalize_for_match(s: str) -> str:
    return re.sub(r"[\s\-_]+", " ", s).lower().strip()


def sanitize_npc_name(name: str) -> tuple[str, list[str]]:
    if not name or "(" not in name:
        return name.strip(), []
    m = re.match(r"^(.+?)\s*\((.+)\)\s*$", name)
    if not m:
        return name.strip(), []
    clean = m.group(1).strip()
    paren = m.group(2).strip()
    if not clean:
        return name.strip(), []
    alias_match = _ALIAS_HINT_RE.search(paren)
    if alias_match:
        alias = paren[alias_match.end() :].strip().rstrip(".")
        return clean, [alias] if alias else []
    return clean, [paren] if paren else []


def apply_name_sanitization(npc: NpcData) -> None:
    raw = npc.name
    if "(" not in raw:
        return
    clean, extracted = sanitize_npc_name(raw)
    if clean == raw:
        return
    npc.name = clean
    existing_lower = {a.lower() for a in npc.aliases}
    if raw.lower() not in existing_lower and raw.lower() != clean.lower():
        npc.aliases.append(raw)
        existing_lower.add(raw.lower())
    for alias in extracted:
        if alias.lower() not in existing_lower and alias.lower() != clean.lower():
            npc.aliases.append(alias)
            existing_lower.add(alias.lower())
    clean_lower = clean.lower()
    npc.aliases = [a for a in npc.aliases if a.lower() != clean_lower]
    log(f"[NPC] Sanitized name: '{raw}' → '{clean}' (aliases: {npc.aliases})")


def _find_by_id(game: "GameState", npc_ref: str) -> NpcData | None:
    for n in game.npcs:
        if n.id == npc_ref:
            return n
    return None


def _find_by_exact_name(game: "GameState", ref_norm: str) -> NpcData | None:
    for n in game.npcs:
        if normalize_for_match(n.name) == ref_norm:
            return n
    return None


def _find_by_exact_alias(game: "GameState", ref_norm: str) -> NpcData | None:
    for n in game.npcs:
        for alias in n.aliases:
            if normalize_for_match(alias) == ref_norm:
                return n
    return None


def _find_by_substring(game: "GameState", ref_norm: str) -> NpcData | None:
    if len(ref_norm) < eng().fuzzy_match.min_word_length:
        return None
    ref_words = set(ref_norm.split())
    if ref_words and ref_words <= eng().name_titles:
        return None

    min_len = eng().fuzzy_match.min_word_length
    best_match: NpcData | None = None
    best_score = 0

    for n in game.npcs:
        name_norm = normalize_for_match(n.name)
        if ref_norm in name_norm or name_norm in ref_norm:
            score = min(len(ref_norm), len(name_norm))
            if score >= min_len and score > best_score:
                best_score = score
                best_match = n
            continue
        for alias in n.aliases:
            alias_norm = normalize_for_match(alias)
            if ref_norm in alias_norm or alias_norm in ref_norm:
                score = min(len(ref_norm), len(alias_norm))
                if score >= min_len and score > best_score:
                    best_score = score
                    best_match = n

    return best_match


def find_npc(game: "GameState", npc_ref: str | None) -> NpcData | None:
    if not npc_ref:
        return None

    hit = _find_by_id(game, npc_ref)
    if hit:
        return hit

    ref_norm = normalize_for_match(npc_ref)
    hit = _find_by_exact_name(game, ref_norm)
    if hit:
        return hit
    hit = _find_by_exact_alias(game, ref_norm)
    if hit:
        return hit

    substring_match = _find_by_substring(game, ref_norm)
    if substring_match:
        log(f"[NPC] Fuzzy matched '{npc_ref}' → '{substring_match.name}'")
    return substring_match


def resolve_about_npc(game: "GameState", raw: str | None, owner_id: str | None = None) -> str | None:
    if not raw:
        return None
    npc = find_npc(game, raw)
    if npc:
        resolved = npc.id
        if owner_id and resolved == owner_id:
            log(f"[NPC] about_npc self-reference rejected (owner={owner_id}, raw='{raw}')")
            return None
        if resolved != raw:
            log(f"[NPC] about_npc resolved '{raw}' → '{resolved}'")
        return resolved
    return None


def next_npc_id(game: "GameState") -> tuple[str, int]:
    max_num = 0
    for n in game.npcs:
        m = re.match(r"npc_(\d+)", n.id)
        if m:
            max_num = max(max_num, int(m.group(1)))
    max_num += 1
    return f"npc_{max_num}", max_num


def edit_distance_le1(a: str, b: str) -> bool:
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if a == b:
        return True
    if la == lb:
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    if la > lb:
        a, b = b, a
    j = diffs = 0
    for i in range(len(b)):
        if j < len(a) and a[j] == b[i]:
            j += 1
        else:
            diffs += 1
            if diffs > 1:
                return False
    return True


@dataclass
class _FuzzyMatch:
    npc: NpcData | None = None
    score: int = 0
    match_type: str = "identity"


def _strip_titles(words: set[str] | list[str], titles: "frozenset[str]") -> set[str]:
    return {w for w in words if w.rstrip(".") not in titles}


def _check_substring_match(new_norm: str, npc: NpcData, best: _FuzzyMatch, min_word_length: int) -> None:
    name_norm = normalize_for_match(npc.name)
    if new_norm in name_norm or name_norm in new_norm:
        shorter_len = min(len(new_norm), len(name_norm))
        if shorter_len >= min_word_length and shorter_len > best.score:
            best.score = shorter_len
            best.npc = npc
            best.match_type = "identity"


def _check_alias_match(
    new_norm: str, npc: NpcData, best: _FuzzyMatch, min_word_length: int
) -> tuple[NpcData, str] | None:
    for alias in npc.aliases:
        alias_norm = normalize_for_match(alias)
        if alias_norm == new_norm:
            return npc, "identity"
        if new_norm in alias_norm or alias_norm in new_norm:
            shorter_len = min(len(new_norm), len(alias_norm))
            if shorter_len >= min_word_length and shorter_len > best.score:
                best.score = shorter_len
                best.npc = npc
                best.match_type = "identity"
    return None


def _check_word_overlap(
    new_norm: str,
    new_words: set[str],
    npc: NpcData,
    best: _FuzzyMatch,
    titles: "frozenset[str]",
    min_word_length: int,
    exact_dedup_threshold: float,
) -> None:
    name_norm = normalize_for_match(npc.name)
    name_words = _strip_titles(set(name_norm.split()), titles)
    alias_words: set[str] = set()
    for alias in npc.aliases:
        alias_words.update(_strip_titles(set(normalize_for_match(alias).split()), titles))
    all_words = name_words | alias_words

    overlap = new_words & all_words
    significant = [w for w in overlap if len(w) >= min_word_length]
    if not significant:
        return

    if len(significant) == 1:
        word = significant[0]
        name_ratio = len(word) / max(len(name_norm), 1)
        new_ratio = len(word) / max(len(new_norm), 1)
        if max(name_ratio, new_ratio) < exact_dedup_threshold:
            return

    score = sum(len(w) for w in significant)
    if score > best.score:
        best.score = score
        best.npc = npc


def _check_edit_distance_variant(
    new_norm: str,
    npc: NpcData,
    best: _FuzzyMatch,
    titles: "frozenset[str]",
    min_word_length: int,
    stt_alias_bonus: int,
) -> None:
    name_norm = normalize_for_match(npc.name)
    ext_words = sorted(_strip_titles(name_norm.split(), titles))
    new_words_sorted = sorted(_strip_titles(new_norm.split(), titles))

    if not ext_words or not new_words_sorted or len(ext_words) != len(new_words_sorted):
        return

    _fm = eng().fuzzy_match
    _desc_word_min = _fm.description_word_min_length
    exact = 0
    near = 0
    for nw, ew in zip(new_words_sorted, ext_words, strict=True):
        if nw == ew:
            exact += 1
        elif len(nw) >= _desc_word_min and len(ew) >= _desc_word_min and edit_distance_le1(nw, ew):
            near += 1
        else:
            return

    if near < 1:
        return
    accept = exact >= 1 or (len(new_words_sorted) == 1 and len(new_words_sorted[0]) >= min_word_length)
    if not accept:
        return

    stt_score = sum(len(w) for w in new_words_sorted) + stt_alias_bonus
    if stt_score > best.score:
        best.score = stt_score
        best.npc = npc
        best.match_type = "stt_variant"
        log(f"[NPC] Edit-distance match: '{new_norm}' ~ '{npc.name}'")


def fuzzy_match_existing_npc(game: "GameState", new_name: str) -> tuple[NpcData | None, str | None]:
    if not new_name or len(new_name.strip()) < eng().fuzzy_match.npc_name_min_length:
        return None, None

    new_norm = normalize_for_match(new_name)
    titles = eng().name_titles
    new_words_raw = set(new_norm.split())
    new_words = _strip_titles(new_words_raw, titles)

    _fuzzy = eng().fuzzy_match
    _npc_match = eng().npc_matching

    best = _FuzzyMatch()

    for npc in game.npcs:
        if normalize_for_match(npc.name) == new_norm:
            continue

        name_norm = normalize_for_match(npc.name)
        if new_norm in name_norm or name_norm in new_norm:
            _check_substring_match(new_norm, npc, best, _fuzzy.min_word_length)
            continue

        early = _check_alias_match(new_norm, npc, best, _fuzzy.min_word_length)
        if early is not None:
            return early

        _check_word_overlap(
            new_norm, new_words, npc, best, titles, _fuzzy.min_word_length, _fuzzy.exact_dedup_threshold
        )

        _check_edit_distance_variant(new_norm, npc, best, titles, _fuzzy.min_word_length, _npc_match.stt_alias_bonus)

    if best.npc:
        log(
            f"[NPC] Fuzzy match accepted: '{new_name}' → '{best.npc.name}' (score={best.score}, type={best.match_type})"
        )
    return best.npc, best.match_type if best.npc else None
