from __future__ import annotations

from typing import Any

from .models import SessionLog


def compute_validator_balance(slog: SessionLog) -> dict[str, Any]:
    rule_count = 0
    llm_count = 0
    unknown_count = 0
    for turn in slog.turns:
        if not turn.validator:
            continue
        for attempt in turn.validator.attempt_violation_text:
            for v in attempt:
                if v.startswith("[rule]"):
                    rule_count += 1
                elif v.startswith("[llm]"):
                    llm_count += 1
                else:
                    unknown_count += 1

    total = rule_count + llm_count + unknown_count
    suspected_drift = ""
    if total >= 20:
        rule_share = rule_count / total
        llm_share = llm_count / total
        if rule_share < 0.1:
            suspected_drift = (
                f"rule-validator share {rule_share:.0%} of {total} violations — "
                f"may have drifted (rule patterns stopped matching actual narration)"
            )
        elif llm_share < 0.1:
            suspected_drift = (
                f"llm-validator share {llm_share:.0%} of {total} violations — "
                f"may have drifted (llm prompt stopped catching its category)"
            )

    return {
        "rule_violations": rule_count,
        "llm_violations": llm_count,
        "unknown_violations": unknown_count,
        "total_violations_across_attempts": total,
        "rule_share": round(rule_count / total, 3) if total else None,
        "llm_share": round(llm_count / total, 3) if total else None,
        "suspected_drift": suspected_drift,
    }


def check_blueprint_drift(slog: SessionLog) -> dict[str, Any]:
    bp = slog.story_blueprint
    if not bp:
        return {"checked": False, "reason": "no blueprint in session log"}

    setting_id = slog.config.get("game", {}).get("setting_id", "")
    if not setting_id:
        return {"checked": False, "reason": "no setting_id in session config"}

    try:
        from straightjacket.engine.datasworn.settings import load_package

        pkg = load_package(setting_id)
    except Exception as e:
        return {"checked": False, "reason": f"could not load setting: {type(e).__name__}: {e}"}

    if pkg is None:
        return {"checked": False, "reason": f"setting '{setting_id}' not found"}

    gc = pkg.genre_constraints
    if not gc:
        return {"checked": False, "reason": "setting has no genre_constraints"}

    from straightjacket.engine.config_loader import narrator_model_family

    drift_list = gc.atmospheric_drift_for(narrator_model_family())
    if not drift_list:
        return {"checked": False, "reason": "setting has no atmospheric_drift list"}

    drift_words = {w.lower() for w in drift_list}
    forbidden = {w.lower() for w in (gc.forbidden_terms or [])}

    fields_to_scan: list[tuple[str, str]] = [
        ("central_conflict", str(bp.get("central_conflict", ""))),
        ("thematic_thread", str(bp.get("thematic_thread", ""))),
        ("antagonist_force", str(bp.get("antagonist_force", ""))),
    ]
    for act in bp.get("acts", []):
        phase = act.get("phase", "?")
        fields_to_scan.append((f"act[{phase}].goal", str(act.get("goal", ""))))
        fields_to_scan.append((f"act[{phase}].mood", str(act.get("mood", ""))))
        fields_to_scan.append((f"act[{phase}].transition_trigger", str(act.get("transition_trigger", ""))))

    drift_hits: list[dict[str, str]] = []
    forbidden_hits: list[dict[str, str]] = []
    for field_name, text in fields_to_scan:
        if not text:
            continue
        words_in_text = set(text.lower().split())
        for w in words_in_text & drift_words:
            drift_hits.append({"field": field_name, "word": w})
        for w in words_in_text & forbidden:
            forbidden_hits.append({"field": field_name, "word": w})

    threshold = gc.atmospheric_drift_threshold or 0
    return {
        "checked": True,
        "setting_id": setting_id,
        "drift_threshold": threshold,
        "drift_hits_total": len(drift_hits),
        "drift_hits_exceeds_threshold": len(drift_hits) > threshold,
        "drift_hits": drift_hits[:20],
        "forbidden_hits_total": len(forbidden_hits),
        "forbidden_hits": forbidden_hits[:20],
    }


def compute_drift_summary(slog: SessionLog) -> dict[str, Any]:
    return {
        "validator_balance": compute_validator_balance(slog),
        "blueprint_drift": check_blueprint_drift(slog),
    }
