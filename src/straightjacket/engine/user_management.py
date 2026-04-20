"""User and save directory management, config load/save.

Split from logging_util.py — these are filesystem operations for user data,
not logging concerns. logging_util.py retains only log(), setup_file_logging(),
and get_logger().
"""

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from .config_loader import GLOBAL_CONFIG_FILE, USERS_DIR, cfg as _cfg
from .logging_util import log


def _safe_name(name: str) -> str:
    """Sanitize a user/save name to prevent path traversal and filesystem issues.

    Strips path separators, parent references, null bytes, and leading dots.
    Rejects empty results and names that are filesystem-special (., ..).
    Max 100 characters to prevent filesystem edge cases.
    """
    clean = name.replace("/", "").replace("\\", "").replace("\0", "").replace("..", "").strip()
    clean = clean.lstrip(".")
    clean = " ".join(clean.split())
    if not clean or clean in (".", ".."):
        raise ValueError(f"Invalid name: {name!r}")
    if len(clean) > 100:
        raise ValueError(f"Name too long ({len(clean)} chars, max 100): {name[:20]!r}...")
    return clean


def _get_user_dir(username: str) -> Path:
    return USERS_DIR / _safe_name(username)


def get_save_dir(username: str) -> Path:
    return _get_user_dir(username) / "saves"


def _get_user_config_file(username: str) -> Path:
    return _get_user_dir(username) / "settings.json"


def load_global_config() -> dict:
    """Load global server config.

    Delegates to cfg() — single source of truth for config.yaml.
    Returns the 'server' section as a flat dict.
    """

    try:
        return asdict(_cfg().server)
    except (OSError, ValueError, KeyError) as e:
        log(f"[UserMgmt] load_global_config failed: {e}", level="warning")
        return {}


def save_global_config(cfg: dict) -> None:
    """Merge and save server config section to the global config yaml."""

    try:
        full_cfg: dict = {}
        if GLOBAL_CONFIG_FILE.exists():
            full_cfg = yaml.safe_load(GLOBAL_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        if "server" not in full_cfg:
            full_cfg["server"] = {}
        full_cfg["server"].update(cfg)
        GLOBAL_CONFIG_FILE.write_text(
            yaml.dump(full_cfg, default_flow_style=False, allow_unicode=True), encoding="utf-8"
        )
    except OSError as e:
        log(f"[UserMgmt] save_global_config write failed: {e}", level="warning")
        return
    try:
        import stat

        GLOBAL_CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as e:
        log(f"[UserMgmt] chmod on {GLOBAL_CONFIG_FILE.name} failed: {e}", level="warning")


def load_user_config(username: str) -> dict:
    """Load per-user settings."""
    cfg_file = _get_user_config_file(username)
    if not cfg_file.exists():
        return {}
    try:
        return json.loads(cfg_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"[UserMgmt] load_user_config('{username}') failed: {e}", level="warning")
        return {}


def save_user_config(username: str, cfg: dict) -> None:
    """Save per-user settings to settings.json."""
    cfg_file = _get_user_config_file(username)
    try:
        cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log(f"[UserMgmt] save_user_config('{username}') failed: {e}", level="warning")


def list_users() -> list[dict]:
    """List all users. Returns list of dicts with 'name'."""
    users = []
    if USERS_DIR.exists():
        for p in sorted(USERS_DIR.iterdir()):
            if p.is_dir():
                users.append({"name": p.name})
    return users


def create_user(name: str) -> bool:
    """Create a new user directory with metadata."""
    user_dir = _get_user_dir(name)
    if user_dir.exists():
        return False
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "saves").mkdir(exist_ok=True)
    meta = {"created": datetime.now().isoformat()}
    (user_dir / "user.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    log(f"[User] Created user: {name}")
    return True


def delete_user(name: str) -> bool:
    """Delete a user and all their data."""
    user_dir = _get_user_dir(name)
    if not user_dir.exists():
        return False

    shutil.rmtree(user_dir)
    log(f"[User] Deleted user: {name}")
    return True
