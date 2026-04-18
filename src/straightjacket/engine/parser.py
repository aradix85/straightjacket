#!/usr/bin/env python3
"""Straightjacket response parser: narration processing, memory updates, game data.

parse_narrator_response is a linear pipeline of regex cleanup steps. Each step
targets a specific model artifact (leaked JSON, XML tags, markdown, etc.).
New steps should have a matching test in test_parser.py. The _hits log tracks
which steps fire per response — check this before adding steps.
"""

import re

from .logging_util import log
from .models import GameState
from .npc import (
    NAME_TITLES,
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

    from .engine_loader import eng as _eng

    if last_sentence > _eng().parser.max_label_length and last_sentence < len(prose):
        trimmed = prose[:last_sentence].rstrip()
        log(f"[Narrator] Trimmed truncated prose: {len(prose)} → {len(trimmed)} chars")
        prose = trimmed

    return prose + metadata


# RESPONSE PARSER


def parse_narrator_response(game: GameState, raw: str) -> str:
    """Parse narrator response: strip leaked metadata from prose.
    Metadata extraction (memory_updates, scene_context, NPCs, etc.) is handled
    separately by call_narrator_metadata() — this function only cleans prose
    to keep it player-facing."""
    narration = raw
    _hits = []  # Track which cleanup steps actually changed content

    # --- 0) Strip accidental role-label prefix (e.g. "Narrator:" in English) ---
    _before = narration
    narration = re.sub(r"^\s*Narrator:\s*", "", narration, flags=re.IGNORECASE)
    if narration != _before:
        _hits.append("0:role_prefix")

    # --- 1) Strip all XML metadata tags ---
    _before = narration
    narration = re.sub(
        r"<(?:npc_rename|new_npcs|npc_details|memory_updates|scene_context|"
        r"location_update|time_update|game_data)>[\s\S]*?</(?:npc_rename|new_npcs|"
        r"npc_details|memory_updates|scene_context|location_update|time_update|"
        r"game_data)>",
        "",
        narration,
    ).strip()
    # Strip prompt-echo tags (narrator sometimes echoes input XML)
    narration = re.sub(
        r"</?(?:task|scene|world|character|situation|conflict|possible_endings|"
        r"session_log|npc|returning_npc|campaign_history|chapter|story_arc|"
        r"story_ending|momentum_burn|revelation_ready)[^>]*>",
        "",
        narration,
    ).strip()
    if narration != _before:
        _hits.append("2:xml_tags")

    # --- 3) Strip code fences ---
    _before = narration
    narration = re.sub(r"```(?:\w+)?\s*[\s\S]*?```", "", narration).strip()
    narration = re.sub(r"^\s*```(?:\w+)?\s*$", "", narration, flags=re.MULTILINE).strip()
    if narration != _before:
        _hits.append("3:code_fences")

    # --- 4) Strip JSON arrays/objects that leaked into prose ---
    _before = narration
    narration = re.sub(r'\[[\s]*\{[^[\]]*"(?:npc_id|event|emotional_weight)"[\s\S]*$', "", narration).strip()
    narration = re.sub(r'\{[^{}]*"(?:scene_context|location|npc_id)"[^{}]*\}', "", narration).strip()
    if narration != _before:
        _hits.append("4:leaked_json")

    # --- 5) Strip bracket-format metadata labels ---
    _before = narration
    narration = re.sub(
        r"^\[(?:memory[_\s-]*updates?|scene[_\s-]*context|new[_\s-]*npcs?|npc[_\s-]*renames?|"
        r"npc[_\s-]*details?|location[_\s-]*update?|time[_\s-]*update?|game[_\s-]*data)\].*$",
        "",
        narration,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()
    if narration != _before:
        _hits.append("5:bracket_labels")

    # --- 6) Strip markdown metadata labels (Scene Context:, etc.) ---
    meta_match = re.search(
        r"^[*_#\s]*(scene[\s_-]*context|memory[\s_-]*updates?|location)\s*[*_#]*\s*[:=]\s*",
        narration,
        re.IGNORECASE | re.MULTILINE,
    )
    if meta_match:
        narration = narration[: meta_match.start()].rstrip()
        _hits.append("6:md_metadata")

    # --- 7) Strip trailing JSON lines ---
    _before = narration
    lines = narration.rstrip().split("\n")
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
    narration = "\n".join(lines).rstrip()
    if narration != _before:
        _hits.append("7:trailing_json")

    # --- 7.5) Strip bold-bracket game mechanic annotations ---
    _before = narration
    narration = re.sub(r"\*{1,3}\[[^\]]+\]\*{1,3}", "", narration).strip()
    narration = re.sub(r"^\s*\[[A-Z][A-Z0-9 _\-]*:?[^\]]*\]\s*$", "", narration, flags=re.MULTILINE).strip()
    if narration != _before:
        _hits.append("7.5:mechanic_annotations")

    # --- 8) Strip markdown artifacts ---
    _before = narration
    narration = re.sub(r"^\s*[-*_]{3,}\s*$", "", narration, flags=re.MULTILINE).strip()
    narration = re.sub(r"\s*\*{1,3}\s*$", "", narration, flags=re.MULTILINE).rstrip()
    narration = re.sub(r"\*{3}(.+?)\*{3}", r"\1", narration)
    narration = re.sub(r"\*{2}(.+?)\*{2}", r"\1", narration)
    narration = re.sub(r"\*(.+?)\*", r"\1", narration)
    narration = re.sub(r"(?<!\*)\*(?!\*)", "", narration)
    if narration != _before:
        _hits.append("8:markdown")

    if _hits:
        log(f"[Parser] Cleanup steps triggered: {', '.join(_hits)}")

    # --- 9) Normalize NPC dispositions ---
    normalize_npc_dispositions(game.npcs)

    # --- 10) Mark NPCs as introduced if their name appears in visible text ---
    narration_lower = narration.lower()
    for npc in game.npcs:
        if not npc.introduced and npc.name:
            name = npc.name.strip()
            if not name:
                continue
            if name.lower() in narration_lower:
                npc.introduced = True
                continue
            # Check individual name parts (e.g. "Totewald" from
            # "Director Clemens Totewald") — min 4 chars to avoid
            # matching generic short words; skip known titles
            from .engine_loader import eng as _eng

            min_part = _eng().parser.min_line_length
            for part in name.split():
                part_clean = part.strip(".,;:!?\"'()-").lower()
                if len(part_clean) >= min_part and part_clean not in NAME_TITLES and part_clean in narration_lower:
                    npc.introduced = True
                    break

    # Summary log
    active = [n for n in game.npcs if n.status == "active"]
    background = [n for n in game.npcs if n.status == "background"]
    introduced = [n for n in active if n.introduced]
    log(
        f"[Parser] Done. NPCs total={len(game.npcs)} active={len(active)} background={len(background)} "
        f"introduced={len(introduced)}: {[n.name for n in introduced]}"
    )

    # Safety: if parser stripped everything, return a minimal fallback
    if not narration.strip():
        log("[Parser] WARNING: Narration empty after parsing — returning raw text excerpt", level="warning")
        for para in raw.split("\n\n"):
            clean_para = para.strip()
            if clean_para and not clean_para.startswith(("<", "{", "[", "```")):
                narration = clean_para
                break
        if not narration.strip():
            narration = "(The narrator pauses, gathering thoughts...)"

    return narration
