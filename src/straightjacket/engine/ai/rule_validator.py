"""Rule-based narrator constraint checks.

Instant, zero-cost checks that catch common violations without an LLM call.
Used as first pass before the LLM validator (which handles semantic checks
like RESOLUTION PACING that require understanding context).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..datasworn.settings import GenreConstraints
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics.impacts import impact_label
from ..models import GameState


@dataclass
class ValidationContext:
    """Turn-specific context for validation. Built once per validation cycle."""

    game: GameState
    result_type: str = ""
    player_words: str = ""
    consequences: list[str] = field(default_factory=list)
    consequence_sentences: list[str] = field(default_factory=list)
    genre_constraints: GenreConstraints | None = None
    threat_names: list[str] = field(default_factory=list)
    impact_changes: list[str] = field(default_factory=list)  # Impact labels added/cleared this turn

    @classmethod
    def build(
        cls,
        game: GameState,
        result_type: str = "",
        player_words: str = "",
        consequences: list[str] | None = None,
        consequence_sentences: list[str] | None = None,
        genre_constraints: GenreConstraints | None = None,
    ) -> ValidationContext:
        """Build context, deriving threat_names and impact_changes from game state."""
        # Detect impacts changed this turn by comparing to snapshot
        changes: list[str] = []
        snap = game.last_turn_snapshot
        if snap is not None:
            old = set(snap.impacts)
            new = set(game.impacts)
            changes = [impact_label(k) for k in (old ^ new)]

        return cls(
            game=game,
            result_type=result_type,
            player_words=player_words,
            consequences=consequences or [],
            consequence_sentences=consequence_sentences or [],
            genre_constraints=genre_constraints,
            threat_names=[t.name for t in game.threats if t.status == "active"],
            impact_changes=changes,
        )


# Regex patterns live in engine.yaml validator.agency_patterns.
# English-only, tuned for Qwen 3 narrator drift.


def check_player_agency(narration: str) -> list[str]:
    """Check for narrator deciding player character's thoughts/feelings.

    Strips quoted NPC speech first — "You think X?" from an NPC is not
    a player agency violation.
    """
    # Remove quoted speech to avoid false positives on NPC dialog
    prose_only = eng().compiled_pattern("validator", "quote_patterns", "strip").sub("", narration)
    templates = eng().rule_validator.violation_templates
    violations = []
    for pattern in eng().compiled_patterns("validator", "agency_patterns"):
        matches = pattern.findall(prose_only)
        for match in matches:
            violations.append(templates["player_agency"].format(match=match.strip()))

    # Deduplicate similar violations
    _rv = eng().rule_validator
    seen = set()
    unique = []
    for v in violations:
        key = v[: _rv.violation_dedup_key_length]
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique[:3]  # Cap at 3 to avoid noise


# Patterns in engine.yaml validator.miss_silver_lining_patterns / .miss_annihilation_patterns


def check_result_integrity(narration: str, result_type: str) -> list[str]:
    """Check that narration matches the mechanical result type."""
    templates = eng().rule_validator.violation_templates
    violations = []
    if result_type == "MISS":
        for pattern in eng().compiled_patterns("validator", "miss_silver_lining_patterns"):
            m = pattern.search(narration)
            if m:
                violations.append(templates["miss_silver_lining"].format(match=m.group()))
                break  # One is enough
        for pattern in eng().compiled_patterns("validator", "miss_annihilation_patterns"):
            m = pattern.search(narration)
            if m:
                violations.append(templates["miss_annihilation"].format(match=m.group()))
                break
    return violations


def check_genre_fidelity(narration: str, genre_constraints: GenreConstraints | None) -> list[str]:
    """Check for forbidden terms in narration."""
    if not genre_constraints:
        return []
    template = eng().rule_validator.violation_templates["genre_forbidden_term"]
    violations = []
    narration_lower = narration.lower()
    for term in genre_constraints.forbidden_terms:
        if term.lower() in narration_lower:
            violations.append(template.format(term=term))
    return violations


def check_atmospheric_register(narration: str, genre_constraints: GenreConstraints | None) -> list[str]:
    """Flag atmospheric register drift when setting-specific markers pile up.

    Reads atmospheric_drift (word list) and atmospheric_drift_threshold (int)
    from genre_constraints. No config = no check.
    """
    if not genre_constraints:
        return []
    drift_words = genre_constraints.atmospheric_drift
    threshold = genre_constraints.atmospheric_drift_threshold
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
        eng()
        .rule_validator.violation_templates["atmospheric_register"]
        .format(count=len(matches), examples=", ".join(unique[:5]))
    ]


# Patterns in engine.yaml validator.format_patterns


def check_output_format(narration: str) -> list[str]:
    """Check for metadata/formatting leaking into prose."""
    template = eng().rule_validator.violation_templates["output_format"]
    violations = []
    for pattern, label in eng().compiled_labeled_patterns("validator", "format_patterns"):
        if pattern.search(narration):
            violations.append(template.format(label=label))
    return violations


def check_npc_monologue(narration: str) -> list[str]:
    """Heuristic: flag NPC speech that dominates the scene.

    Only checks structural dominance — content quality (unsolicited info)
    is left to the LLM validator. Speech length alone is not a violation.

    Flags when 4+ quoted segments appear with minimal narrative between them,
    indicating an NPC monologue that crowds out player action and scene detail.
    """
    _rv = eng().rule_validator
    quote_re = eng().compiled_pattern("validator", "quote_patterns", "match")
    quotes = quote_re.findall(narration)
    if len(quotes) < _rv.min_quote_count:
        return []

    parts = quote_re.split(narration)
    consecutive_short_gaps = 0
    for i in range(2, len(parts), 2):
        stripped = parts[i].strip()
        if len(stripped) < _rv.max_gap_chars:
            consecutive_short_gaps += 1
        else:
            consecutive_short_gaps = 0
        if consecutive_short_gaps >= _rv.max_consecutive_short_gaps:
            return [_rv.violation_templates["npc_monologue"]]

    return []


def check_consequence_keywords(narration: str, consequence_sentences: list[str], player_name: str = "") -> list[str]:
    """Check that each consequence sentence has at least one keyword reflected in narration.

    Strips possessives, contractions, and player name words (narrator writes
    "you" not the character name). Uses stem matching for common consequence
    verbs the model paraphrases.
    """
    if not consequence_sentences:
        return []
    stopwords = eng().stopwords.consequence
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
        keywords = cleaned - stopwords - name_words
        if not keywords:
            continue
        if any(kw in narration_lower for kw in keywords):
            continue
        stems_found = False
        stems_map = _consequence_stems()
        for kw in keywords:
            stem_variants = stems_map.get(kw, ())
            if any(sv in narration_lower for sv in stem_variants):
                stems_found = True
                break
        if stems_found:
            continue
        _rv = eng().rule_validator
        violations.append(
            _rv.violation_templates["consequence_missing"].format(
                sentence=sentence[: _rv.consequence_sentence_preview],
                keywords=sorted(keywords)[:4],
            )
        )
    return violations[:2]


def _consequence_stems() -> dict[str, tuple[str, ...]]:
    """Load consequence stem map from engine.yaml validator.consequence_stems.

    Raises KeyError if the section is missing — no silent fallback.
    """
    raw = eng().get_raw("validator")["consequence_stems"]
    return {k: tuple(v) for k, v in raw.items()}


def check_threat_advance(narration: str, threat_names: list[str]) -> list[str]:
    """Check that narrator acknowledges threat menace advancement.

    When a <threat_advance> tag was in the prompt, the narration should
    reflect the threat's growing pressure — by name or by implication.
    """
    if not threat_names:
        return []
    stopwords = eng().stopwords.consequence
    narration_lower = narration.lower()
    for name in threat_names:
        words = {w.strip(".,;:!?\"'()-").lower() for w in name.split() if len(w) >= 3}
        words -= stopwords
        if any(w in narration_lower for w in words):
            continue
        return [eng().rule_validator.violation_templates["threat_advance"].format(name=name)]
    return []


def check_impact_acknowledgment(narration: str, impact_changes: list[str]) -> list[str]:
    """Check that narrator acknowledges impact changes (mark/clear) this turn.

    When game.impacts changed since last snapshot, the narration must mention
    the impact label (or a clear synonym) — the character's condition changed.
    """
    if not impact_changes:
        return []
    narration_lower = narration.lower()
    for label in impact_changes:
        if label.lower() in narration_lower:
            continue
        # Allow first word of multi-word labels ("permanently harmed" → "permanently" or "harmed")
        words = [w.lower() for w in label.split() if len(w) >= 4]
        if any(w in narration_lower for w in words):
            continue
        return [eng().rule_validator.violation_templates["impact_change"].format(label=label)]
    return []


def run_rule_checks(narration: str, ctx: ValidationContext) -> dict:
    """Run all rule-based checks. Returns same format as LLM validator."""
    violations = []

    violations.extend(check_player_agency(narration))
    if ctx.result_type in ("MISS", "WEAK_HIT", "STRONG_HIT"):
        violations.extend(check_result_integrity(narration, ctx.result_type))
    violations.extend(check_genre_fidelity(narration, ctx.genre_constraints))
    violations.extend(check_atmospheric_register(narration, ctx.genre_constraints))
    violations.extend(check_output_format(narration))
    violations.extend(check_npc_monologue(narration))
    violations.extend(check_threat_advance(narration, ctx.threat_names))
    violations.extend(check_impact_acknowledgment(narration, ctx.impact_changes))

    if violations:
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in violations[:3])
        log(f"[RuleValidator] FAILED: {violations}")
        return {"pass": False, "violations": violations, "correction": f"Fix: {correction}"}

    log("[RuleValidator] Passed")
    return {"pass": True, "violations": [], "correction": ""}
