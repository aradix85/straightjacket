#!/usr/bin/env python3
"""Architect blueprint genre validation.

Extracted from validator.py. Checks story blueprints for genre fidelity
using rule-based drift detection and LLM semantic checking.
"""

import json

from ..config_loader import model_for_role, sampling_params
from ..datasworn.settings import GenreConstraints
from ..logging_util import log
from ..prompt_loader import get_prompt
from .provider_base import AIProvider, create_with_retry
from .schemas import ARCHITECT_VALIDATOR_SCHEMA


def validate_architect(
    provider: AIProvider,
    blueprint: dict,
    genre: str,
    tone: str,
    genre_constraints: GenreConstraints | None = None,
) -> dict:
    """Check story architect blueprint for genre fidelity.

    Two layers:
    1. Rule-based: check all text fields against atmospheric_drift words.
    2. LLM: check central_conflict and antagonist_force semantically.

    Returns the blueprint, possibly with corrected fields.
    On API failure, returns the blueprint with only rule-based fixes applied.
    """
    if genre_constraints is None:
        return blueprint

    # Layer 1: rule-based drift check on all blueprint text fields
    if genre_constraints.atmospheric_drift:
        drift_lower = {w.lower() for w in genre_constraints.atmospheric_drift}
        _check_blueprint_text_fields(blueprint, drift_lower)

    # No LLM constraints = skip LLM check
    if (
        not genre_constraints.forbidden_terms
        and not genre_constraints.forbidden_concepts
        and not genre_constraints.genre_test
    ):
        return blueprint

    conflict = blueprint.get("central_conflict", "")
    antagonist = blueprint.get("antagonist_force", "")

    constraint_text = ""
    if genre_constraints.forbidden_terms:
        constraint_text += f"Forbidden terms: {', '.join(genre_constraints.forbidden_terms)}. "
    if genre_constraints.forbidden_concepts:
        constraint_text += "Forbidden concepts: " + "; ".join(genre_constraints.forbidden_concepts) + ". "
    if genre_constraints.genre_test:
        constraint_text += f"Test: {genre_constraints.genre_test}"

    system = get_prompt("architect_validator_system", constraint_text=constraint_text)
    prompt = get_prompt(
        "architect_validator_user",
        genre=genre,
        tone=tone,
        conflict=conflict,
        antagonist=antagonist,
    )

    try:
        _vap = dict(sampling_params("validator_architect"))
        _vap["max_retries"] = 1
        response = create_with_retry(
            provider,
            model=model_for_role("validator_architect"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=ARCHITECT_VALIDATOR_SCHEMA,
            log_role="validator_architect",
            **_vap,
        )
        result = json.loads(response.content)
        if not result.get("pass", True):
            violations = result.get("violations", [])
            log(f"[ArchitectValidator] FAILED: {violations}")
            fixed_conflict = result.get("fixed_conflict", "").strip()
            fixed_antagonist = result.get("fixed_antagonist", "").strip()
            if fixed_conflict:
                log(f"[ArchitectValidator] Conflict: '{conflict[:60]}' → '{fixed_conflict[:60]}'")
                blueprint["central_conflict"] = fixed_conflict
            if fixed_antagonist:
                log(f"[ArchitectValidator] Antagonist: '{antagonist[:60]}' → '{fixed_antagonist[:60]}'")
                blueprint["antagonist_force"] = fixed_antagonist
        else:
            log("[ArchitectValidator] Passed")
        return blueprint

    except Exception as e:
        log(f"[ArchitectValidator] Check failed ({e}), blueprint unchanged", level="warning")
        return blueprint


def _check_blueprint_text_fields(blueprint: dict, drift_words: set[str]) -> None:
    """Rule-based drift check on blueprint text fields."""
    fields_to_check = [
        ("central_conflict", blueprint.get("central_conflict", "")),
        ("antagonist_force", blueprint.get("antagonist_force", "")),
        ("thematic_thread", blueprint.get("thematic_thread", "")),
    ]
    for act in blueprint.get("acts", []):
        phase = act.get("phase", "?")
        fields_to_check.append((f"act[{phase}].goal", act.get("goal", "")))
        fields_to_check.append((f"act[{phase}].transition_trigger", act.get("transition_trigger", "")))

    for field_name, text in fields_to_check:
        if not text:
            continue
        text_lower = text.lower()
        found = [w for w in drift_words if w in text_lower]
        if found:
            log(
                f"[ArchitectValidator] Drift words in {field_name}: {found[:5]}. Text: '{text[:80]}'",
                level="warning",
            )
