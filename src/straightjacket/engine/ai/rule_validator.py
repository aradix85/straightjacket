from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config_loader import narrator_model_family
from ..datasworn.settings import GenreConstraints
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics.impacts import impact_label
from ..models import GameState


@dataclass
class ValidationContext:
    game: GameState
    result_type: str = ""
    player_words: str = ""
    consequences: list[str] = field(default_factory=list)
    consequence_sentences: list[str] = field(default_factory=list)
    genre_constraints: GenreConstraints | None = None
    threat_names: list[str] = field(default_factory=list)
    impact_changes: list[str] = field(default_factory=list)
    target_npc_name: str = ""
    fact_budget: int = -1

    @classmethod
    def build(
        cls,
        game: GameState,
        result_type: str = "",
        player_words: str = "",
        consequences: list[str] | None = None,
        consequence_sentences: list[str] | None = None,
        genre_constraints: GenreConstraints | None = None,
        target_npc_name: str = "",
        fact_budget: int = -1,
    ) -> ValidationContext:
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
            target_npc_name=target_npc_name,
            fact_budget=fact_budget,
        )


def check_player_agency(narration: str) -> list[str]:
    prose_only = eng().compiled_pattern("validator", "quote_patterns", "strip").sub("", narration)
    templates = eng().rule_validator.violation_templates
    violations = []
    family = narrator_model_family()
    for pattern in eng().compiled_patterns_for_family("validator", "agency_patterns", family):
        matches = pattern.findall(prose_only)
        for match in matches:
            violations.append(templates["player_agency"].format(match=match.strip()))

    _rv = eng().rule_validator
    seen = set()
    unique = []
    for v in violations:
        key = v[: _rv.violation_dedup_key_length]
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique[: _rv.agency_violations_cap]


def check_result_integrity(narration: str, result_type: str) -> list[str]:
    templates = eng().rule_validator.violation_templates
    violations = []
    if result_type == "MISS":
        family = narrator_model_family()
        for pattern in eng().compiled_patterns_for_family("validator", "miss_silver_lining_patterns", family):
            m = pattern.search(narration)
            if m:
                violations.append(templates["miss_silver_lining"].format(match=m.group()))
                break
        for pattern in eng().compiled_patterns_for_family("validator", "miss_annihilation_patterns", family):
            m = pattern.search(narration)
            if m:
                violations.append(templates["miss_annihilation"].format(match=m.group()))
                break
    return violations


def check_genre_fidelity(narration: str, genre_constraints: GenreConstraints | None) -> list[str]:
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
    if not genre_constraints:
        return []
    drift_words = genre_constraints.atmospheric_drift_for(narrator_model_family())
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
    _rv = eng().rule_validator
    return [
        _rv.violation_templates["atmospheric_register"].format(
            count=len(matches), examples=", ".join(unique[: _rv.atmospheric_examples_cap])
        )
    ]


def check_output_format(narration: str) -> list[str]:
    template = eng().rule_validator.violation_templates["output_format"]
    violations = []
    for pattern, label in eng().compiled_labeled_patterns("validator", "format_patterns"):
        if pattern.search(narration):
            violations.append(template.format(label=label))
    return violations


def check_npc_monologue(narration: str) -> list[str]:
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


def check_threat_advance(narration: str, threat_names: list[str]) -> list[str]:
    if not threat_names:
        return []
    _rv = eng().rule_validator
    stopwords = eng().stopwords.consequence
    narration_lower = narration.lower()
    for name in threat_names:
        words = {w.strip(".,;:!?\"'()-").lower() for w in name.split() if len(w) >= _rv.threat_name_min_word_length}
        words -= stopwords
        if any(w in narration_lower for w in words):
            continue
        return [_rv.violation_templates["threat_advance"].format(name=name)]
    return []


def check_impact_acknowledgment(narration: str, impact_changes: list[str]) -> list[str]:
    if not impact_changes:
        return []
    _rv = eng().rule_validator
    narration_lower = narration.lower()
    for label in impact_changes:
        if label.lower() in narration_lower:
            continue

        words = [w.lower() for w in label.split() if len(w) >= _rv.impact_label_min_word_length]
        if any(w in narration_lower for w in words):
            continue
        return [_rv.violation_templates["impact_change"].format(label=label)]
    return []


def run_rule_checks(narration: str, ctx: ValidationContext) -> dict:
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
        _rv = eng().rule_validator
        correction = "; ".join(
            v.split(": ", 1)[1] if ": " in v else v for v in violations[: _rv.correction_violations_cap]
        )
        log(f"[RuleValidator] FAILED: {violations}")
        return {"pass": False, "violations": violations, "correction": f"Fix: {correction}"}

    log("[RuleValidator] Passed")
    return {"pass": True, "violations": [], "correction": ""}
