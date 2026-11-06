import shutil
from pathlib import Path
from typing import Any

from straightjacket.engine.config_loader import USERS_DIR
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.logging_util import log

_FORBIDDEN_NAME_CHARS = frozenset('<>:"|?*/\\')
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"{port}{n}" for port in ("COM", "LPT") for n in "123456789¹²³"}
)


class InvalidNameError(ValueError):
    pass


def _safe_name(name: str) -> str:
    if any(ch in _FORBIDDEN_NAME_CHARS or ch < " " for ch in name):
        msg = f"Name contains a character no file name may hold: {name!r}"
        raise InvalidNameError(msg)
    clean = " ".join(name.split())
    if not clean:
        msg = f"Invalid name: {name!r}"
        raise InvalidNameError(msg)
    max_length = eng().persistence.max_name_length
    if len(clean) > max_length:
        msg = f"Name too long ({len(clean)} chars, max {max_length}): {name[:20]!r}..."
        raise InvalidNameError(msg)
    if clean.startswith("."):
        msg = f"Name starts with a dot: {name!r}"
        raise InvalidNameError(msg)
    if clean.endswith("."):
        msg = f"Name ends with a dot, which Windows drops: {name!r}"
        raise InvalidNameError(msg)
    if clean.split(".")[0].strip().upper() in _WINDOWS_RESERVED_NAMES:
        msg = f"Name is a reserved device name on Windows: {name!r}"
        raise InvalidNameError(msg)
    return clean


def _get_user_dir(username: str) -> Path:
    return USERS_DIR / _safe_name(username)


def get_save_dir(username: str) -> Path:
    return _get_user_dir(username) / "saves"


def list_users() -> list[dict[str, Any]]:
    return [{"name": p.name} for p in sorted(USERS_DIR.iterdir()) if p.is_dir()]


def create_user(name: str) -> None:
    user_dir = _get_user_dir(name)
    if user_dir.exists():
        return
    (user_dir / "saves").mkdir(parents=True)
    log(f"[User] Created user: {name}")


def delete_user(name: str) -> None:
    user_dir = _get_user_dir(name)
    if not user_dir.exists():
        return
    shutil.rmtree(user_dir)
    log(f"[User] Deleted user: {name}")
