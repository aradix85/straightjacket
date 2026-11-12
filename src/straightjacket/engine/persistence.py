from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar

from straightjacket.engine.logging_util import log
from straightjacket.engine.models import GameState
from straightjacket.engine.serialization import SerializableMixin, build_strict, shaped
from straightjacket.engine.user_management import _safe_name, get_save_dir

if TYPE_CHECKING:
    from pathlib import Path

_S = TypeVar("_S")


class IncompatibleSaveError(Exception):
    pass


@dataclass
class ChatMessage(SerializableMixin):
    role: str
    content: str
    epilogue: bool


@dataclass
class SavedGame(SerializableMixin):
    saved_at: str
    game_state: GameState
    chat_messages: list[ChatMessage]


@dataclass
class SaveInfo(SerializableMixin):
    name: str
    player_name: str
    scene_count: int
    chapter_number: int
    saved_at: str


def save_game(game: GameState, username: str, chat_messages: list[ChatMessage], name: str) -> None:
    name = _safe_name(name)
    save_dir = get_save_dir(username)
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"{name}.json"

    saved = SavedGame(saved_at=datetime.now().astimezone().isoformat(), game_state=game, chat_messages=chat_messages)
    path.write_text(json.dumps(saved.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[Save] Game saved: {username}/{name} (Scene {game.narrative.scene_count}, {len(chat_messages)} chat msgs)")


def load_game(username: str, name: str) -> tuple[GameState | None, list[ChatMessage]]:
    name = _safe_name(name)
    save_dir = get_save_dir(username)
    path = save_dir / f"{name}.json"
    if not path.exists():
        log(f"[Load] No save named {username}/{name}")
        return None, []
    data = json.loads(path.read_text(encoding="utf-8"))

    try:
        saved = build_strict(SavedGame, data, f"{username}/{name}")
    except ValueError as e:
        raise IncompatibleSaveError(str(e)) from e

    game, chat_messages = saved.game_state, saved.chat_messages
    log(
        f"[Load] Game loaded: {username}/{name} "
        f"({game.player_name}, Scene {game.narrative.scene_count}, {len(chat_messages)} chat msgs)"
    )
    return game, chat_messages


def _header(part: dict[str, object], key: str, shape: type[_S], where: str) -> _S:
    return shaped(part[key], shape, f"{where}: {key} expected {shape.__name__}")


def _save_info(path: Path) -> SaveInfo:
    where = path.name
    data = shaped(json.loads(path.read_text(encoding="utf-8")), dict, f"{where}: expected dict")
    game = _header(data, "game_state", dict, where)
    return SaveInfo(
        name=path.stem,
        player_name=_header(game, "player_name", str, where),
        scene_count=_header(_header(game, "narrative", dict, where), "scene_count", int, where),
        chapter_number=_header(_header(game, "campaign", dict, where), "chapter_number", int, where),
        saved_at=_header(data, "saved_at", str, where),
    )


def list_saves_with_info(username: str) -> list[SaveInfo]:
    infos = []
    for path in get_save_dir(username).glob("*.json"):
        try:
            infos.append(_save_info(path))
        except (OSError, ValueError, KeyError) as e:
            log(f"[Persistence] Skipping corrupt save '{path.name}': {e}", level="warning")
    infos.sort(key=lambda info: info.saved_at, reverse=True)
    return infos


def delete_save(username: str, name: str) -> None:
    name = _safe_name(name)
    path = get_save_dir(username) / f"{name}.json"
    if not path.exists():
        return
    path.unlink()
    log(f"[Save] Deleted: {username}/{name}")
