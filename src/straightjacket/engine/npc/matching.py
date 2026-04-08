#!/usr/bin/env python3
"""NPC name matching: title/honorific filtering, sanitization, fuzzy matching,
edit-distance."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import GameState

from ..logging_util import log
from ..models import NpcData

# TITLE / HONORIFIC FILTER
# Prevents false positive fuzzy matches like "Mrs. Chen" ↔ "Mrs. Kowalski".
NAME_TITLES = frozenset(
    {
        # English common
        "mr",
        "mr.",
        "mrs",
        "mrs.",
        "ms",
        "ms.",
        "dr",
        "dr.",
        "sir",
        "lady",
        "lord",
        "miss",
        "captain",
        "cpt",
        "lieutenant",
        "lt",
        "sergeant",
        "sgt",
        "officer",
        "detective",
        "professor",
        "prof",
        "father",
        "sister",
        "brother",
        "uncle",
        "aunt",
        "grandma",
        "grandpa",
        "old",
        "young",
        "the",
        # English nobility/military
        "king",
        "queen",
        "prince",
        "princess",
        "duke",
        "duchess",
        "baron",
        "baroness",
        "count",
        "countess",
        "viscount",
        "marquis",
        "earl",
        "colonel",
        "commander",
        "general",
        "admiral",
        "major",
        "corporal",
        "private",
        "judge",
        "sheriff",
        "mayor",
        "governor",
        "senator",
        "chancellor",
        # English clergy
        "priest",
        "priestess",
        "bishop",
        "cardinal",
        "reverend",
        "pastor",
        "rabbi",
        "imam",
        "monk",
        "abbot",
        "abbess",
        # English diplomatic
        "ambassador",
        "consul",
        "envoy",
        "delegate",
        # French
        "monsieur",
        "madame",
        "mademoiselle",
        # Spanish
        "señor",
        "señora",
        "señorita",
        "don",
        "doña",
        # Fantasy/RPG — magic users
        "wizard",
        "sorcerer",
        "sorceress",
        "mage",
        "warlock",
        "witch",
        "archmage",
        "enchantress",
        "necromancer",
        "alchemist",
        # Fantasy/RPG — classes
        "paladin",
        "cleric",
        "rogue",
        "assassin",
        "berserker",
        "barbarian",
        "gladiator",
        "champion",
        "sentinel",
        "guardian",
        "inquisitor",
        "templar",
        "crusader",
        # Fantasy/RPG — nobility
        "squire",
        "knight",
        "liege",
        "regent",
        "viceroy",
        "castellan",
        "seneschal",
        "steward",
        "herald",
        "grandmaster",
        # Fantasy/RPG — spiritual
        "shaman",
        "oracle",
        "prophet",
        "seer",
        "sage",
        "elder",
        "druid",
        "mystic",
        "augur",
        "diviner",
        # Fantasy/RPG — medieval trades
        "peasant",
        "blacksmith",
        "fletcher",
        "reeve",
        "constable",
        # Sci-fi
        "ensign",
        "marshal",
        "overseer",
        "commissioner",
        "agent",
        "operative",
        "warlord",
        "android",
        "emissary",
        "arbiter",
        "overlord",
        "archon",
        "praetor",
        "legate",
        "centurion",
        # Eastern
        "shogun",
        "samurai",
        "ronin",
        "khan",
        "caliph",
        "emir",
        "shah",
        # Generic descriptors
        "outcast",
        "exile",
        "pilgrim",
        "wanderer",
        "mercenary",
        "neighbor",
        "stranger",
        "customer",
    }
)

# NAME SANITIZATION
_ALIAS_HINT_RE = re.compile(
    r"\b(?:also\s+known\s+as|aka|called)\s+",
    re.IGNORECASE,
)


def normalize_for_match(s: str) -> str:
    """Normalize a name string for comparison only — stored names are never modified.
    Collapses hyphens, underscores, and whitespace variants to a single space,
    then lowercases and strips. Makes 'Wacholder-im-Schnee', 'Wacholder im Schnee',
    and 'wacholder_im_schnee' all compare equal."""
    return re.sub(r"[\s\-_]+", " ", s).lower().strip()


def sanitize_npc_name(name: str) -> tuple[str, list[str]]:
    """Strip parenthetical annotations from NPC names.
    Returns (clean_name, extracted_aliases)."""
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
    """Sanitize an NPC's name in-place: strip parentheticals, add as aliases."""
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


# NPC LOOKUP


def find_npc(game: "GameState", npc_ref: str) -> NpcData | None:
    """Find an NPC by ID, name, alias, or substring match."""
    if not npc_ref:
        return None
    for n in game.npcs:
        if n.id == npc_ref:
            return n
    ref_norm = normalize_for_match(npc_ref)
    for n in game.npcs:
        if normalize_for_match(n.name) == ref_norm:
            return n
    for n in game.npcs:
        for alias in n.aliases:
            if normalize_for_match(alias) == ref_norm:
                return n
    if len(ref_norm) >= 5:
        ref_words = set(ref_norm.split())
        if ref_words and ref_words <= NAME_TITLES:
            return None
        best_match = None
        best_score = 0
        for n in game.npcs:
            name_norm = normalize_for_match(n.name)
            if ref_norm in name_norm or name_norm in ref_norm:
                score = min(len(ref_norm), len(name_norm))
                if score >= 5 and score > best_score:
                    best_score = score
                    best_match = n
                continue
            for alias in n.aliases:
                alias_norm = normalize_for_match(alias)
                if ref_norm in alias_norm or alias_norm in ref_norm:
                    score = min(len(ref_norm), len(alias_norm))
                    if score >= 5 and score > best_score:
                        best_score = score
                        best_match = n
        if best_match:
            log(f"[NPC] Fuzzy matched '{npc_ref}' → '{best_match.name}' (score={best_score})")
            return best_match
    return None


def resolve_about_npc(game: "GameState", raw: str | None, owner_id: str | None = None) -> str | None:
    """Resolve an about_npc value to a canonical npc_id.
    If owner_id is provided and the resolved ID matches it, returns None
    (prevents self-references in NPC memories)."""
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
    """Determine the next available NPC ID."""
    max_num = 0
    for n in game.npcs:
        m = re.match(r"npc_(\d+)", n.id)
        if m:
            max_num = max(max_num, int(m.group(1)))
    max_num += 1
    return f"npc_{max_num}", max_num


# EDIT DISTANCE & FUZZY MATCHING


def edit_distance_le1(a: str, b: str) -> bool:
    """Check if Levenshtein distance between a and b is ≤ 1."""
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


def fuzzy_match_existing_npc(game: "GameState", new_name: str) -> tuple[NpcData | None, str | None]:
    """Check if a 'new' NPC name fuzzy-matches an existing NPC.
    Returns (matching_npc, match_type) or (None, None).
    match_type is 'identity' for normal matches or 'stt_variant' for edit-distance-1 matches."""
    if not new_name or len(new_name.strip()) < 3:
        return None, None
    new_norm = normalize_for_match(new_name)
    new_words_raw = set(new_norm.split())
    new_words = {w for w in new_words_raw if w.rstrip(".") not in NAME_TITLES}

    best_match = None
    best_score = 0
    best_type = "identity"

    for n in game.npcs:
        name_norm = normalize_for_match(n.name)
        if name_norm == new_norm:
            continue

        # 1. Substring check
        if new_norm in name_norm or name_norm in new_norm:
            shorter_len = min(len(new_norm), len(name_norm))
            if shorter_len >= 5 and shorter_len > best_score:
                best_score = shorter_len
                best_match = n
                best_type = "identity"
            continue

        # 2. Alias substring match
        for alias in n.aliases:
            alias_norm = normalize_for_match(alias)
            if alias_norm == new_norm:
                return n, "identity"
            if new_norm in alias_norm or alias_norm in new_norm:
                shorter_len = min(len(new_norm), len(alias_norm))
                if shorter_len >= 5 and shorter_len > best_score:
                    best_score = shorter_len
                    best_match = n
                    best_type = "identity"

        # 3. Significant word overlap
        name_words = {w for w in name_norm.split() if w.rstrip(".") not in NAME_TITLES}
        alias_words: set[str] = set()
        for alias in n.aliases:
            alias_words.update(w for w in normalize_for_match(alias).split() if w.rstrip(".") not in NAME_TITLES)
        all_words = name_words | alias_words

        overlap = new_words & all_words
        significant_overlap = [w for w in overlap if len(w) >= 5]

        if significant_overlap:
            overlap_dominated = False
            if len(significant_overlap) == 1:
                word = significant_overlap[0]
                name_ratio = len(word) / max(len(name_norm), 1)
                new_ratio = len(word) / max(len(new_norm), 1)
                if max(name_ratio, new_ratio) < 0.4:
                    overlap_dominated = True

            if not overlap_dominated:
                score = sum(len(w) for w in significant_overlap)
                if score > best_score:
                    best_score = score
                    best_match = n

        # 4. Edit distance variant check
        ext_name_words = sorted(w for w in name_norm.split() if w.rstrip(".") not in NAME_TITLES)
        new_name_words = sorted(w for w in new_norm.split() if w.rstrip(".") not in NAME_TITLES)

        if ext_name_words and new_name_words and len(ext_name_words) == len(new_name_words):
            exact = 0
            near = 0
            fail = False
            for nw, ew in zip(new_name_words, ext_name_words, strict=True):
                if nw == ew:
                    exact += 1
                elif len(nw) >= 3 and len(ew) >= 3 and edit_distance_le1(nw, ew):
                    near += 1
                else:
                    fail = True
                    break

            if not fail and near >= 1:
                accept = exact >= 1 or (len(new_name_words) == 1 and len(new_name_words[0]) >= 5)
                if accept:
                    stt_score = sum(len(w) for w in new_name_words) + 10
                    if stt_score > best_score:
                        best_score = stt_score
                        best_match = n
                        best_type = "stt_variant"
                        log(f"[NPC] Edit-distance match: '{new_name}' ~ '{n.name}'")

    if best_match:
        log(f"[NPC] Fuzzy match accepted: '{new_name}' → '{best_match.name}' (score={best_score}, type={best_type})")
    return best_match, best_type
