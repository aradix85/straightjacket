#!/usr/bin/env python3
"""Rule-based narrator constraint checks.

Instant, zero-cost checks that catch common violations without an LLM call.
Used as first pass before the LLM validator (which handles semantic checks
like RESOLUTION PACING that require understanding context).
"""

import re

from ..logging_util import log


# ── PLAYER AGENCY ────────────────────────────────────────────

# Patterns where "You feel/sense/realize" is followed by an emotion or interpretation,
# NOT a physical sensation. "You feel the cold metal" = OK. "You feel uneasy" = violation.
_AGENCY_EMOTION_PATTERNS = [
    # "You feel" + emotion/interpretation (not physical object)
    r"\byou feel\b(?!\s+(?:the|a|an|your|its|it|his|her|their|cold|hot|warm|cool|wet|dry|rough|smooth|sharp|dull|soft|hard|heavy|light|damp|slick|gritty|sticky))\s+\w+",
    # Direct thought/interpretation attributions
    # "you think" only when NOT followed by about/of/through/over (those are actions)
    r"\byou (?:realize|understand|sense that|suspect|conclude|decide|believe|assume|recognize that|grasp)\b",
    r"\byou think\b(?!\s+(?:about|of|through|over|back))",
    # Invented memories
    r"\byou (?:remember|recall|knew|have seen|'ve seen)\b",
    # Emotional state declarations
    r"\b(?:a (?:wave|surge|pang|flash|jolt|stab) of (?:fear|dread|anger|grief|joy|relief|guilt|shame|hope|despair|panic|revulsion|unease|disgust|sadness|horror|rage|fury))\b",
    # "something in you" constructions
    r"\bsomething (?:in|inside|within) you\b",
    # Abstract weight/pressure as emotional metaphor
    r"\b(?:the )?weight of (?:your |the |his |her )?(?:failure|guilt|shame|loss|grief|regret|betrayal|silence|withdrawal)\b",
    # "makes you want to" — imposes desire
    r"\bmakes you (?:want|need|wish|long|ache) to\b",
    # Objects/situations imposing feelings
    r"\b(?:the |a )?(?:silence|darkness|cold|emptiness|room|air|wind) (?:offers|invites|urges|compels|forces|demands|asks|tells) you\b",
    # Pressure/weight settling on player
    r"\b(?:press(?:es|ing)|settl(?:es|ing)|weigh(?:s|ing)|hang(?:s|ing)|bears? down) (?:against |on |upon )?your (?:chest|shoulders|ears|back|spine|ribs)\b",
    # Dragging posture/body as emotional metaphor
    r"\bdragging your (?:posture|shoulders|head|body|gaze)\b",
    # Crushing/suffocating as emotional descriptor
    r"\b(?:crushing|suffocating) (?:pressure|weight|silence|darkness|realization)\b",
    # "feels distant/underwater" — imposed dissociation
    r"\b(?:sound|voice|world|noise)s? feels? (?:distant|muffled|far away|underwater)\b",
    # "as if you are" — imposed internal comparison
    r"\bas if you (?:are|were) (?:already |somehow )?(?:underwater|drowning|falling|sinking|floating)\b",
    # Evaporation/loss metaphors applied to player state
    r"\b(?:whatever |the )?(?:fragile |thin )?(?:advantage|connection|trust|hope|progress) you (?:thought you )?held\b",
    r"\b(?:advantage|connection|trust|hope) (?:you held |between you )?(?:evaporates?|dissolves?|vanishes?|crumbles?)\b",
    # Qwen patterns: knowledge/conclusion imposed on player (from Elvira baseline)
    r"\byou(?:'ve| have) found (?:the |a )?(?:break|answer|pattern|key|link|cause|source|reason)\b",
    r"\b(?:sticks|lodges|burns|stays|lingers|registers) in your (?:mind|memory|thoughts|head)\b",
    r"\byou (?:can tell|can sense|can feel|just know|already know|know enough)\b",
    r"\byou (?:notice|catch|spot|see) (?:yourself|your own)\s+(?:thinking|feeling|hoping|wanting)\b",
]
_AGENCY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _AGENCY_EMOTION_PATTERNS]


_QUOTE_STRIP_RE = re.compile(r"\u201c[^\u201d]*\u201d")


def check_player_agency(narration: str) -> list[str]:
    """Check for narrator deciding player character's thoughts/feelings.

    Strips quoted NPC speech first — "You think X?" from an NPC is not
    a player agency violation.
    """
    # Remove quoted speech to avoid false positives on NPC dialog
    prose_only = _QUOTE_STRIP_RE.sub("", narration)
    violations = []
    for pattern in _AGENCY_PATTERNS:
        matches = pattern.findall(prose_only)
        for match in matches:
            violations.append(
                f"PLAYER AGENCY: narrator wrote '{match.strip()}' — player owns their thoughts and feelings"
            )
    # Deduplicate similar violations
    seen = set()
    unique = []
    for v in violations:
        key = v[:60]
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique[:3]  # Cap at 3 to avoid noise


# ── RESULT INTEGRITY ─────────────────────────────────────────

_MISS_SILVER_LINING_PATTERNS = [
    r"\bat least\b",
    r"\bfortunately\b",
    r"\bluckily\b",
    r"\bmanage[sd]? to\b",
    r"\bbut (?:you|the|it|she|he|they)\b.*\b(?:safe|survive|escape|learn|gain|find|discover)\b",
    r"\bsilver lining\b",
    r"\bblessing in disguise\b",
    r"\bbright side\b",
]
_MISS_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _MISS_SILVER_LINING_PATTERNS]

_MISS_ANNIHILATION_PATTERNS = [
    r"\byou (?:die|are dead|collapse.{0,20}lifeless|stop breathing)\b",
    r"\beverything (?:goes black|fades to nothing|ends)\b",
    r"\byour (?:vision|world|consciousness) (?:fades|dims|goes|ends)\b",
]
_ANNIHILATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _MISS_ANNIHILATION_PATTERNS]


def check_result_integrity(narration: str, result_type: str) -> list[str]:
    """Check that narration matches the mechanical result type."""
    violations = []
    if result_type == "MISS":
        for pattern in _MISS_PATTERNS:
            m = pattern.search(narration)
            if m:
                violations.append(
                    f"RESULT INTEGRITY: MISS contains silver lining '{m.group()}' — "
                    f"a MISS must show concrete failure with no upside"
                )
                break  # One is enough
        for pattern in _ANNIHILATION_PATTERNS:
            m = pattern.search(narration)
            if m:
                violations.append(
                    f"RESULT INTEGRITY: MISS is annihilation '{m.group()}' — "
                    f"a MISS is a setback, not death or total defeat"
                )
                break
    return violations


# ── GENRE FIDELITY ───────────────────────────────────────────


def check_genre_fidelity(narration: str, genre_constraints: dict | None) -> list[str]:
    """Check for forbidden terms in narration."""
    if not genre_constraints:
        return []
    violations = []
    narration_lower = narration.lower()
    for term in genre_constraints.get("forbidden_terms", []):
        if term.lower() in narration_lower:
            violations.append(f"GENRE FIDELITY: forbidden term '{term}' found in narration")
    return violations


# ── ATMOSPHERIC REGISTER ────────────────────────────────────


def check_atmospheric_register(narration: str, genre_constraints: dict | None) -> list[str]:
    """Flag atmospheric register drift when setting-specific markers pile up.

    Reads atmospheric_drift (word list) and atmospheric_drift_threshold (int)
    from genre_constraints. No config = no check.
    """
    if not genre_constraints:
        return []
    drift_words = genre_constraints.get("atmospheric_drift", [])
    threshold = genre_constraints.get("atmospheric_drift_threshold", 3)
    if not drift_words or threshold < 1:
        return []

    narration_lower = narration.lower()
    matches = []
    for word in drift_words:
        word_lower = word.lower()
        if " " in word_lower:
            if word_lower in narration_lower:
                matches.append(word_lower)
        else:
            hits = re.findall(rf"\b{re.escape(word_lower)}\b", narration_lower)
            matches.extend(hits)

    if len(matches) < threshold:
        return []
    unique = sorted(set(matches))
    return [
        f"ATMOSPHERIC REGISTER: {len(matches)} drift markers in one scene "
        f"({', '.join(unique[:5])}). Ground the prose in physical sensation from <sensory_palette>"
    ]


# ── OUTPUT FORMAT ────────────────────────────────────────────

_FORMAT_PATTERNS = [
    (re.compile(r"^\s*(?:Narrator|Assistant|System)\s*:", re.MULTILINE), "role label prefix"),
    (re.compile(r"\[(?:CLOCK|THREAT|SCENE|NPC|CONTEXT|NOTE)[^\]]*\]"), "bracketed annotation"),
    (re.compile(r"```"), "code block"),
    (re.compile(r"^\s*#{1,6}\s", re.MULTILINE), "markdown heading"),
    (re.compile(r"\*\*[^*]+\*\*"), "bold markdown"),
]


def check_output_format(narration: str) -> list[str]:
    """Check for metadata/formatting leaking into prose."""
    violations = []
    for pattern, label in _FORMAT_PATTERNS:
        if pattern.search(narration):
            violations.append(f"OUTPUT FORMAT: narration contains {label}")
    return violations


# ── NPC MONOLOGUE HEURISTIC ──────────────────────────────────

_QUOTE_RE = re.compile(r"\u201c([^\u201d]+)\u201d")


def check_npc_monologue(narration: str) -> list[str]:
    """Heuristic: flag NPC speech that dominates the scene.

    Only checks structural dominance — content quality (unsolicited info)
    is left to the LLM validator. Speech length alone is not a violation.

    Flags when 4+ quoted segments appear with minimal narrative between them,
    indicating an NPC monologue that crowds out player action and scene detail.
    """
    quotes = _QUOTE_RE.findall(narration)
    if len(quotes) < 4:
        return []

    parts = _QUOTE_RE.split(narration)
    # parts alternates: [before, quote1, between, quote2, ...]
    # Non-quote gaps are at even indices starting from 2
    consecutive_short_gaps = 0
    for i in range(2, len(parts), 2):
        stripped = parts[i].strip()
        if len(stripped) < 40:
            consecutive_short_gaps += 1
        else:
            consecutive_short_gaps = 0
        if consecutive_short_gaps >= 3:
            return ["RESOLUTION PACING: NPC delivers an extended monologue (4+ quoted segments with minimal breaks)"]

    return []


# ── CONSEQUENCE VERIFICATION ────────────────────────────────

_CONSEQUENCE_STOPWORDS = frozenset(
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
        "will",
        "can",
        "been",
        "into",
        "than",
        "then",
        "about",
        "something",
        "nothing",
        "their",
        "your",
        "what",
        "when",
        "where",
        "does",
        "doesn",
        "again",
        "back",
        "just",
        "now",
        "still",
        "even",
        "more",
        "much",
        "very",
        "only",
        "also",
    }
)


def check_consequence_keywords(narration: str, consequence_sentences: list[str], player_name: str = "") -> list[str]:
    """Check that each consequence sentence has at least one keyword reflected in narration.

    Strips possessives, contractions, and player name words (narrator writes
    "you" not the character name). Uses stem matching for common consequence
    verbs the model paraphrases.
    """
    if not consequence_sentences:
        return []
    narration_lower = narration.lower()
    # Player name words to exclude — narrator writes "you", not "Wanderer-369"
    name_words = {w.strip(".,;:!?\"'()-").lower() for w in player_name.split()} if player_name else set()
    violations = []
    for sentence in consequence_sentences:
        raw_words = {w.strip(".,;:!?\"'()-").lower() for w in sentence.split()}
        cleaned = set()
        for w in raw_words:
            # Strip possessives: "Corvo's" → "corvo", "player's" → "player"
            if w.endswith("'s") or w.endswith("\u2019s"):
                w = w[:-2]
            # Skip contractions like "it's", "don't"
            elif "'" in w or "\u2019" in w:
                continue
            if len(w) >= 4:
                cleaned.add(w)
        keywords = cleaned - _CONSEQUENCE_STOPWORDS - name_words
        if not keywords:
            continue
        if any(kw in narration_lower for kw in keywords):
            continue
        stems_found = False
        for kw in keywords:
            stem_variants = _CONSEQUENCE_STEMS.get(kw, ())
            if any(sv in narration_lower for sv in stem_variants):
                stems_found = True
                break
        if stems_found:
            continue
        violations.append(
            f"CONSEQUENCE MISSING: narrator did not reflect '{sentence[:60]}' — "
            f"none of {sorted(keywords)[:4]} found in narration"
        )
    return violations[:2]


_CONSEQUENCE_STEMS: dict[str, tuple[str, ...]] = {
    "breaks": ("broke", "broken", "snaps", "snapped", "crack", "cracked", "shatter"),
    "broken": ("breaks", "broke", "snaps", "cracked", "shatter"),
    "closes": ("closed", "closing", "shuts", "shut"),
    "dims": ("dimmed", "dimming", "fades", "faded", "darkens", "darkened"),
    "loses": ("lost", "losing", "gone"),
    "lost": ("loses", "losing", "gone"),
    "gone": ("lost", "loses", "vanish", "disappear"),
    "pulls": ("pulled", "pulling", "draws", "drew"),
    "withdraws": ("withdrew", "withdrawal", "retreats", "retreated", "pulls"),
    "fractures": ("fractured", "cracks", "cracked", "breaks", "broken"),
    "settles": ("settled", "settling", "sinks", "sank"),
    "falters": ("faltered", "faltering", "wavers", "wavered"),
    "evaporates": ("evaporated", "vanishes", "vanished", "dissolves", "dissolved"),
    "staggers": ("staggered", "staggering", "stumbles", "stumbled"),
    "crumples": ("crumpled", "collapses", "collapsed"),
    "advantage": ("edge", "leverage", "upper hand", "opening"),
    "momentum": ("advantage", "edge", "leverage", "initiative"),
    "doubt": ("uncertain", "hesitat", "waver"),
    "exhaustion": ("exhausted", "fatigue", "fatigued", "weariness", "weary", "tired"),
    "slips": ("slipped", "slipping", "falters", "faltered"),
    "supplies": ("supply", "gear", "pack", "rations", "kit", "provisions"),
    "dropped": ("drops", "drop", "fell", "spill", "spilled"),
    "spent": ("used", "consumed", "depleted", "empty", "emptied"),
    "turns": ("turned", "turning"),
    "crosses": ("crossed", "crossing"),
    "steps": ("stepped", "stepping"),
    "shifts": ("shifted", "shifting", "changes", "changed"),
}


# ── PUBLIC API ───────────────────────────────────────────────


def run_rule_checks(
    narration: str,
    result_type: str,
    player_words: str = "",
    genre_constraints: dict | None = None,
    consequence_sentences: list[str] | None = None,
    player_name: str = "",
) -> dict:
    """Run all rule-based checks. Returns same format as LLM validator."""
    violations = []

    violations.extend(check_player_agency(narration))
    if result_type in ("MISS", "WEAK_HIT", "STRONG_HIT"):
        violations.extend(check_result_integrity(narration, result_type))
    violations.extend(check_genre_fidelity(narration, genre_constraints))
    violations.extend(check_atmospheric_register(narration, genre_constraints))
    violations.extend(check_output_format(narration))
    violations.extend(check_npc_monologue(narration))

    if violations:
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in violations[:3])
        log(f"[RuleValidator] FAILED: {violations}")
        return {"pass": False, "violations": violations, "correction": f"Fix: {correction}"}

    log("[RuleValidator] Passed")
    return {"pass": True, "violations": [], "correction": ""}
