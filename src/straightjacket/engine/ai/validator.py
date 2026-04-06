#!/usr/bin/env python3
"""Constraint validator: lightweight post-narrator check.

After the narrator produces prose, the validator checks whether
the output respects engine constraints (MISS is real failure,
genre stays consistent, player agency preserved). On violation,
it returns a correction instruction for a narrator retry.

Supports up to two retries (configurable). Each retry is re-validated.
Cost: ~0.3s per check with a fast model.
"""

import json

from ..config_loader import cfg
from ..logging_util import log
from ..models import EngineConfig, GameState
from .provider_base import AIProvider, create_with_retry
from .schemas import ARCHITECT_VALIDATOR_SCHEMA, VALIDATOR_SCHEMA

# Maximum retries. Each retry re-validates. Set to 2 for Qwen (one retry
# catches ~65% of violations, two retries push above 85%).
MAX_VALIDATOR_RETRIES = 2

def validate_narration(
    provider: AIProvider,
    narration: str,
    result_type: str,
    genre: str,
    player_words: str = "",
    consequences: list | None = None,
    config: EngineConfig | None = None,
    genre_constraints: dict | None = None,
) -> dict:
    """Check narrator output against engine constraints.

    Args:
        narration: The narrator's prose output.
        result_type: "MISS", "WEAK_HIT", "STRONG_HIT", "dialog", or "opening".
        genre: The game's genre string (from setting_genre).
        player_words: What the player actually typed.
        consequences: Mechanical consequences from apply_consequences.
        config: Engine config for language.
        genre_constraints: Setting-specific constraints dict with keys
            forbidden_terms, forbidden_concepts, genre_test. If None,
            genre fidelity check is skipped.

    Returns:
        Dict with "pass" (bool), "violations" (list[str]), "correction" (str).
        On API failure, returns pass=True (fail-open, don't block gameplay).
    """
    _c = cfg()
    cons_text = ", ".join(consequences) if consequences else "none"

    gc = genre_constraints or {}
    forbidden_terms = gc.get("forbidden_terms", [])
    forbidden_concepts = gc.get("forbidden_concepts", [])
    genre_test = gc.get("genre_test", "")

    if forbidden_terms or forbidden_concepts or genre_test:
        genre_section = "2. GENRE FIDELITY: The narration must stay within the genre."
        if forbidden_terms:
            genre_section += f" Forbidden words: {', '.join(forbidden_terms)}."
        if forbidden_concepts:
            genre_section += " Forbidden concepts: " + "; ".join(forbidden_concepts) + "."
        if genre_test:
            genre_section += f" TEST: {genre_test}"
    else:
        genre_section = "2. GENRE FIDELITY: No specific genre constraints for this setting. Skip this check."

    system = f"""Constraint checker for an RPG narrator. You receive narration and mechanical context.
Check these constraints and ONLY these. Be STRICT — when in doubt, flag it.

1. RESULT INTEGRITY: If result_type is MISS, the narration must show concrete failure — the situation is worse, not a learning experience, not a silver lining, not "but at least...". If WEAK_HIT, there must be a real cost visible in the prose BUT the character must achieve their goal partially — not total defeat, not unconsciousness, not capture. If STRONG_HIT, success should be clean.

{genre_section}

3. PLAYER AGENCY: The narrator must not decide what the player character thinks, feels, plans, or decides next. The narrator must not invent memories, backstory, or past experiences for the player character ("You've seen one before," "You remember," "You knew"). The narrator must not skip ahead past the player's stated action. The narrator must not ignore the stated action.

4. RESOLUTION PACING: The narrator must not resolve mysteries, conflicts, or tensions prematurely. Specific checks:
- A new secret must not be explained in the same scene it is introduced.
- NPCs must not name, identify, or explain mysterious objects the player just discovered.
- An NPC who is asked a specific question must answer ONLY that question — they must NOT volunteer accusations, theories, connections to other events, or information the player did not ask about. One question asked = one fragment answered.
- A new NPC must not deliver a monologue that explains the plot on their first appearance.
- Tension introduced in this scene must survive to the next scene.

5. SPEECH HANDLING: If <player_words> contains a described action rather than literal dialog (e.g. "I ask about the fire" rather than exact quoted speech), the narration must NOT quote it as literal dialog. It should be narrated as indirect speech or action description.

If ALL constraints are met, return pass=true with empty violations and correction.
If ANY constraint is violated, return pass=false with specific violations and a one-sentence correction instruction."""

    prompt = f"""<narration>{narration[:2500]}</narration>
<context result_type="{result_type}" genre="{genre}" consequences="{cons_text}"/>
<player_words>{player_words[:300]}</player_words>
Check all constraints. Be strict on MISS (must be real failure) and resolution pacing (NPCs answer only what was asked, no info dumps)."""

    try:
        response = create_with_retry(
            provider, max_retries=1,
            model=_c.ai.brain_model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=VALIDATOR_SCHEMA,
            temperature=0.2,
            top_p=0.9,
        )
        result = json.loads(response.content)
        passed = result.get("pass", True)
        violations = result.get("violations", [])
        if not passed:
            log(f"[Validator] FAILED: {violations}")
        else:
            log("[Validator] Passed")
        return result

    except Exception as e:
        log(f"[Validator] Check failed ({e}), passing by default", level="warning")
        return {"pass": True, "violations": [], "correction": ""}

def validate_and_retry(
    provider: AIProvider,
    narration: str,
    prompt: str,
    result_type: str,
    game: GameState,
    player_words: str = "",
    consequences: list | None = None,
    config: EngineConfig | None = None,
    max_retries: int = MAX_VALIDATOR_RETRIES,
) -> tuple[str, dict]:
    """Validate narration and retry up to max_retries times on failure.

    Each retry appends the correction instruction to the prompt, calls the
    narrator again, parses the response, and re-validates the new output.

    Genre constraints are loaded from the active setting package if available.

    Returns:
        (narration, report) where report contains:
            passed: bool — final pass/fail status
            retries: int — number of retries actually performed
            violations: list[str] — violations from the last failed check (empty if passed)
            checks: list[dict] — full trail of every validation check
    """
    from ..ai.narrator import call_narrator
    from ..datasworn.settings import active_package
    from ..parser import parse_narrator_response

    # Load genre constraints from setting package
    gc_dict = None
    pkg = active_package(game)
    if pkg:
        gc = pkg.genre_constraints
        gc_dict = {
            "forbidden_terms": gc.forbidden_terms,
            "forbidden_concepts": gc.forbidden_concepts,
            "genre_test": gc.genre_test,
        }

    report: dict = {"passed": True, "retries": 0, "violations": [], "checks": []}

    for attempt in range(max_retries):
        check = validate_narration(
            provider, narration, result_type, game.setting_genre,
            player_words=player_words, consequences=consequences,
            config=config, genre_constraints=gc_dict,
        )
        report["checks"].append(check)
        if check.get("pass", True) or not check.get("correction"):
            return narration, report

        correction = check["correction"]
        report["retries"] = attempt + 1
        log(f"[Validator] Retry {attempt + 1}/{max_retries}: {correction}")

        retry_prompt = prompt + f"\n<constraint_correction>{correction}</constraint_correction>"
        raw = call_narrator(provider, retry_prompt, game, config)
        narration = parse_narrator_response(game, raw)

    # Final validation after last retry (don't silently pass a bad final attempt)
    final_check = validate_narration(
        provider, narration, result_type, game.setting_genre,
        player_words=player_words, consequences=consequences,
        config=config, genre_constraints=gc_dict,
    )
    report["checks"].append(final_check)
    if not final_check.get("pass", True):
        report["passed"] = False
        report["violations"] = final_check.get("violations", [])
        log(f"[Validator] Still failing after {max_retries} retries: "
            f"{report['violations']}. Accepting best attempt.",
            level="warning")

    return narration, report

# ARCHITECT VALIDATION

def validate_architect(
    provider: AIProvider,
    blueprint: dict,
    genre: str,
    tone: str,
    genre_constraints: dict | None = None,
) -> dict:
    """Check story architect blueprint for genre fidelity.

    Uses genre_constraints from the active setting package. If no constraints
    are provided or they're empty, the blueprint passes unchanged.

    Returns the blueprint, possibly with corrected central_conflict and
    antagonist_force. On API failure, returns the blueprint unchanged.
    """
    gc = genre_constraints or {}
    forbidden_terms = gc.get("forbidden_terms", [])
    forbidden_concepts = gc.get("forbidden_concepts", [])
    genre_test = gc.get("genre_test", "")

    # No constraints = no check needed
    if not forbidden_terms and not forbidden_concepts and not genre_test:
        return blueprint

    _c = cfg()
    conflict = blueprint.get("central_conflict", "")
    antagonist = blueprint.get("antagonist_force", "")

    constraint_text = ""
    if forbidden_terms:
        constraint_text += f"Forbidden terms: {', '.join(forbidden_terms)}. "
    if forbidden_concepts:
        constraint_text += "Forbidden concepts: " + "; ".join(forbidden_concepts) + ". "
    if genre_test:
        constraint_text += f"Test: {genre_test}"

    system = f"""Genre fidelity checker for an RPG story blueprint. You receive the central_conflict and antagonist_force from a story architect.

Check for genre violations. {constraint_text}

If the blueprint passes, return pass=true with empty fields.
If it violates, return pass=false with the violations listed, and provide rewritten versions that preserve the dramatic intent but stay within genre. Keep the same scale and stakes."""

    prompt = f"""<genre>{genre}</genre>
<tone>{tone}</tone>
<central_conflict>{conflict}</central_conflict>
<antagonist_force>{antagonist}</antagonist_force>
Check genre fidelity. Be strict — if it implies anything beyond physical reality, flag it."""

    try:
        response = create_with_retry(
            provider, max_retries=1,
            model=_c.ai.brain_model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=ARCHITECT_VALIDATOR_SCHEMA,
            temperature=0.2,
            top_p=0.9,
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
        log(f"[ArchitectValidator] Check failed ({e}), blueprint unchanged",
            level="warning")
        return blueprint
