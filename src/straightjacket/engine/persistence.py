#!/usr/bin/env python3
"""Straightjacket persistence: save/load games."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import VERSION
from .engine_loader import eng
from .logging_util import log
from .user_management import _safe_name, get_save_dir
from .models import GameState
from .npc import (
    apply_name_sanitization,
    normalize_npc_dispositions,
)

# SAVE / LOAD


def save_game(game: GameState, username: str, chat_messages: list | None = None, name: str = "autosave") -> Path:
    """Save game state and chat history."""
    name = _safe_name(name)
    save_dir = get_save_dir(username)
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"{name}.json"

    data: dict[str, Any] = {"saved_at": datetime.now().isoformat()}
    data["engine_version"] = VERSION
    data["game_state"] = game.to_dict()

    # Chat history (exclude transient recaps)
    raw_messages = chat_messages or []
    data["chat_messages"] = [msg for msg in raw_messages if not msg.get("recap")]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(
        f"[Save] Game saved: {username}/{name} (Scene {game.narrative.scene_count}, {len(data['chat_messages'])} chat msgs)"
    )
    return path


def load_game(username: str, name: str = "autosave") -> tuple[GameState | None, list]:
    """Load game state and chat history. Returns (game, chat_messages)."""
    name = _safe_name(name)
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
        apply_name_sanitization(npc)

    chat_messages = data.get("chat_messages", [])
    log(
        f"[Load] Game loaded: {username}/{name} ({game.player_name}, Scene {game.narrative.scene_count}, {len(chat_messages)} chat msgs)"
    )

    # Rebuild database from loaded state
    from .db import sync as _db_sync
    from .db.connection import reset_db

    reset_db()
    _db_sync(game)

    return game, chat_messages


def list_saves_with_info(username: str) -> list[dict]:
    """List all saves with metadata, sorted newest first."""
    save_dir = get_save_dir(username)
    if not save_dir.exists():
        return []
    infos = []
    for path in save_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            gs = data.get("game_state", {})
            infos.append(
                {
                    "name": path.stem,
                    "player_name": gs.get("player_name", "?"),
                    "scene_count": gs.get("narrative", {}).get("scene_count", 0),
                    "chapter_number": gs.get("campaign", {}).get("chapter_number", 1),
                    "saved_at": data.get("saved_at", ""),
                }
            )
        except Exception:
            infos.append({"name": path.stem, "player_name": "?", "scene_count": 0, "chapter_number": 1, "saved_at": ""})
    infos.sort(key=lambda x: str(x.get("saved_at", "")), reverse=True)
    return infos


def delete_save(username: str, name: str) -> bool:
    """Delete a save file. Returns True if deleted, False if not found."""
    name = _safe_name(name)
    save_dir = get_save_dir(username)
    path = save_dir / f"{name}.json"
    if not path.exists():
        return False
    path.unlink()
    # Clean up any orphaned chapter archive directory
    chapter_dir = save_dir / "chapters" / name
    if chapter_dir.exists():
        import shutil

        shutil.rmtree(chapter_dir, ignore_errors=True)
    log(f"[Save] Deleted: {username}/{name}")
    return True
