from __future__ import annotations

from typing import Any

from .models import SessionLog


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

    drift_list = gc.atmospheric_drift
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
        phase = act["phase"]
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
        "blueprint_drift": check_blueprint_drift(slog),
    }
