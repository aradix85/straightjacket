#!/usr/bin/env python3
"""Straightjacket response parser: narration processing, memory updates, game data.

parse_narrator_response is a linear pipeline of regex cleanup steps. Each step
targets a specific model artifact (leaked JSON, XML tags, markdown, etc.).
New steps should have a matching test in test_parser.py. The _hits log tracks
which steps fire per response — check this before adding steps.
"""

import json
import re

from .engine_loader import eng
from .logging_util import log
from .mechanics import TIME_PHASES, update_location
from .models import ClockData, GameState, MemoryEntry, NpcData
from .npc import (
    NAME_TITLES,
    apply_name_sanitization,
    consolidate_memory,
    find_npc,
    fuzzy_match_existing_npc,
    next_npc_id,
    normalize_npc_dispositions,
    reactivate_npc,
    resolve_about_npc,
    score_importance,
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
        ".»",
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
    if stripped.endswith(('."', '!"', '?"', ".»", "!»", "?»")):
        last_sentence = max(last_sentence, len(stripped))

    if last_sentence > 30 and last_sentence < len(prose):
        trimmed = prose[:last_sentence].rstrip()
        log(f"[Narrator] Trimmed truncated prose: {len(prose)} → {len(trimmed)} chars")
        prose = trimmed

    return prose + metadata


# RESPONSE PARSER


def _process_game_data(game: GameState, data: dict, force_npcs: bool = True):
    """Process structured game_data from narrator response (opening scene).
    Shared logic for both tagged and untagged game_data extraction.
    If force_npcs=False, only sets game.npcs when currently empty (fallback parsing)."""
    if data.get("npcs"):
        # Determine starting ID counter from existing NPCs
        max_num = 0
        for n in game.npcs:
            id_match = re.match(r"npc_(\d+)", str(n.id))
            if id_match:
                max_num = max(max_num, int(id_match.group(1)))
        npcs_out = []
        for nd in data["npcs"]:
            if not nd.get("id") or not re.match(r"^npc_\d+$", str(nd.get("id", ""))):
                max_num += 1
                nd["id"] = f"npc_{max_num}"
            else:
                id_match = re.match(r"npc_(\d+)", nd["id"])
                if id_match:
                    max_num = max(max_num, int(id_match.group(1)))
            nd.setdefault("introduced", False)
            nd.setdefault("last_location", game.world.current_location or "")
            raw_mem = nd.get("memory", [])
            nd["memory"] = [
                m if isinstance(m, dict) else {"scene": 0, "event": str(m), "emotional_weight": "neutral"}
                for m in raw_mem
            ]
            for m in nd["memory"]:
                if isinstance(m, dict) and "importance" not in m:
                    ew = m.get("emotional_weight", "neutral")
                    ev = m.get("event", "")
                    imp, dbg = score_importance(ew, ev, debug=True)
                    m["importance"] = imp
                    m["type"] = m.get("type", "observation")
                    m["_score_debug"] = f"opening game_data | {dbg}"
            npcs_out.append(NpcData.from_dict(nd))
        player_lower = game.player_name.lower().strip()
        npcs_out = [n for n in npcs_out if n.name.lower().strip() != player_lower]
        for npc in npcs_out:
            apply_name_sanitization(npc)
        if force_npcs or not game.npcs:
            game.npcs = npcs_out
            log(f"[NPC] Opening game_data: set {len(game.npcs)} NPCs: {[n.name for n in game.npcs]}")
    if data.get("clocks"):
        existing_names = {c.name for c in game.world.clocks}
        new_clocks = [ClockData.from_dict(c) for c in data["clocks"] if c.get("name") not in existing_names]
        if new_clocks:
            game.world.clocks.extend(new_clocks)
            log(
                f"[Clock] Added {len(new_clocks)} new clocks (skipped {len(data['clocks']) - len(new_clocks)} duplicates)"
            )
    if data.get("location"):
        update_location(game, data["location"])
    if data.get("scene_context"):
        game.world.current_scene_context = data["scene_context"]
    if data.get("time_of_day") and data["time_of_day"] in TIME_PHASES:
        game.world.time_of_day = data["time_of_day"]


def parse_narrator_response(game: GameState, raw: str) -> str:
    """Parse narrator response: extract game_data (opening scenes) and clean prose.
    Metadata extraction (memory_updates, scene_context, NPCs, etc.) is handled
    separately by call_narrator_metadata() — this function only strips leaked
    metadata from the prose to keep it player-facing clean."""
    narration = raw
    _hits = []  # Track which cleanup steps actually changed content

    # --- 0) Strip accidental role-label prefix (e.g. "Narrator:" in English) ---
    _before = narration
    narration = re.sub(r"^\s*Narrator:\s*", "", narration, flags=re.IGNORECASE)
    if narration != _before:
        _hits.append("0:role_prefix")

    # --- 1) Tagged game_data (opening scene / new chapter) ---
    gd = re.search(r"<game_data>([\s\S]*?)</game_data>", narration)
    if gd:
        log(f"[Parser] Step 1: Found <game_data> tag ({len(gd.group(1))} chars)")
        try:
            data = json.loads(gd.group(1))
            if game.narrative.scene_count <= 1:
                _process_game_data(game, data)
            else:
                log(
                    f"[Parser] Step 1: Mid-game <game_data> detected (scene {game.narrative.scene_count}), "
                    f"using force_npcs=False to prevent NPC list replacement"
                )
                _process_game_data(game, data, force_npcs=False)
        except (json.JSONDecodeError, KeyError) as e:
            log(f"[Parser] Step 1: Failed to parse game_data JSON: {e}", level="warning")
        narration = re.sub(r"<game_data>[\s\S]*?</game_data>", "", narration).strip()

    # --- 1.5) Untagged game_data (Narrator omitted XML tags) ---
    if not gd:
        npcs_obj_match = re.search(r'\{[\s\S]*?"npcs"\s*:\s*\[', narration)
        if npcs_obj_match:
            log(f"[Parser] Step 1.5: Found untagged game_data JSON at pos {npcs_obj_match.start()}")
            start = npcs_obj_match.start()
            try:
                decoder = json.JSONDecoder()
                data, end_idx = decoder.raw_decode(narration, start)
                if isinstance(data, dict) and (data.get("npcs") or data.get("clocks")):
                    _process_game_data(game, data)
                    narration = (narration[:start].rstrip() + "\n" + narration[start + end_idx :].lstrip()).strip()
            except (json.JSONDecodeError, ValueError) as e:
                log(f"[Parser] Step 1.5: Failed to parse untagged game_data: {e}", level="warning")

    # --- 2) Strip all XML metadata tags (narrator may still emit them from history) ---
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
        r"^[*_#\s]*(scene[\s_-]*context|memory[\s_-]*updates?|szenenkontext|location)\s*[*_#]*\s*[:=]\s*",
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
        if re.match(
            r"^(scene[\s_-]*context|memory[\s_-]*updates?|location|szenenkontext)\s*[:=]", clean_last, re.IGNORECASE
        ):
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
            # "Geschäftsführer Clemens Totewald") — min 4 chars to avoid
            # matching generic words like "der", "von"; skip known titles
            for part in name.split():
                part_clean = part.strip(".,;:!?\"'()-").lower()
                if len(part_clean) >= 4 and part_clean not in NAME_TITLES and part_clean in narration_lower:
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


def apply_memory_updates(
    game: GameState,
    updates: list,
    scene_present_ids: set | None = None,
    pre_turn_npc_ids: set | None = None,
    pre_turn_lore_ids: set | None = None,
):
    """Apply NPC memory updates with importance scoring and consolidation.

    scene_present_ids: NPC IDs activated/mentioned in this scene (from activate_npcs_for_prompt).
    pre_turn_npc_ids: NPC IDs that existed before this turn's new_npcs were created.
    pre_turn_lore_ids: NPC IDs that had status="lore" before _process_new_npcs ran.

    When scene_present_ids and pre_turn_npc_ids are both provided, memory updates
    for known, non-exempt NPCs absent from scene_present_ids are rejected.
    Exemptions: freshly-created NPCs, lore NPCs, deceased NPCs, auto-created stubs."""
    for u in updates:
        if not isinstance(u, dict) or "npc_id" not in u:
            continue
        npc = find_npc(game, u["npc_id"])

        # Fuzzy fallback: try word-overlap matching before creating a stub
        # Additional first-name mismatch guard
        if not npc and u["npc_id"] and u["npc_id"] not in ("world", "player", ""):
            fuzzy_candidate, _ = fuzzy_match_existing_npc(game, u["npc_id"])
            if fuzzy_candidate:
                # Safety: if both names have 2+ words, verify first names aren't
                # completely different (prevents "Marissa Chen" → "Mrs. Chen")
                ref_parts = u["npc_id"].strip().split()
                match_parts = fuzzy_candidate.name.strip().split()
                if len(ref_parts) >= 2 and len(match_parts) >= 2:
                    ref_first = ref_parts[0].lower().strip(".")
                    match_first = match_parts[0].lower().strip(".")
                    if (
                        ref_first not in NAME_TITLES
                        and match_first not in NAME_TITLES
                        and ref_first != match_first
                        and ref_first not in match_first
                        and match_first not in ref_first
                    ):
                        log(
                            f"[NPC] memory_update fuzzy REJECTED: '{u['npc_id']}' ~ "
                            f"'{fuzzy_candidate.name}' (first-name mismatch: "
                            f"'{ref_first}' vs '{match_first}')"
                        )
                        fuzzy_candidate = None
                if fuzzy_candidate:
                    npc = fuzzy_candidate
                    log(f"[NPC] memory_update fuzzy-matched '{u['npc_id']}' → '{npc.name}'")

        # Auto-create NPC stub if not found (safety net when <new_npcs> was omitted)
        if not npc and u["npc_id"] and u["npc_id"] not in ("world", "player", ""):
            npc_name = u["npc_id"]
            # Skip technical ID references (e.g. "npc_4") — this is a Narrator
            # reference error to an existing NPC, not a new character
            if re.match(r"^npc_\d+$", npc_name, re.IGNORECASE):
                log(f"[NPC] Skipping auto-stub for technical ID reference: {npc_name}", level="warning")
                continue
            if npc_name.lower().strip() != game.player_name.lower().strip() and not (
                set(npc_name.lower().split()) & set(game.player_name.lower().split())
            ):
                npc_id, _ = next_npc_id(game)
                npc = NpcData(
                    id=npc_id,
                    name=npc_name,
                    bond=eng().bonds.start,
                    bond_max=eng().bonds.max,
                    last_location=game.world.current_location or "",
                )
                game.npcs.append(npc)
                log(f"[NPC] Auto-created stub NPC from memory_update: {npc_name}")

        if npc:
            # --- Presence guard ---
            # Reject memories for NPCs that weren't present in this scene,
            # unless they are exempt (freshly created, lore, deceased, stubs).
            if (
                scene_present_ids is not None
                and pre_turn_npc_ids is not None
                and npc.id in pre_turn_npc_ids  # known before this turn
                and npc.id not in scene_present_ids  # not in scene
                and npc.status not in ("lore", "deceased")
                and (pre_turn_lore_ids is None or npc.id not in pre_turn_lore_ids)
            ):
                log(
                    f"[NPC] memory_update REJECTED for absent NPC '{npc.name}' (not in scene_present_ids)",
                    level="warning",
                )
                continue

            # Resurrect deceased NPCs if the extractor reports them as active
            # (exact npc_id match = extractor considers them physically present)
            if npc.status == "deceased":
                reactivate_npc(npc, reason="memory_update for deceased NPC — resurrection detected", force=True)
            # Reactivate background NPCs that appear in current scene
            elif npc.status == "background":
                reactivate_npc(npc, reason="memory_update in current scene")
            # Ensure memory system fields exist

            event_text = u.get("event", "")
            emotional = u.get("emotional_weight", "neutral")
            importance, score_debug = score_importance(emotional, event_text, debug=True)

            npc.memory.append(
                MemoryEntry(
                    scene=game.narrative.scene_count,
                    event=event_text,
                    emotional_weight=emotional,
                    importance=importance,
                    type="observation",
                    about_npc=resolve_about_npc(game, u.get("about_npc"), owner_id=npc.id),
                    _score_debug=score_debug,
                )
            )

            npc.importance_accumulator = npc.importance_accumulator + importance
            # Track where this NPC was last seen (spatial consistency)
            if game.world.current_location:
                npc.last_location = game.world.current_location
            if npc.importance_accumulator >= eng().npc.reflection_threshold:
                npc.needs_reflection = True
                log(f"[NPC] {npc.name} needs reflection (accumulator={npc.importance_accumulator})")

            # Consolidate memory (replaces simple FIFO)
            consolidate_memory(npc)
