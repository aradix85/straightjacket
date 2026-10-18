from typing import Any
import json
import shutil
from datetime import datetime
from pathlib import Path

from .config_loader import USERS_DIR
from .logging_util import log


_FORBIDDEN_NAME_CHARS = frozenset('<>:"|?*/\\')
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"{port}{n}" for port in ("COM", "LPT") for n in "123456789¹²³"}
)


class InvalidNameError(ValueError):
    pass


def _safe_name(name: str) -> str:
    if any(ch in _FORBIDDEN_NAME_CHARS or ord(ch) < 32 for ch in name):
        raise InvalidNameError(f"Name contains a character no file name may hold: {name!r}")
    clean = " ".join(name.split())
    if not clean:
        raise InvalidNameError(f"Invalid name: {name!r}")
    if len(clean) > 100:
        raise InvalidNameError(f"Name too long ({len(clean)} chars, max 100): {name[:20]!r}...")
    if clean.startswith("."):
        raise InvalidNameError(f"Name starts with a dot: {name!r}")
    if clean.endswith("."):
        raise InvalidNameError(f"Name ends with a dot, which Windows drops: {name!r}")
    if clean.split(".")[0].strip().upper() in _WINDOWS_RESERVED_NAMES:
        raise InvalidNameError(f"Name is a reserved device name on Windows: {name!r}")
    return clean


def _get_user_dir(username: str) -> Path:
    return USERS_DIR / _safe_name(username)


def get_save_dir(username: str) -> Path:
    return _get_user_dir(username) / "saves"


def list_users() -> list[dict[str, Any]]:
    users = []
    if USERS_DIR.exists():
        for p in sorted(USERS_DIR.iterdir()):
            if p.is_dir():
                users.append({"name": p.name})
    return users


def create_user(name: str) -> bool:
    user_dir = _get_user_dir(name)
    if user_dir.exists():
        return False
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "saves").mkdir(exist_ok=True)
    meta = {"created": datetime.now().astimezone().isoformat()}
    (user_dir / "user.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    log(f"[User] Created user: {name}")
    return True


def delete_user(name: str) -> bool:
    user_dir = _get_user_dir(name)
    if not user_dir.exists():
        return False

    shutil.rmtree(user_dir)
    log(f"[User] Deleted user: {name}")
    return True
