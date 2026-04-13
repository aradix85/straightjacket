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

from ..config_loader import model_for_role, sampling_params
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
    consequence_sentences: list[str] | None = None,
) -> dict:
    """Check narrator output against engine constraints.

    Two layers, short-circuit on rule failures:
    1. Rule-based (instant): player agency patterns, result integrity,
       genre fidelity, output format, NPC monologue heuristic, consequence keywords.
    2. LLM (semantic): resolution pacing, subtle agency, contextual checks.
       Skipped when rule-based already found violations (fast retry path).

    Returns:
        Dict with "pass" (bool), "violations" (list[str]), "correction" (str).
    """
    from .rule_validator import run_rule_checks

    # Layer 1: rule-based (instant, free)
    rule_result = run_rule_checks(
        narration, result_type, player_words, genre_constraints, consequence_sentences, player_name
    )
    rule_violations = rule_result.get("violations", [])

    # Fast path: rule violations found → skip LLM, retry immediately
    if rule_violations:
        all_violations = [f"[rule] {v}" for v in rule_violations]
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:3])
        log(f"[Validator] FAILED (rule fast path, {len(rule_violations)} violations): {all_violations}")
        return {"pass": False, "violations": all_violations, "correction": f"Fix: {correction}"}

    # Layer 2: LLM (semantic) — only when rules passed
    llm_violations = []
    cons_text = ", ".join(consequences) if consequences else "none"
    pc_hint = f' The player character is "{player_name}" (the "you").' if player_name else ""
    cons_sentence_text = ""
    if consequence_sentences:
        cons_sentence_text = (
            "\n\nCONSEQUENCE COMPLIANCE: Each consequence below MUST be reflected in the narration. "
            "The narrator may use different words but the event described MUST visibly occur. "
            "If a consequence is completely absent from the prose, flag it.\n"
            + "\n".join(f"- {s}" for s in consequence_sentences)
        )

    system = f"""Constraint checker for RPG narration. Be STRICT and PRECISE.

GENRE PHYSICS: Materials MUST NOT exhibit consciousness, memory, or transformation. Wood does not weep, bleed, reshape, or form faces. Stone does not remember. Fluids do not change color symbolically. Inanimate objects MUST NOT have agency, awareness, or intent. If the setting is low-magic or grounded sci-fi, ANY supernatural element is a violation. When in doubt about genre physics, FAIL — genre drift is harder to fix than a retry.

RESOLUTION PACING: NPCs respond to what was asked or done — nothing more. The test is INFORMATION, not length.
VIOLATION: NPC volunteers facts, theories, names, locations, or connections that the player did not ask about and has not earned through a successful move. Each NPC response should contain at most ONE new fact beyond the direct answer.
ALLOWED: NPC speaks at length IF every sentence responds to the player's action or question. Emotional reactions, resistance, physical actions, and atmosphere are always fine regardless of length.
IMPORTANT: Do NOT count sentences. Sentence count is NEVER a violation. An NPC speaking three, four, or ten sentences is FINE if they are all responsive to the player. Only flag unsolicited NEW FACTS.
WRONG: Player asks where the ship docked. NPC answers, then adds that Ashwatch burned, the woman disappeared, and she had debts — three unsolicited facts.
WRONG: Player asks about tracks. NPC identifies the stride, names the hatch, and suggests checking the forges — volunteering a plan the player didn't ask for.
RIGHT: Player asks where the ship docked. NPC says it was the eastern pier, hesitates, then looks away. One fact, one reaction.
RIGHT: Player compels an NPC. NPC argues back, deflects, eventually gives in with a grudging answer. Long exchange, but every sentence is a response to pressure.
RIGHT: NPC gives orders during a crisis — "Lock the hatch, reroute power, brace for impact." These are reactive, not unsolicited facts.
A new mystery must not be explained in the scene it appears. Tension introduced must survive to the next scene.

PLAYER AGENCY: This applies ONLY to the player character (the "you" in narration).{pc_hint}
TWO CATEGORIES — only the first is a violation:
COGNITIVE (VIOLATION): The narrator decides what the player character thinks, concludes, realizes, remembers, decides, believes, or intends. "you realize", "you understand why", "you decide to trust him", "you remember the promise", "makes you want to", "something inside you". These take choices away from the player.
SENSORY (ALLOWED): The narrator describes how things feel, look, sound, smell to the player character — including subjective or metaphorical descriptions. "unnervingly white", "sharp enough to cut", "silence feels heavy", "cold enough to bite", "the air tastes of copper". These create atmosphere and are ALWAYS allowed. PASS these.
NPC EXCEPTION: Any description of an NPC's behavior, demeanor, or emotional state is ALWAYS allowed. "hollow", "mechanical", "guarded", "stripped of emotion" about an NPC = PASS.

RESULT INTEGRITY: If result_type is MISS, the failure must be concrete — the situation is WORSE than before. What is NOT allowed: the player character LEARNS, DISCOVERS, GAINS insight, or makes PROGRESS. If WEAK_HIT, there must be a SPECIFIC tangible cost: something broken, lost, spent, damaged. Atmospheric tension alone is not a cost. If STRONG_HIT or dialog, skip this check entirely — STRONG_HIT is clean success with no required cost.
{cons_sentence_text}
DOUBT RULES:
- PLAYER AGENCY: flag ONLY cognitive violations (thoughts, decisions, conclusions, memories). Sensory descriptions and atmospheric metaphors are NEVER violations — PASS those without hesitation.
- RESOLUTION PACING: flag ONLY when the NPC volunteers unsolicited facts — names, locations, theories, plans — that the player did not ask about. Length alone is NEVER a violation. Emotional reactions, resistance, and physical actions are ALWAYS allowed.
- GENRE PHYSICS: when in doubt, FAIL — genre drift compounds.

Return pass=true if ALL constraints met.
Return pass=false with:
- violations: list each as "CATEGORY: what specifically went wrong"
- correction: one sentence naming the exact problem and what to do instead"""

    prompt = f"""<narration>{narration[:4000]}</narration>
<context result_type="{result_type}" genre="{genre}" consequences="{cons_text}"/>
<player_words>{player_words[:500]}</player_words>
Check constraints."""

    try:
        _vp = sampling_params("validator")
        _vp["max_retries"] = 1  # Single attempt for LLM constraint check
        response = create_with_retry(
            provider,
            model=model_for_role("validator"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=VALIDATOR_SCHEMA,
            log_role="validator",
            **_vp,
        )
        content = response.content.strip()
        if not content:
            # Empty response from json_schema mode — retry without schema
            log("[Validator] Empty response from json_schema, retrying without schema")
            _vp2 = sampling_params("validator")
            _vp2["max_retries"] = 1
            response = create_with_retry(
                provider,
                model=model_for_role("validator"),
                system=system
                + '\n\nRespond with ONLY a JSON object: {"pass": true/false, "violations": [...], "correction": "..."}',
                messages=[{"role": "user", "content": prompt}],
                log_role="validator",
                **_vp2,
            )
            content = response.content.strip()
        if content:
            # Try direct parse, then extract from fenced blocks
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                from .brain import _extract_json

                result = _extract_json(content)
            if result and not result.get("pass", True):
                llm_violations = result.get("violations", [])
    except Exception as e:
        log(f"[Validator] LLM check failed ({e}), using rule results only", level="warning")

    if llm_violations:
        all_violations = [f"[llm] {v}" for v in llm_violations]
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:3])
        log(f"[Validator] FAILED ({len(llm_violations)} llm): {all_violations}")
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
    consequence_sentences: list[str] | None = None,
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
        max_retries = sampling_params("narrator").get("max_retries", 3)

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
        # Atmospheric register control from raw config
        raw_gc = pkg.raw_config.get("genre_constraints", {})
        if "atmospheric_drift" in raw_gc:
            gc_dict["atmospheric_drift"] = raw_gc["atmospheric_drift"]
            gc_dict["atmospheric_drift_threshold"] = raw_gc.get("atmospheric_drift_threshold", 3)

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
            consequence_sentences=consequence_sentences,
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
            elif "genre physics" in vl:
                rewrite_instructions.append(
                    "Materials MUST NOT exhibit consciousness, memory, or transformation. "
                    "Wood does not weep, bleed, or form faces. Stone does not remember. "
                    "Replace ALL supernatural material behavior with physical description "
                    "from <sensory_palette>: grain, cracks, stains, weathering, temperature."
                )
            elif "atmospheric register" in vl:
                rewrite_instructions.append(
                    "Too many supernatural/horror words (pulse, hum, thrum, whisper, glow, shimmer, "
                    "weep, ooze, writhe, visage, reshape). "
                    "Replace with physical sensations from the <sensory_palette>: mud, iron, cold, "
                    "woodsmoke, wind, creaking wood, weight, texture, temperature."
                )
            elif "output format" in vl:
                rewrite_instructions.append(
                    "Remove all metadata, brackets, markdown, role labels. Begin with narrative prose."
                )
            elif "consequence missing" in vl:
                rewrite_instructions.append(
                    "Each <consequence> tag describes something that MUST happen in this scene. "
                    "Show every consequence in the prose — the player must see it occur."
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
        retry_prompt = _strip_prompt_for_retry(prompt, violations)
        # Include the failed narration as assistant turn + correction as user turn.
        # This gives the model its own output to correct rather than rewriting blind.
        failed_narration_msg = {"role": "assistant", "content": narration}
        correction_msg = {
            "role": "user",
            "content": f"<REWRITE>\nYour narration above violated constraints:\n{instructions_text}\n"
            f"Rewrite the COMPLETE scene following the original prompt below. "
            f"Keep what worked, fix what was flagged.\n</REWRITE>\n\n{retry_prompt}",
        }
        # Skip narration_history — previous narrations may contain the same
        # violations and act as poisoned few-shot examples.
        raw = call_narrator(
            provider,
            retry_prompt,
            game,
            config,
            system_suffix=system_suffix,
            skip_history=True,
            extra_messages=[failed_narration_msg, correction_msg],
        )
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
        consequence_sentences=consequence_sentences,
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

    Two layers:
    1. Rule-based: check all text fields against atmospheric_drift words.
    2. LLM: check central_conflict and antagonist_force semantically.

    Returns the blueprint, possibly with corrected fields.
    On API failure, returns the blueprint with only rule-based fixes applied.
    """
    gc = genre_constraints or {}
    forbidden_terms = gc.get("forbidden_terms", [])
    forbidden_concepts = gc.get("forbidden_concepts", [])
    genre_test = gc.get("genre_test", "")
    drift_words = gc.get("atmospheric_drift", [])

    # Layer 1: rule-based drift check on all blueprint text fields
    if drift_words:
        drift_lower = {w.lower() for w in drift_words}
        _check_blueprint_text_fields(blueprint, drift_lower)

    # No LLM constraints = skip LLM check
    if not forbidden_terms and not forbidden_concepts and not genre_test:
        return blueprint

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
        _vap = sampling_params("validator_architect")
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
    """Rule-based drift check on blueprint text fields.

    Scans central_conflict, antagonist_force, thematic_thread, and each act's
    goal and transition_trigger for atmospheric drift words. Logs findings but
    does not auto-rewrite free text — the mood sanitizer in architect.py handles moods.
    """
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
