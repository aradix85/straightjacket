import json
import re
from typing import Any

from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import EngineConfig, GameState
from ..prompt_loader import get_prompt
from .json_utils import extract_json
from .provider_base import AIProvider, create_with_retry


def _word_boundary_pattern(name: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)


def _narrative_text(narrative: dict[str, Any]) -> str:
    parts: list[str] = [
        str(narrative.get("title", "")),
        str(narrative.get("summary", "")),
        str(narrative.get("character_growth", "")),
        str(narrative.get("thematic_question", "")),
    ]
    parts.extend(str(t) for t in narrative.get("unresolved_threads", []))
    for ev in narrative.get("npc_evolutions", []):
        if isinstance(ev, dict):
            parts.append(str(ev.get("name", "")))
            parts.append(str(ev.get("evolution", "")))
            parts.append(str(ev.get("description", "")))
    return "\n".join(p for p in parts if p)


def _keyword_near_match(text: str, name_pat: re.Pattern[str], keywords: list[str]) -> bool:
    for m in name_pat.finditer(text):
        start = max(0, m.start() - eng().truncations.log_short)
        end = min(len(text), m.end() + eng().truncations.log_short)
        window = text[start:end].lower()
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", window):
                return True
    return False


def _rule_check(narrative: dict[str, Any], game: GameState) -> list[str]:
    text = _narrative_text(narrative)
    if not text.strip():
        return []

    cv = eng().chapter_validator
    templates = eng().rule_validator.violation_templates
    violations: list[str] = []

    for npc in game.npcs:
        if npc.status == "deceased":
            continue
        if not npc.name or len(npc.name) < eng().fuzzy_match.npc_name_min_length:
            continue
        pat = _word_boundary_pattern(npc.name)
        if _keyword_near_match(text, pat, cv.death_keywords):
            violations.append(templates["chapter_npc_contradiction"].format(name=npc.name, status=npc.status))

    for track in game.progress_tracks:
        if track.status == "completed":
            continue
        if not track.name or len(track.name) < eng().fuzzy_match.npc_name_min_length:
            continue
        pat = _word_boundary_pattern(track.name)
        if _keyword_near_match(text, pat, cv.completion_keywords):
            violations.append(templates["chapter_track_contradiction"].format(name=track.name, status=track.status))

    for threat in game.threats:
        if threat.status in ("resolved", "overcome"):
            continue
        if not threat.name or len(threat.name) < eng().fuzzy_match.npc_name_min_length:
            continue
        pat = _word_boundary_pattern(threat.name)
        if _keyword_near_match(text, pat, cv.resolution_keywords):
            violations.append(templates["chapter_threat_contradiction"].format(name=threat.name, status=threat.status))

    return violations


def _build_state_block(game: GameState) -> str:
    lines: list[str] = []
    if game.npcs:
        lines.append("NPCs:")
        for n in game.npcs:
            lines.append(f"  - {n.name}: {n.status}")
    if game.progress_tracks:
        lines.append("Tracks:")
        for t in game.progress_tracks:
            lines.append(f"  - {t.name}: {t.status}")
    if game.threats:
        lines.append("Threats:")
        for th in game.threats:
            lines.append(f"  - {th.name}: {th.status}")
    if lines:
        return "\n".join(lines)
    return eng().ai_text.narrator_defaults["chapter_validator_no_state"]


def _llm_check(provider: AIProvider, narrative: dict[str, Any], game: GameState) -> list[str]:
    state_block = _build_state_block(game)
    empty_block = eng().ai_text.narrator_defaults["chapter_validator_empty_block"]

    evolutions_lines = [
        f"  - {ev.get('name', '')}: {ev.get('evolution', '')}"
        for ev in narrative.get("npc_evolutions", [])
        if isinstance(ev, dict)
    ]
    npc_evolutions_block = "\n".join(evolutions_lines) if evolutions_lines else empty_block

    threads_lines = [f"  - {t}" for t in narrative.get("unresolved_threads", [])]
    unresolved_threads_block = "\n".join(threads_lines) if threads_lines else empty_block

    user_prompt = get_prompt(
        "chapter_validator_user",
        role="chapter_validator",
        state_block=state_block,
        title=str(narrative.get("title", "")),
        summary=str(narrative.get("summary", "")),
        character_growth=str(narrative.get("character_growth", "")),
        npc_evolutions_block=npc_evolutions_block,
        unresolved_threads_block=unresolved_threads_block,
        thematic_question=str(narrative.get("thematic_question", "")),
    )

    try:
        response = create_with_retry(
            provider,
            model=model_for_role("chapter_validator"),
            system=get_prompt("chapter_validator_system", role="chapter_validator"),
            messages=[{"role": "user", "content": user_prompt}],
            log_role="chapter_validator",
            **sampling_params("chapter_validator"),
        )
        content = response.content.strip()
        if not content:
            log("[ChapterValidator] LLM returned empty content")
            return []

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = extract_json(content)
        if not result:
            log("[ChapterValidator] LLM response unparseable")
            return []
        if result["pass"]:
            return []
        return [f"[llm] {v}" for v in result.get("violations", [])]
    except Exception as e:
        log(f"[ChapterValidator] LLM check failed ({type(e).__name__}: {e}), using rule results only", level="warning")
        return []


def validate_chapter_summary(
    provider: AIProvider, narrative: dict[str, Any], game: GameState
) -> tuple[bool, list[str], str]:
    rule_violations = _rule_check(narrative, game)
    llm_violations = _llm_check(provider, narrative, game)
    all_violations = rule_violations + llm_violations
    if not all_violations:
        return True, [], ""

    correction_intro = get_prompt("chapter_validator_correction_intro", role="chapter_validator")
    correction = correction_intro + "\n".join(f"- {v}" for v in all_violations)
    return False, all_violations, correction


def validate_and_retry(
    provider: AIProvider,
    narrative: dict[str, Any],
    game: GameState,
    config: EngineConfig | None,
    call_summary: Any,
    epilogue_text: str = "",
) -> dict[str, Any]:
    cv = eng().chapter_validator
    current = narrative

    for attempt in range(cv.max_retries):
        passed, violations, correction = validate_chapter_summary(provider, current, game)
        if passed:
            if attempt > 0:
                log(f"[ChapterValidator] Passed on retry {attempt}")
            return current
        log(f"[ChapterValidator] Attempt {attempt}: {len(violations)} violations: {violations}")

        retry_epilogue = (epilogue_text + "\n\n" + correction).strip()
        current = call_summary(provider, game, config, epilogue_text=retry_epilogue)

    passed, violations, _ = validate_chapter_summary(provider, current, game)
    if passed:
        return current
    log(
        f"[ChapterValidator] Exhausted {cv.max_retries} retries with {len(violations)} violations remaining; "
        f"keeping last narrative",
        level="warning",
    )
    return current
