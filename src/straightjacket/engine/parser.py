"""Straightjacket response parser: narration processing, memory updates, game data.

parse_narrator_response is a linear pipeline of regex cleanup steps. Each step
targets a specific model artifact (leaked JSON, XML tags, markdown, etc.).
New steps should have a matching test in test_parser.py. The _hits log tracks
which steps fire per response — check this before adding steps.
"""

import re
from collections.abc import Callable

from .engine_loader import eng
from .logging_util import log
from .models import GameState
from .npc import (
    normalize_npc_dispositions,
)


def salvage_truncated_narration(raw: str) -> str:
    """Clean up a truncated narrator response so it ends at a natural break."""
    last_open = raw.rfind("<game_data>")
    if last_open != -1 and raw.find("</game_data>", last_open) == -1:
        raw = raw[:last_open].rstrip()
        log("[Narrator] Removed incomplete <game_data> from truncated response")

    prose_end = len(raw)
    idx = raw.find("<game_data>")
    if idx != -1 and idx < prose_end:
        prose_end = idx

    prose = raw[:prose_end]
    metadata = raw[prose_end:]

    last_sentence = -1
    for pattern in [
        ". ",
        '." ',
        '."\n',
        '."',
        ".\n\n",
        "! ",
        '!" ',
        '!"',
        "!\n\n",
        "? ",
        '?" ',
        '?"',
        "?\n\n",
        "…",
        '…"',
        "… ",
    ]:
        idx = prose.rfind(pattern)
        if idx != -1:
            end = idx + len(pattern)
            if end > last_sentence:
                last_sentence = end

    stripped = prose.rstrip()
    if stripped and stripped[-1] in ".!?":
        last_sentence = max(last_sentence, len(stripped))
    if stripped.endswith(('."', '!"', '?"')):
        last_sentence = max(last_sentence, len(stripped))

    if last_sentence > eng().parser.max_label_length and last_sentence < len(prose):
        trimmed = prose[:last_sentence].rstrip()
        log(f"[Narrator] Trimmed truncated prose: {len(prose)} → {len(trimmed)} chars")
        prose = trimmed

    return prose + metadata


# RESPONSE PARSER


def _strip_role_prefix(text: str) -> str:
    """Step 0: strip leading 'Narrator:' role prefix."""
    return re.sub(r"^\s*Narrator:\s*", "", text, flags=re.IGNORECASE)


def _strip_metadata_and_prompt_tags(text: str) -> str:
    """Step 2: remove leaked <game_data>, <memory_updates>, etc., plus prompt-echo XML tags."""
    text = re.sub(
        r"<(?:npc_rename|new_npcs|npc_details|memory_updates|scene_context|"
        r"location_update|time_update|game_data)>[\s\S]*?</(?:npc_rename|new_npcs|"
        r"npc_details|memory_updates|scene_context|location_update|time_update|"
        r"game_data)>",
        "",
        text,
    ).strip()
    # Prompt-echo: narrator sometimes echoes input XML verbatim
    return re.sub(
        r"</?(?:task|scene|world|character|situation|conflict|possible_endings|"
        r"session_log|npc|returning_npc|campaign_history|chapter|story_arc|"
        r"story_ending|momentum_burn|revelation_ready)[^>]*>",
        "",
        text,
    ).strip()


def _strip_code_fences(text: str) -> str:
    """Step 3: fenced code blocks and dangling triple-backticks."""
    text = re.sub(r"```(?:\w+)?\s*[\s\S]*?```", "", text).strip()
    return re.sub(r"^\s*```(?:\w+)?\s*$", "", text, flags=re.MULTILINE).strip()


def _strip_leaked_json(text: str) -> str:
    """Step 4: JSON blobs that leaked out of the metadata path."""
    text = re.sub(r'\[[\s]*\{[^[\]]*"(?:npc_id|event|emotional_weight)"[\s\S]*$', "", text).strip()
    return re.sub(r'\{[^{}]*"(?:scene_context|location|npc_id)"[^{}]*\}', "", text).strip()


def _strip_bracket_labels(text: str) -> str:
    """Step 5: bracketed section labels on their own lines."""
    return re.sub(
        r"^\[(?:memory[_\s-]*updates?|scene[_\s-]*context|new[_\s-]*npcs?|npc[_\s-]*renames?|"
        r"npc[_\s-]*details?|location[_\s-]*update?|time[_\s-]*update?|game[_\s-]*data)\].*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()


def _strip_markdown_metadata_header(text: str) -> tuple[str, bool]:
    """Step 6: markdown-style 'Scene Context:' / 'Memory Updates:' headers — cut from there on."""
    meta_match = re.search(
        r"^[*_#\s]*(scene[\s_-]*context|memory[\s_-]*updates?|location)\s*[*_#]*\s*[:=]\s*",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if meta_match:
        return text[: meta_match.start()].rstrip(), True
    return text, False


def _strip_trailing_json_and_labels(text: str) -> str:
    """Step 7: peel off trailing lines that are JSON artifacts or metadata labels."""
    lines = text.rstrip().split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if last.startswith(("{", "[")):
            lines.pop()
            continue
        clean_last = re.sub(r"^[\s*_#]+", "", last)
        if re.match(r"^(scene[\s_-]*context|memory[\s_-]*updates?|location)\s*[:=]", clean_last, re.IGNORECASE):
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


def _strip_mechanic_annotations(text: str) -> str:
    """Step 7.5: *[STRONG HIT]*-style annotations and [CAPS_LABEL] lines."""
    text = re.sub(r"\*{1,3}\[[^\]]+\]\*{1,3}", "", text).strip()
    return re.sub(r"^\s*\[[A-Z][A-Z0-9 _\-]*:?[^\]]*\]\s*$", "", text, flags=re.MULTILINE).strip()


def _strip_markdown_formatting(text: str) -> str:
    """Step 8: horizontal rules, trailing asterisks, bold/italic emphasis marks, stray stars."""
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"\s*\*{1,3}\s*$", "", text, flags=re.MULTILINE).rstrip()
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return re.sub(r"(?<!\*)\*(?!\*)", "", text)


def _mark_introduced_npcs(game: GameState, narration: str) -> None:
    """After cleanup, mark any NPC as introduced if their name (or a significant part)
    appears in the narration.
    """
    narration_lower = narration.lower()
    _e = eng()
    min_part = _e.parser.min_line_length
    titles = _e.name_titles

    for npc in game.npcs:
        if npc.introduced or not npc.name:
            continue
        name = npc.name.strip()
        if not name:
            continue
        if name.lower() in narration_lower:
            npc.introduced = True
            continue
        # Individual-part match (e.g. "Totewald" from "Director Clemens Totewald")
        # Min length avoids matching generic short words; titles excluded.
        for part in name.split():
            part_clean = part.strip(".,;:!?\"'()-").lower()
            if len(part_clean) >= min_part and part_clean not in titles and part_clean in narration_lower:
                npc.introduced = True
                break


def _salvage_empty_narration(raw: str) -> str:
    """Fallback when cleanup stripped everything: pick the first paragraph that
    isn't an obvious metadata block.
    """
    for para in raw.split("\n\n"):
        clean_para = para.strip()
        if clean_para and not clean_para.startswith(("<", "{", "[", "```")):
            return clean_para
    return "(The narrator pauses, gathering thoughts...)"


def parse_narrator_response(game: GameState, raw: str) -> str:
    """Parse narrator response: strip leaked metadata from prose.

    Metadata extraction (memory_updates, scene_context, NPCs, etc.) is handled
    separately by call_narrator_metadata() — this function only cleans prose
    to keep it player-facing.

    Pipeline of labeled cleanup steps. The _hits log tracks which fired.
    """
    narration = raw
    hits: list[str] = []

    # Each step: (label, cleanup_fn). Single-return steps; step 6 needs its own branch
    # because it returns a flag alongside the string.
    steps: list[tuple[str, Callable[[str], str]]] = [
        ("0:role_prefix", _strip_role_prefix),
        ("2:xml_tags", _strip_metadata_and_prompt_tags),
        ("3:code_fences", _strip_code_fences),
        ("4:leaked_json", _strip_leaked_json),
        ("5:bracket_labels", _strip_bracket_labels),
    ]
    for label, fn in steps:
        before = narration
        narration = fn(narration)
        if narration != before:
            hits.append(label)

    # Step 6 has a different signature (returns a bool too)
    narration, md_hit = _strip_markdown_metadata_header(narration)
    if md_hit:
        hits.append("6:md_metadata")

    steps_post_md: list[tuple[str, Callable[[str], str]]] = [
        ("7:trailing_json", _strip_trailing_json_and_labels),
        ("7.5:mechanic_annotations", _strip_mechanic_annotations),
        ("8:markdown", _strip_markdown_formatting),
    ]
    for label, fn in steps_post_md:
        before = narration
        narration = fn(narration)
        if narration != before:
            hits.append(label)

    if hits:
        log(f"[Parser] Cleanup steps triggered: {', '.join(hits)}")

    normalize_npc_dispositions(game.npcs)
    _mark_introduced_npcs(game, narration)

    active = [n for n in game.npcs if n.status == "active"]
    background = [n for n in game.npcs if n.status == "background"]
    introduced = [n for n in active if n.introduced]
    log(
        f"[Parser] Done. NPCs total={len(game.npcs)} active={len(active)} background={len(background)} "
        f"introduced={len(introduced)}: {[n.name for n in introduced]}"
    )

    if not narration.strip():
        log("[Parser] WARNING: Narration empty after parsing — returning raw text excerpt", level="warning")
        narration = _salvage_empty_narration(raw)

    return narration
