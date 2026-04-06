#!/usr/bin/env python3
"""Straightjacket persistence: save/load games, chapter archives."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import VERSION
from .engine_loader import eng
from .logging_util import get_save_dir, log
from .models import GameState
from .npc import (
    apply_name_sanitization,
    normalize_npc_dispositions,
)

# SAVE / LOAD

def save_game(game: GameState, username: str, chat_messages: list | None = None,
              name: str = "autosave") -> Path:
    """Save game state and chat history."""
    save_dir = get_save_dir(username)
    save_dir.mkdir(parents=True, exist_ok=True)
    # Version history: carry forward from existing save
    version_history = []
    path = save_dir / f"{name}.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            version_history = existing.get("version_history", [])
            if not version_history and existing.get("engine_version"):
                version_history = [existing["engine_version"]]
        except Exception:
            pass
    if not version_history or version_history[-1] != VERSION:
        version_history.append(VERSION)

    data: dict[str, Any] = {"saved_at": datetime.now().isoformat()}
    data["engine_version"] = VERSION
    data["version_history"] = version_history
    data["game_state"] = game.to_dict()

    # Chat history (strip audio binary data and transient recaps)
    raw_messages = chat_messages or []
    data["chat_messages"] = [
        {k: v for k, v in msg.items() if k not in ("audio_bytes", "audio_format")}
        for msg in raw_messages
        if not msg.get("recap")
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[Save] Game saved: {username}/{name} (Scene {game.narrative.scene_count}, {len(data['chat_messages'])} chat msgs)")
    return path

def load_game(username: str, name: str = "autosave") -> tuple[GameState | None, list]:
    """Load game state and chat history. Returns (game, chat_messages)."""
    save_dir = get_save_dir(username)
    path = save_dir / f"{name}.json"
    if not path.exists():
        log(f"[Load] Save not found: {username}/{name}", level="warning")
        return None, []
    data = json.loads(path.read_text(encoding="utf-8"))

    game_data = data["game_state"]
    game = GameState.from_dict(game_data)

    # NPC data integrity
    normalize_npc_dispositions(game.npcs)
    for npc in game.npcs:
        name_lower = npc.name.lower()
        npc.aliases = [a for a in npc.aliases if a.lower() != name_lower]
        npc.needs_reflection = npc.importance_accumulator >= eng().npc.reflection_threshold
        if (npc.status in ("active", "background")
                and not npc.memory
                and npc.introduced):
            log(f"[Load] WARNING: NPC '{npc.name}' ({npc.id}) "
                f"has no memories", level="warning")
        apply_name_sanitization(npc)

    chat_messages = data.get("chat_messages", [])
    log(f"[Load] Game loaded: {username}/{name} ({game.player_name}, Scene {game.narrative.scene_count}, {len(chat_messages)} chat msgs)")
    return game, chat_messages

def list_saves(username: str) -> list[str]:
    save_dir = get_save_dir(username)
    if not save_dir.exists():
        return []
    return sorted([p.stem for p in save_dir.glob("*.json")])

def get_save_info(username: str, name: str) -> dict | None:
    """Read save metadata without loading full game state."""
    path = get_save_dir(username) / f"{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        gs = data.get("game_state", {})
        return {
            "name": name,
            "player_name": gs.get("player_name", "?"),
            "scene_count": gs.get("narrative", {}).get("scene_count", 0),
            "chapter_number": gs.get("campaign", {}).get("chapter_number", 1),
            "saved_at": data.get("saved_at", ""),
            "setting_genre": gs.get("setting_genre", ""),
            "setting_tone": gs.get("setting_tone", ""),
            "setting_archetype": gs.get("setting_archetype", ""),
            "character_concept": gs.get("character_concept", ""),
            "backstory": gs.get("backstory", ""),
            "player_wishes": gs.get("preferences", {}).get("player_wishes", ""),
            "content_lines": gs.get("preferences", {}).get("content_lines", ""),
            "engine_version": data.get("engine_version", ""),
            "version_history": list(data.get("version_history", [])),
        }
    except Exception:
        return {"name": name, "player_name": "?", "scene_count": 0,
                "chapter_number": 1, "saved_at": "", "setting_genre": "",
                "engine_version": "", "version_history": []}

def list_saves_with_info(username: str) -> list[dict]:
    """List all saves with metadata, sorted by saved_at descending (newest first)."""
    saves = list_saves(username)
    infos = []
    for name in saves:
        info = get_save_info(username, name)
        if info:
            infos.append(info)
    # Sort: newest first
    infos.sort(key=lambda x: str(x.get("saved_at", "")), reverse=True)
    return infos

def delete_save(username: str, name: str) -> bool:
    """Delete a save file and its chapter archives. Returns True if deleted, False if not found."""
    path = get_save_dir(username) / f"{name}.json"
    if path.exists():
        path.unlink()
        delete_chapter_archives(username, name)
        log(f"[Save] Deleted: {username}/{name}")
        return True
    return False

# CHAPTER ARCHIVES (separate files per chapter for read-only replay)

def save_chapter_archive(username: str, save_name: str, chapter_number: int,
                         chat_messages: list, title: str = "") -> Path:
    """Archive chat messages for a completed chapter as a separate file."""
    chapter_dir = get_save_dir(username) / "chapters" / save_name
    chapter_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "chapter": chapter_number,
        "title": title or f"Chapter {chapter_number}",
        "archived_at": datetime.now().isoformat(),
        "chat_messages": [
            {k: v for k, v in msg.items() if k not in ("audio_bytes", "audio_format")}
            for msg in chat_messages if not msg.get("recap")
        ],
    }
    path = chapter_dir / f"chapter_{chapter_number}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[ChapterArchive] Saved ch{chapter_number} for {username}/{save_name} "
        f"({len(data['chat_messages'])} msgs, title={title!r})")
    return path

def load_chapter_archive(username: str, save_name: str, chapter_number: int) -> tuple[list, str]:
    """Load archived chat messages for a chapter. Returns (chat_messages, title)."""
    path = get_save_dir(username) / "chapters" / save_name / f"chapter_{chapter_number}.json"
    if not path.exists():
        return [], ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("chat_messages", []), data.get("title", "")
    except (json.JSONDecodeError, OSError) as e:
        log(f"[ChapterArchive] Load failed ch{chapter_number}: {e}", level="warning")
        return [], ""

def list_chapter_archives(username: str, save_name: str) -> list[dict]:
    """List available chapter archives for a save. Returns [{"chapter": 1, "title": "..."}, ...]."""
    chapter_dir = get_save_dir(username) / "chapters" / save_name
    if not chapter_dir.exists():
        return []
    archives = []
    for f in chapter_dir.iterdir():
        m = re.match(r"chapter_(\d+)\.json", f.name)
        if m:
            ch_num = int(m.group(1))
            title = ""
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                title = data.get("title", "")
            except (json.JSONDecodeError, OSError):
                pass
            archives.append({"chapter": ch_num, "title": title})
    archives.sort(key=lambda x: int(str(x.get("chapter", 0))))
    return archives

def delete_chapter_archives(username: str, save_name: str):
    """Delete all chapter archives for a save slot."""
    chapter_dir = get_save_dir(username) / "chapters" / save_name
    if chapter_dir.exists():
        import shutil
        shutil.rmtree(chapter_dir, ignore_errors=True)
        log(f"[ChapterArchive] Deleted archives: {username}/{save_name}")

def copy_chapter_archives(username: str, src_save: str, dst_save: str):
    """Copy all chapter archives from one save slot to another.
    Destination directory is created if it does not exist.
    If source does not exist, this is a no-op."""
    import shutil
    src_dir = get_save_dir(username) / "chapters" / src_save
    dst_dir = get_save_dir(username) / "chapters" / dst_save
    if not src_dir.exists():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        shutil.copy2(f, dst_dir / f.name)
    log(f"[ChapterArchive] Copied archives: {username}/{src_save} → {dst_save} "
        f"({len(list(src_dir.iterdir()))} file(s))")

