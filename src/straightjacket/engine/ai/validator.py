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
import re

from ..config_loader import cfg
from ..logging_util import log
from ..models import EngineConfig, GameState
from .provider_base import AIProvider, create_with_retry
from .schemas import ARCHITECT_VALIDATOR_SCHEMA, VALIDATOR_SCHEMA


def _strip_prompt_for_retry(prompt: str, violations: list[str]) -> str:
    """Reduce NPC context in the prompt when violations suggest information leaking.

    For RESOLUTION PACING violations: strip NPC secrets and memories from the prompt.
    The model can't leak what it doesn't have. NPC names, dispositions, and basic
    traits remain so the narrator can still write them in-character.
    """
    has_pacing = any("resolution pacing" in v.lower() or "monologue" in v.lower() for v in violations)
    if not has_pacing:
        return prompt

    stripped = prompt
    # Remove secrets from target_npc blocks
    stripped = re.sub(
        r"secrets\(weave subtly,never reveal\):\[.*?\]",
        "secrets:[]",
        stripped,
        flags=re.DOTALL,
    )
    # Remove memory lines (recent: ... and insight: ...)
    stripped = re.sub(r"^(?:recent|insight):.*$", "", stripped, flags=re.MULTILINE)
    # Remove agenda lines (NPCs with less agenda = less monologue fuel)
    stripped = re.sub(r"^agenda:.*$", "agenda:(follow the scene)", stripped, flags=re.MULTILINE)

    if stripped != prompt:
        log("[Validator] Stripped NPC secrets/memories/agenda from retry prompt")
    return stripped


def validate_narration(
    provider: AIProvider,
    narration: str,
    result_type: str,
    genre: str,
    player_words: str = "",
    player_name: str = "",
    consequences: list | None = None,
    config: EngineConfig | None = None,
    genre_constraints: dict | None = None,
) -> dict:
    """Check narrator output against engine constraints.

    Both layers always run, results are merged:
    1. Rule-based (instant): player agency patterns, result integrity,
       genre fidelity, output format, NPC monologue heuristic.
    2. LLM (semantic): resolution pacing, subtle agency, contextual checks.

    Returns:
        Dict with "pass" (bool), "violations" (list[str]), "correction" (str).
    """
    from .rule_validator import run_rule_checks

    # Layer 1: rule-based (instant, free)
    rule_result = run_rule_checks(narration, result_type, player_words, genre_constraints)
    rule_violations = rule_result.get("violations", [])

    # Layer 2: LLM (semantic)
    llm_violations = []
    _c = cfg()
    cons_text = ", ".join(consequences) if consequences else "none"
    pc_hint = f' The player character is "{player_name}" (the "you").' if player_name else ""

    system = f"""Constraint checker for RPG narration. Be STRICT but PRECISE.

RESOLUTION PACING: NPCs answer ONLY the specific question asked — no volunteering theories, connections, accusations, or context the player did not request. A new mystery must not be explained in the scene it appears. A new NPC must not monologue. Tension introduced must survive to the next scene.

PLAYER AGENCY: This applies ONLY to the player character (the "you" in narration).{pc_hint} NPCs MAY think, feel, remember, interpret — that is good characterization, not a violation. The narrator must not impose thoughts, feelings, interpretations, or memories on the PLAYER CHARACTER. "You see the door" = OK. "You see the fear in her eyes" = violation (imposes interpretation). "You notice she is trembling" = OK (observable). "You understand why she is trembling" = violation (imposes interpretation).

RESULT INTEGRITY: If result_type is MISS, the failure must be concrete — no learning, no silver lining, no disguised success. If WEAK_HIT, there must be a SPECIFIC tangible cost visible in the prose: something broken, lost, spent, damaged, or worsened. Atmospheric tension alone is not a cost. "The fuel cell cracks" = cost. "The air feels heavier" = not a cost. If dialog, skip this check.

Return pass=true if ALL constraints met.
Return pass=false with:
- violations: list each as "CATEGORY: what specifically went wrong"
- correction: one sentence naming the exact problem and what to do instead"""

    prompt = f"""<narration>{narration[:4000]}</narration>
<context result_type="{result_type}" genre="{genre}" consequences="{cons_text}"/>
<player_words>{player_words[:500]}</player_words>
Check constraints."""

    try:
        response = create_with_retry(
            provider,
            max_retries=1,
            model=_c.ai.brain_model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=VALIDATOR_SCHEMA,
            temperature=0.2,
            top_p=0.9,
        )
        result = json.loads(response.content)
        if not result.get("pass", True):
            llm_violations = result.get("violations", [])
    except Exception as e:
        log(f"[Validator] LLM check failed ({e}), using rule results only", level="warning")

    # Merge: deduplicate by category prefix, tag source for diagnostics
    all_violations = [f"[rule] {v}" for v in rule_violations]
    rule_categories = {v.split(":")[0].strip() for v in rule_violations}
    for v in llm_violations:
        cat = v.split(":")[0].strip()
        if cat not in rule_categories:
            all_violations.append(f"[llm] {v}")

    if all_violations:
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:3])
        log(f"[Validator] FAILED ({len(rule_violations)} rule, {len(llm_violations)} llm): {all_violations}")
        return {"pass": False, "violations": all_violations, "correction": f"Fix: {correction}"}

    log("[Validator] Passed (rule + llm)")
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
    max_retries: int | None = None,
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

    # Resolve max_retries from config if not explicitly passed
    if max_retries is None:
        max_retries = cfg().ai.max_retries.narrator

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

    # Track all attempts: (narration, violation_count, check_result)
    attempts: list[tuple[str, int, dict]] = []

    for attempt in range(max_retries):
        check = validate_narration(
            provider,
            narration,
            result_type,
            game.setting_genre,
            player_words=player_words,
            player_name=game.player_name,
            consequences=consequences,
            config=config,
            genre_constraints=gc_dict,
        )
        report["checks"].append(check)
        violations = check.get("violations", [])
        attempts.append((narration, len(violations), check))

        if check.get("pass", True) or not check.get("correction"):
            return narration, report

        report["retries"] = attempt + 1
        log(f"[Validator] Retry {attempt + 1}/{max_retries}: {violations}")

        # Build concrete rewrite instructions per violation type.
        # Tell the model what to DO, not just what it did wrong.
        # Strip diagnostic tags before matching.
        rewrite_instructions = []
        for v in violations:
            vl = re.sub(r"^\[(?:rule|llm)\]\s*", "", v).lower()
            if "player agency" in vl:
                rewrite_instructions.append(
                    "Remove sentences where the PLAYER CHARACTER (the 'you') thinks, "
                    "feels, realizes, interprets, or remembers. NPCs may think and feel "
                    "freely. Describe only what the player character PERCEIVES."
                )
            elif "resolution pacing" in vl or "monologue" in vl:
                rewrite_instructions.append(
                    "Cut the NPC's speech to answer ONLY the specific question asked. "
                    "Remove all volunteered theories, explanations, connections. "
                    "One short answer, then the NPC stops or acts."
                )
            elif "result integrity" in vl and "silver" in vl:
                rewrite_instructions.append(
                    "Remove any positive outcome. The MISS ends with the situation "
                    "worse than before. No learning, no lucky break."
                )
            elif "result integrity" in vl and "annihilation" in vl:
                rewrite_instructions.append(
                    "Reduce the severity. A MISS is a setback: injury, lost ground, "
                    "broken equipment. Not death or total defeat."
                )
            elif "result integrity" in vl and ("cost" in vl or "weak" in vl):
                rewrite_instructions.append(
                    "Add a SPECIFIC tangible cost for the WEAK_HIT: something breaks, "
                    "is lost, is spent, or worsens. Atmosphere alone is not a cost. "
                    "Name the thing that is damaged or lost."
                )
            elif "genre fidelity" in vl:
                rewrite_instructions.append(
                    "Remove the forbidden genre element. Replace with something that fits the world's rules."
                )
            elif "output format" in vl:
                rewrite_instructions.append(
                    "Remove all metadata, brackets, markdown, role labels. Begin with narrative prose."
                )
            else:
                rewrite_instructions.append(f"Fix: {v}")
        # Deduplicate identical instructions
        seen: set[str] = set()
        unique_instructions = []
        for inst in rewrite_instructions:
            if inst not in seen:
                seen.add(inst)
                unique_instructions.append(inst)

        instructions_text = "\n".join(f"- {inst}" for inst in unique_instructions)
        system_suffix = (
            f"\n<correction_mode>\n"
            f"Your previous narration was rejected. Rewrite following these instructions:\n"
            f"{instructions_text}\n"
            f"</correction_mode>"
        )
        retry_prompt = f"<REWRITE>\n{instructions_text}\n</REWRITE>\n\n" + prompt
        # Strip NPC secrets/memories if pacing violation — remove fuel for info dumps.
        retry_prompt = _strip_prompt_for_retry(retry_prompt, violations)
        # Skip narration_history — previous narrations may contain the same
        # violations and act as poisoned few-shot examples.
        raw = call_narrator(provider, retry_prompt, game, config, system_suffix=system_suffix, skip_history=True)
        narration = parse_narrator_response(game, raw)

    # Final validation of last attempt
    final_check = validate_narration(
        provider,
        narration,
        result_type,
        game.setting_genre,
        player_words=player_words,
        player_name=game.player_name,
        consequences=consequences,
        config=config,
        genre_constraints=gc_dict,
    )
    report["checks"].append(final_check)
    final_violations = final_check.get("violations", [])
    attempts.append((narration, len(final_violations), final_check))

    if not final_check.get("pass", True):
        # Pick the attempt with the fewest violations
        best_narration, best_count, best_check = min(attempts, key=lambda a: a[1])
        report["passed"] = False
        report["violations"] = best_check.get("violations", [])
        if best_count < len(final_violations):
            log(
                f"[Validator] Picking attempt with {best_count} violations "
                f"over final attempt with {len(final_violations)}.",
                level="warning",
            )
            narration = best_narration
        else:
            log(
                f"[Validator] Still failing after {max_retries} retries: "
                f"{report['violations']}. Accepting best attempt.",
                level="warning",
            )

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
            provider,
            max_retries=1,
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
        log(f"[ArchitectValidator] Check failed ({e}), blueprint unchanged", level="warning")
        return blueprint
