from __future__ import annotations

import re

from straightjacket.engine.models import GameState

from .models import NpcSnapshot


_LEAKED_MECHANICS = [
    (re.compile(r"\b(?:MISS|WEAK_HIT|STRONG_HIT)\b"), "result type leaked"),
    (re.compile(r"\b(?:health|spirit|supply|momentum)\s*[=:]\s*\d", re.IGNORECASE), "raw stat value leaked"),
    (re.compile(r"<(?:game_data|memory_updates|scene_context|npc_rename|new_npcs)>"), "XML metadata tag leaked"),
    (re.compile(r"```"), "code fence leaked"),
    (re.compile(r'\{[^}]*"(?:npc_id|emotional_weight|scene_context)"'), "JSON metadata leaked"),
    (re.compile(r"\[(?:CLOCK|THREAT|SCENE CONTEXT|MEMORY)[^\]]*\]"), "bracket annotation leaked"),
    (re.compile(r"\b(?:d6|d10|2d6|2d10|action_score|challenge_dice)\b", re.IGNORECASE), "dice mechanic term leaked"),
    (re.compile(r"\*{2,}[^*]+\*{2,}"), "markdown bold leaked"),
    (re.compile(r"^#{1,3}\s", re.MULTILINE), "markdown heading leaked"),
]


def check_narration_quality(narration: str) -> list[str]:
    findings: list[str] = []
    for pattern, description in _LEAKED_MECHANICS:
        match = pattern.search(narration)
        if match:
            excerpt = match.group(0)[:40]
            findings.append(f"{description}: '{excerpt}'")
    return findings


def check_npc_spatial_consistency(
    game: GameState,
    prev_npcs: list[NpcSnapshot] | None,
    narration: str,
) -> list[str]:
    if not prev_npcs:
        return []

    findings: list[str] = []
    narration_lower = narration.lower()
    prev_by_id = {n.id: n for n in prev_npcs}

    for npc in game.npcs:
        if npc.status not in ("active", "background"):
            continue
        prev = prev_by_id.get(npc.id)
        if not prev:
            continue
        if not prev.last_location:
            continue

        old_loc = prev.last_location
        new_loc = npc.last_location

        if not old_loc or not new_loc:
            continue
        if old_loc.lower().strip() == new_loc.lower().strip():
            continue

        name_lower = npc.name.lower()
        mentioned = name_lower in narration_lower
        if not mentioned:
            for part in npc.name.split():
                if len(part) >= 4 and part.lower() in narration_lower:
                    mentioned = True
                    break

        if not mentioned:
            findings.append(
                f"NPC '{npc.name}' teleported from '{old_loc}' to '{new_loc}' without appearing in narration"
            )

    return findings


def check_chapter_continuity(
    game: GameState,
    pre_chapter_npcs: list[NpcSnapshot] | None,
) -> list[str]:
    if not pre_chapter_npcs:
        return []

    findings: list[str] = []
    current_names = {n.name.lower().strip() for n in game.npcs}
    current_by_name = {n.name.lower().strip(): n for n in game.npcs}

    for prev in pre_chapter_npcs:
        if prev.status in ("deceased", "lore"):
            continue
        name_lower = prev.name.lower().strip()

        if name_lower not in current_names:
            found = False
            for n in game.npcs:
                if any(a.lower().strip() == name_lower for a in n.aliases):
                    found = True
                    break
            if not found:
                findings.append(f"NPC '{prev.name}' missing after chapter transition")
            continue

        current = current_by_name[name_lower]

        if prev.memory_count > 3 and len(current.memory) == 0:
            findings.append(f"NPC '{prev.name}' lost all {prev.memory_count} memories across chapter")

    return findings
