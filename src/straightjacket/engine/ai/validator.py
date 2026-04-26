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
    has_pacing = any("resolution pacing" in v.lower() or "monologue" in v.lower() for v in violations)
    if not has_pacing:
        return prompt

    retry_strip = eng().validator.retry_strip

    stripped = prompt

    stripped = re.sub(
        r"secrets\([^)]*\):\[.*?\]",
        retry_strip["empty_secrets"],
        stripped,
        flags=re.DOTALL,
    )

    stripped = re.sub(r"^(?:recent|insight):.*$", "", stripped, flags=re.MULTILINE)

    stripped = re.sub(r"^agenda:.*$", retry_strip["agenda_placeholder"], stripped, flags=re.MULTILINE)

    if stripped != prompt:
        log("[Validator] Stripped NPC secrets/memories/agenda from retry prompt")
    return stripped


def _build_validator_system(ctx: ValidationContext) -> str:
    player_name = ctx.game.player_name
    pc_hint = get_prompt("validator_pc_hint", player_name=player_name) if player_name else ""

    active_npc_names = [n.name for n in ctx.game.npcs if n.name and n.status == "active" and n.introduced]
    npc_names_hint = (
        get_prompt("validator_npc_names_hint", npc_names=", ".join(sorted(active_npc_names)))
        if active_npc_names
        else ""
    )

    cons_sentence_text = ""
    if ctx.consequence_sentences and ctx.result_type in ("MISS", "WEAK_HIT"):
        cons_sentence_text = get_prompt(
            "validator_consequence_compliance",
            consequence_list="\n".join(f"- {s}" for s in ctx.consequence_sentences),
        )

    return get_prompt(
        "validator_system",
        role="validator",
        pc_hint=pc_hint,
        npc_names_hint=npc_names_hint,
        consequence_compliance_block=cons_sentence_text,
    )


def validate_narration(
    provider: AIProvider,
    narration: str,
    ctx: ValidationContext,
) -> dict:
    rule_result = run_rule_checks(narration, ctx)
    rule_violations = rule_result.get("violations", [])

    if rule_violations:
        _cap = eng().rule_validator.correction_violations_cap
        all_violations = [f"[rule] {v}" for v in rule_violations]
        correction = "; ".join(v.split(": ", 1)[1] if ": " in v else v for v in all_violations[:_cap])
        log(f"[Validator] FAILED (rule fast path, {len(rule_violations)} violations): {all_violations}")
        return {"pass": False, "violations": all_violations, "correction": f"Fix: {correction}"}

    llm_violations = []
    cons_text = ", ".join(ctx.consequences) if ctx.consequences else "none"
    system = _build_validator_system(ctx)

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
            log("[Validator] Empty response from json_schema, retrying without schema")
            _vp2 = dict(sampling_params("validator"))
            _vp2["max_retries"] = 1
            response = create_with_retry(
                provider,
                model=model_for_role("validator"),
                system=system + get_prompt("validator_json_suffix", role="validator"),
                messages=[{"role": "user", "content": prompt}],
                log_role="validator",
                **_vp2,
            )
            content = response.content.strip()
        if content:
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = extract_json(content)
            if result and not result["pass"]:
                llm_violations = result.get("violations", [])
    except Exception as e:
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
    if max_retries is None:
        max_retries = sampling_params("narrator")["max_retries"]

    gc = None
    pkg = active_package(game)
    if pkg:
        gc = pkg.genre_constraints

    val_ctx = ValidationContext.build(
        game,
        result_type=result_type,
        player_words=player_words,
        consequences=consequences,
        consequence_sentences=consequence_sentences,
        genre_constraints=gc,
    )

    report: dict = {"passed": True, "retries": 0, "violations": [], "checks": []}

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

        rules = eng().validator.rewrite_instructions
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

        failed_narration_msg = {"role": "assistant", "content": narration}
        correction_msg = {
            "role": "user",
            "content": f"<REWRITE>\n{_vblocks['rewrite_user_prefix']}\n{instructions_text}\n"
            f"{_vblocks['rewrite_user_suffix']}\n</REWRITE>\n\n{retry_prompt}",
        }

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

    final_check = validate_narration(provider, narration, val_ctx)
    report["checks"].append(final_check)
    final_violations = final_check.get("violations", [])
    attempts.append((narration, len(final_violations), final_check))

    if not final_check["pass"]:
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
