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
    # Direct thought/interpretation attributions (not 'know' — too ambiguous for rule-based)
    r"\byou (?:realize|understand|sense that|suspect|conclude|decide|think|believe|assume|recognize that|grasp)\b",
    # Invented memories
    r"\byou (?:remember|recall|knew|have seen|'ve seen)\b",
    # Emotional state declarations
    r"\b(?:a (?:wave|surge|pang|flash|jolt|stab) of (?:fear|dread|anger|grief|joy|relief|guilt|shame|hope|despair|panic|revulsion|unease|disgust|sadness|horror|rage|fury))\b",
    # "something in you" constructions
    r"\bsomething (?:in|inside|within) you\b",
]
_AGENCY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _AGENCY_EMOTION_PATTERNS]


def check_player_agency(narration: str) -> list[str]:
    """Check for narrator deciding player character's thoughts/feelings."""
    violations = []
    for pattern in _AGENCY_PATTERNS:
        matches = pattern.findall(narration)
        for match in matches:
            violations.append(f"PLAYER AGENCY: narrator wrote '{match.strip()}' — player owns their thoughts and feelings")
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
            if pattern.search(narration):
                match = pattern.search(narration).group()
                violations.append(
                    f"RESULT INTEGRITY: MISS contains silver lining '{match}' — "
                    f"a MISS must show concrete failure with no upside")
                break  # One is enough
        for pattern in _ANNIHILATION_PATTERNS:
            if pattern.search(narration):
                match = pattern.search(narration).group()
                violations.append(
                    f"RESULT INTEGRITY: MISS is annihilation '{match}' — "
                    f"a MISS is a setback, not death or total defeat")
                break
    return violations


# ── SPEECH HANDLING ──────────────────────────────────────────

def check_speech_handling(narration: str, player_words: str) -> list[str]:
    """Check that described speech isn't turned into invented quotes."""
    if not player_words:
        return []
    pw = player_words.strip().lower()
    # Described speech patterns: "I ask about X", "I tell them Y", "I mention Z"
    described = re.match(
        r"^i\s+(?:ask|tell|mention|explain|describe|say that|inquire|question|demand|request|suggest)",
        pw,
    )
    if not described:
        return []
    # Check if narration contains a direct quote that looks like invented player dialog
    # Look for quoted speech attributed to player actions near described-speech verbs
    # Simple heuristic: if narration has \u201c...\u201d and player_words has no quotes
    if "\u201c" not in player_words and "\u201c" in narration:
        # Count quoted segments — if there are player-attributed quotes, flag it
        # This is a heuristic; the LLM validator catches subtle cases
        quotes = re.findall(r'\u201c([^\u201d]{5,})\u201d', narration)
        if len(quotes) >= 2:
            # Multiple quotes — at least one might be invented for the player
            # Can't tell rule-based which is player vs NPC, so skip
            pass
    return []


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


# ── OUTPUT FORMAT ────────────────────────────────────────────

_FORMAT_PATTERNS = [
    (re.compile(r'^\s*(?:Narrator|Assistant|System)\s*:', re.MULTILINE), "role label prefix"),
    (re.compile(r'\[(?:CLOCK|THREAT|SCENE|NPC|CONTEXT|NOTE)[^\]]*\]'), "bracketed annotation"),
    (re.compile(r'```'), "code block"),
    (re.compile(r'^\s*#{1,6}\s', re.MULTILINE), "markdown heading"),
    (re.compile(r'\*\*[^*]+\*\*'), "bold markdown"),
]


def check_output_format(narration: str) -> list[str]:
    """Check for metadata/formatting leaking into prose."""
    violations = []
    for pattern, label in _FORMAT_PATTERNS:
        if pattern.search(narration):
            violations.append(f"OUTPUT FORMAT: narration contains {label}")
    return violations


# ── NPC MONOLOGUE HEURISTIC ──────────────────────────────────

def check_npc_monologue(narration: str) -> list[str]:
    """Heuristic: flag NPC speech that spans 4+ consecutive quoted segments."""
    # Find all quoted segments
    quotes = re.findall(r'\u201c[^\u201d]+\u201d', narration)
    if len(quotes) < 4:
        return []
    # Check if 4+ quotes appear with minimal non-quote text between them
    # This catches NPC monologues disguised as multiple quote blocks
    parts = re.split(r'\u201c[^\u201d]+\u201d', narration)
    consecutive_short_gaps = 0
    for part in parts[1:-1]:  # Skip before first and after last quote
        stripped = part.strip()
        if len(stripped) < 40:  # Short gap between quotes = same speaker monologuing
            consecutive_short_gaps += 1
        else:
            consecutive_short_gaps = 0
        if consecutive_short_gaps >= 3:
            return ["RESOLUTION PACING: NPC delivers an extended monologue (4+ quoted segments with minimal breaks)"]
    return []


# ── PUBLIC API ───────────────────────────────────────────────

def run_rule_checks(
    narration: str,
    result_type: str,
    player_words: str = "",
    genre_constraints: dict | None = None,
) -> dict:
    """Run all rule-based checks. Returns same format as LLM validator.

    Returns:
        {"pass": bool, "violations": list[str], "correction": str}
    """
    violations = []

    violations.extend(check_player_agency(narration))
    if result_type in ("MISS", "WEAK_HIT", "STRONG_HIT"):
        violations.extend(check_result_integrity(narration, result_type))
    violations.extend(check_genre_fidelity(narration, genre_constraints))
    violations.extend(check_output_format(narration))
    violations.extend(check_npc_monologue(narration))

    if violations:
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in violations[:3])
        log(f"[RuleValidator] FAILED: {violations}")
        return {"pass": False, "violations": violations, "correction": f"Fix: {correction}"}

    log("[RuleValidator] Passed")
    return {"pass": True, "violations": [], "correction": ""}
