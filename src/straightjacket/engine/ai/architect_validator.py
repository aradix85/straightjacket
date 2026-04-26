"""Architect blueprint genre validation.

Extracted from validator.py. Checks story blueprints for genre fidelity
using rule-based drift detection and LLM semantic checking.
"""

import json

from ..config_loader import model_for_role, narrator_model_family, sampling_params
from ..datasworn.settings import GenreConstraints
from ..engine_loader import eng
from ..logging_util import log
from ..prompt_loader import get_prompt
from .provider_base import AIProvider, create_with_retry
from .schemas import get_architect_validator_schema


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
    drift_words = genre_constraints.atmospheric_drift_for(narrator_model_family())
    if drift_words:
        drift_lower = {w.lower() for w in drift_words}
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

    labels = eng().ai_text.architect_labels
    constraint_text = ""
    if genre_constraints.forbidden_terms:
        constraint_text += f"{labels['forbidden_terms_prefix']}: {', '.join(genre_constraints.forbidden_terms)}. "
    if genre_constraints.forbidden_concepts:
        constraint_text += (
            f"{labels['forbidden_concepts_prefix']}: " + "; ".join(genre_constraints.forbidden_concepts) + ". "
        )
    if genre_constraints.genre_test:
        constraint_text += f"{labels['genre_test_prefix']}: {genre_constraints.genre_test}"

    system = get_prompt("architect_validator_system", role="validator_architect", constraint_text=constraint_text)
    prompt = get_prompt(
        "architect_validator_user",
        role="validator_architect",
        genre=genre,
        tone=tone,
        conflict=conflict,
        antagonist=antagonist,
    )

    try:
        _vap = dict(sampling_params("validator_architect"))
        _vap["max_retries"] = eng().retry.constraint_check_max_retries
        response = create_with_retry(
            provider,
            model=model_for_role("validator_architect"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_architect_validator_schema(),
            log_role="validator_architect",
            **_vap,
        )
        result = json.loads(response.content)
        if not result["pass"]:
            violations = result.get("violations", [])
            log(f"[ArchitectValidator] FAILED: {violations}")
            fixed_conflict = result.get("fixed_conflict", "").strip()
            fixed_antagonist = result.get("fixed_antagonist", "").strip()
            _trunc = eng().truncations.log_short
            if fixed_conflict:
                log(f"[ArchitectValidator] Conflict: '{conflict[:_trunc]}' → '{fixed_conflict[:_trunc]}'")
                blueprint["central_conflict"] = fixed_conflict
            if fixed_antagonist:
                log(f"[ArchitectValidator] Antagonist: '{antagonist[:_trunc]}' → '{fixed_antagonist[:_trunc]}'")
                blueprint["antagonist_force"] = fixed_antagonist
        else:
            log("[ArchitectValidator] Passed")
        return blueprint

    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
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
        phase = act["phase"]
        fields_to_check.append((f"act[{phase}].goal", act.get("goal", "")))
        fields_to_check.append((f"act[{phase}].transition_trigger", act.get("transition_trigger", "")))

    _limits = eng().architect_limits
    _trunc = eng().truncations
    for field_name, text in fields_to_check:
        if not text:
            continue
        text_lower = text.lower()
        found = [w for w in drift_words if w in text_lower]
        if found:
            log(
                f"[ArchitectValidator] Drift words in {field_name}: "
                f"{found[: _limits.drift_words_log_window]}. Text: '{text[: _trunc.log_medium]}'",
                level="warning",
            )
