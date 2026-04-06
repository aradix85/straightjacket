#!/usr/bin/env python3
"""Straightjacket logging, user directory management, config load/save."""

import contextlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config_loader import GLOBAL_CONFIG_FILE, USERS_DIR


def _get_user_dir(username: str) -> Path:
    return USERS_DIR / username

def get_save_dir(username: str) -> Path:
    return _get_user_dir(username) / "saves"

def _get_user_config_file(username: str) -> Path:
    return _get_user_dir(username) / "settings.json"

def setup_file_logging():
    """Set up console logging. Safe to call multiple times."""
    logger = logging.getLogger("rpg_engine")
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("%(name)s %(message)s"))
    logger.addHandler(ch)

def get_logger(component: str) -> logging.Logger:
    """Get a child logger for a specific engine component.

    Usage in modules:
        _log = get_logger("npc")
        _log.info("[NPC] Something happened")

    Component loggers inherit from rpg_engine but can be configured
    independently: logging.getLogger("rpg_engine.ai").setLevel(logging.WARNING)
    """
    parent = logging.getLogger("rpg_engine")
    if not parent.handlers:
        setup_file_logging()
    return parent.getChild(component)

def log(msg: str, level: str = "info"):
    """Log a message via the root engine logger.
    Drop-in replacement for print() throughout the codebase.
    """
    logger = logging.getLogger("rpg_engine")
    if not logger.handlers:
        setup_file_logging()
    getattr(logger, level, logger.info)(msg)

def load_global_config() -> dict:
    """Load global server config.

    Delegates to cfg() — single source of truth for config.yaml.
    Returns the 'server' section as a flat dict.
    """
    try:
        from .config_loader import cfg as _cfg
        server = _cfg().server
        return server.to_dict()
    except Exception:
        return {}

def save_global_config(cfg: dict):
    """Merge and save server config section to the global config yaml.
    Existing keys are preserved, passed keys are updated.
    Restricts file permissions to owner-only.
    """
    try:
        import yaml
        full_cfg: dict = {}
        if GLOBAL_CONFIG_FILE.exists():
            full_cfg = yaml.safe_load(GLOBAL_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        if "server" not in full_cfg:
            full_cfg["server"] = {}
        full_cfg["server"].update(cfg)
        GLOBAL_CONFIG_FILE.write_text(yaml.dump(full_cfg, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        # Restrict permissions: owner read/write only (no group/others)
        try:
            import stat
            GLOBAL_CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass  # Windows doesn't support Unix permissions — skip silently
    except OSError:
        pass

def load_user_config(username: str) -> dict:
    """Load per-user settings."""
    cfg_file = _get_user_config_file(username)
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_user_config(username: str, cfg: dict):
    """Save per-user settings to settings.json."""
    cfg_file = _get_user_config_file(username)
    with contextlib.suppress(OSError):
        cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# USER MANAGEMENT

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
    import shutil
    shutil.rmtree(user_dir)
    log(f"[User] Deleted user: {name}")
    return True

