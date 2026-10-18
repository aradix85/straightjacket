import re

from .ai.provider_base import AIUnavailableError
from .engine_loader import eng
from .logging_util import log
from .models import GameState


def salvage_truncated_narration(raw: str) -> str:
    cfg = eng().parser
    prose = raw.rstrip()
    if prose.endswith(tuple(mark.rstrip() for mark in cfg.sentence_breaks)):
        return prose
    last_sentence = max((prose.rfind(mark) + len(mark) for mark in cfg.sentence_breaks if mark in prose), default=0)
    if last_sentence <= cfg.salvage_min_length:
        return prose
    trimmed = prose[:last_sentence].rstrip()
    log(f"[Narrator] Trimmed truncated prose: {len(prose)} → {len(trimmed)} chars")
    return trimmed


def _any_of(words: list[str]) -> str:
    return "|".join(re.escape(word) for word in words)


def _strip_role_prefix(text: str) -> str:
    return re.sub(rf"^\s*(?:{_any_of(eng().parser.role_prefixes)}):\s*", "", text, flags=re.IGNORECASE)


def _strip_prompt_tags(text: str) -> str:
    return re.sub(rf"</?(?:{_any_of(eng().parser.leaked_prompt_tags)})[^>]*>", "", text).strip()


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"```(?:\w+)?\s*[\s\S]*?```", "", text).strip()
    return re.sub(r"^\s*```(?:\w+)?\s*$", "", text, flags=re.MULTILINE).strip()


def _strip_mechanic_annotations(text: str) -> str:
    text = re.sub(r"\*{1,3}\[[^\]]+\]\*{1,3}", "", text).strip()
    return re.sub(r"^\s*\[[A-Z][A-Z0-9 _\-]*:?[^\]]*\]\s*$", "", text, flags=re.MULTILINE).strip()


def _strip_markdown_formatting(text: str) -> str:
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"\s*\*{1,3}\s*$", "", text, flags=re.MULTILINE).rstrip()
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return re.sub(r"(?<!\*)\*(?!\*)", "", text)


def _mark_introduced_npcs(game: GameState, narration: str) -> None:
    narration_lower = narration.lower()
    _e = eng()
    min_part = _e.parser.min_line_length
    titles = _e.name_titles

    for npc in game.npcs:
        if npc.introduced:
            continue
        if npc.name.lower() in narration_lower:
            npc.introduced = True
            continue

        for part in npc.name.split():
            part_clean = part.strip(".,;:!?\"'()-").lower()
            if len(part_clean) >= min_part and part_clean not in titles and part_clean in narration_lower:
                npc.introduced = True
                break


_CLEANUP_STEPS = (
    _strip_role_prefix,
    _strip_prompt_tags,
    _strip_code_fences,
    _strip_mechanic_annotations,
    _strip_markdown_formatting,
)


def parse_narrator_response(game: GameState, raw: str) -> str:
    narration = raw
    hits: list[str] = []
    for step in _CLEANUP_STEPS:
        before = narration
        narration = step(narration)
        if narration != before:
            hits.append(step.__name__)
    if hits:
        log(f"[Parser] Cleanup steps triggered: {', '.join(hits)}")

    _mark_introduced_npcs(game, narration)

    if not narration.strip():
        log("[Parser] WARNING: nothing of the narration is left after cleanup", level="warning")
        raise AIUnavailableError("narrator: empty narration after cleanup")

    return narration


def clean_sentence(text: str, first: bool) -> str:
    cleaned = _strip_role_prefix(text) if first else text
    for step in (_strip_prompt_tags, _strip_mechanic_annotations, _strip_markdown_formatting):
        cleaned = step(cleaned)
    return cleaned.strip()
