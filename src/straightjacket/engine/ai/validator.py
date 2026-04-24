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
from ..datasworn.settings import active_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import EngineConfig, GameState
from ..parser import parse_narrator_response
from .json_utils import extract_json
from ..prompt_loader import get_prompt
from .narrator import call_narrator
from .provider_base import AIProvider, create_with_retry
from .rule_validator import ValidationContext, run_rule_checks
from .schemas import get_validator_schema


def _strip_prompt_for_retry(prompt: str, violations: list[str]) -> str:
    """Reduce NPC context in the prompt when violations suggest information leaking.

    For RESOLUTION PACING violations: strip NPC secrets and memories from the prompt.
    The model can't leak what it doesn't have. NPC names, dispositions, and basic
    traits remain so the narrator can still write them in-character.
    """
    has_pacing = any("resolution pacing" in v.lower() or "monologue" in v.lower() for v in violations)
    if not has_pacing:
        return prompt

    retry_strip = eng().get_raw("validator")["retry_strip"]

    stripped = prompt
    # Remove secrets from target_npc blocks. Match the structural shape
    # `secrets(<any label>):[<json array>]` so the regex survives any edit
    # to the `secrets_label` yaml value.
    stripped = re.sub(
        r"secrets\([^)]*\):\[.*?\]",
        retry_strip["empty_secrets"],
        stripped,
        flags=re.DOTALL,
    )
    # Remove memory lines (recent: ... and insight: ...)
    stripped = re.sub(r"^(?:recent|insight):.*$", "", stripped, flags=re.MULTILINE)
    # Remove agenda lines (NPCs with less agenda = less monologue fuel)
    stripped = re.sub(r"^agenda:.*$", retry_strip["agenda_placeholder"], stripped, flags=re.MULTILINE)

    if stripped != prompt:
        log("[Validator] Stripped NPC secrets/memories/agenda from retry prompt")
    return stripped


def validate_narration(
    provider: AIProvider,
    narration: str,
    ctx: ValidationContext,
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

    # Layer 1: rule-based (instant, free)
    rule_result = run_rule_checks(narration, ctx)
    rule_violations = rule_result.get("violations", [])

    # Fast path: rule violations found → skip LLM, retry immediately
    if rule_violations:
        _cap = eng().rule_validator.correction_violations_cap
        all_violations = [f"[rule] {v}" for v in rule_violations]
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:_cap])
        log(f"[Validator] FAILED (rule fast path, {len(rule_violations)} violations): {all_violations}")
        return {"pass": False, "violations": all_violations, "correction": f"Fix: {correction}"}

    # Layer 2: LLM (semantic) — only when rules passed
    llm_violations = []
    cons_text = ", ".join(ctx.consequences) if ctx.consequences else "none"
    player_name = ctx.game.player_name
    pc_hint = get_prompt("validator_pc_hint", player_name=player_name) if player_name else ""
    cons_sentence_text = ""
    if ctx.consequence_sentences:
        cons_sentence_text = get_prompt(
            "validator_consequence_compliance",
            consequence_list="\n".join(f"- {s}" for s in ctx.consequence_sentences),
        )

    system = get_prompt(
        "validator_system",
        pc_hint=pc_hint,
        consequence_compliance_block=cons_sentence_text,
    )

    _trunc = eng().truncations
    prompt = f"""<narration>{narration[: _trunc.narration_max]}</narration>
<context result_type="{ctx.result_type}" genre="{ctx.game.setting_genre}" consequences="{cons_text}"/>
<player_words>{ctx.player_words[: _trunc.prompt_long]}</player_words>
Check constraints."""

    try:
        _vp = dict(sampling_params("validator"))
        _vp["max_retries"] = eng().retry.constraint_check_max_retries
        response = create_with_retry(
            provider,
            model=model_for_role("validator"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_validator_schema(),
            log_role="validator",
            **_vp,
        )
        content = response.content.strip()
        if not content:
            # Empty response from json_schema mode — retry without schema
            log("[Validator] Empty response from json_schema, retrying without schema")
            _vp2 = dict(sampling_params("validator"))
            _vp2["max_retries"] = 1
            response = create_with_retry(
                provider,
                model=model_for_role("validator"),
                system=system + get_prompt("validator_json_suffix"),
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
                result = extract_json(content)
            if result and not result["pass"]:
                llm_violations = result.get("violations", [])
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(f"[Validator] LLM check failed ({e}), using rule results only", level="warning")

    if llm_violations:
        _cap = eng().rule_validator.correction_violations_cap
        all_violations = [f"[llm] {v}" for v in llm_violations]
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:_cap])
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
    Threat names and player info are derived from game state via ValidationContext.

    Returns:
        (narration, report) where report contains:
            passed: bool — final pass/fail status
            retries: int — number of retries actually performed
            violations: list[str] — violations from the last failed check (empty if passed)
            checks: list[dict] — full trail of every validation check
    """
    # Resolve max_retries from cluster config if not explicitly passed.
    # sampling_params always returns a dict with max_retries (required field).
    if max_retries is None:
        max_retries = sampling_params("narrator")["max_retries"]

    # Load genre constraints from setting package (typed — no dict conversion)
    gc = None
    pkg = active_package(game)
    if pkg:
        gc = pkg.genre_constraints

    # Build validation context once — all checks share it
    val_ctx = ValidationContext.build(
        game,
        result_type=result_type,
        player_words=player_words,
        consequences=consequences,
        consequence_sentences=consequence_sentences,
        genre_constraints=gc,
    )

    report: dict = {"passed": True, "retries": 0, "violations": [], "checks": []}

    # Track all attempts: (narration, violation_count, check_result)
    attempts: list[tuple[str, int, dict]] = []

    for attempt in range(max_retries):
        check = validate_narration(provider, narration, val_ctx)
        report["checks"].append(check)
        violations = check.get("violations", [])
        attempts.append((narration, len(violations), check))

        if check["pass"] or not check.get("correction"):
            return narration, report

        report["retries"] = attempt + 1
        log(f"[Validator] Retry {attempt + 1}/{max_retries}: {violations}")

        # Build concrete rewrite instructions per violation type.
        # Tell the model what to DO, not just what it did wrong.
        # Strip diagnostic tags before matching. Rules live in engine.yaml
        # validator.rewrite_instructions. Keys containing ' AND ' require all
        # parts to be substrings of the violation; plain keys are single-substring.
        # A violation that matches no rule falls through as "Fix: <raw>" — that
        # is intentional LLM behavior, not a config fallback.
        rules = eng().get_raw("validator")["rewrite_instructions"]
        _vblocks = eng().ai_text.validator_blocks
        rewrite_instructions = []
        for v in violations:
            vl = re.sub(r"^\[(?:rule|llm)\]\s*", "", v).lower()
            matched = None
            for key, template in rules.items():
                parts = [p.strip() for p in key.split(" AND ")]
                if all(p in vl for p in parts):
                    matched = template
                    break
            rewrite_instructions.append(
                matched if matched else _vblocks["unmatched_violation_template"].format(violation=v)
            )
        # Deduplicate identical instructions
        seen: set[str] = set()
        unique_instructions = []
        for inst in rewrite_instructions:
            if inst not in seen:
                seen.add(inst)
                unique_instructions.append(inst)

        instructions_text = "\n".join(f"- {inst}" for inst in unique_instructions)
        system_suffix = (
            f"\n<correction_mode>\n{_vblocks['correction_mode_open']}\n{instructions_text}\n</correction_mode>"
        )
        retry_prompt = _strip_prompt_for_retry(prompt, violations)
        # Include the failed narration as assistant turn + correction as user turn.
        # This gives the model its own output to correct rather than rewriting blind.
        failed_narration_msg = {"role": "assistant", "content": narration}
        correction_msg = {
            "role": "user",
            "content": f"<REWRITE>\n{_vblocks['rewrite_user_prefix']}\n{instructions_text}\n"
            f"{_vblocks['rewrite_user_suffix']}\n</REWRITE>\n\n{retry_prompt}",
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
    final_check = validate_narration(provider, narration, val_ctx)
    report["checks"].append(final_check)
    final_violations = final_check.get("violations", [])
    attempts.append((narration, len(final_violations), final_check))

    if not final_check["pass"]:
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
