#!/usr/bin/env python3
"""Straightjacket config loader: yaml-driven configuration.

config.yaml is the single source of truth for all engine settings.
The file ships with the repo. If it's missing, the engine does not start.
Config path can be overridden via STRAIGHTJACKET_CONFIG environment variable.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


from .bootstrap_log import bootstrap_log as _log

# Project root: config.yaml, engine.yaml, data/, users/, logs/ all live here.
# Single source of truth — every module imports PROJECT_ROOT from here.
PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent
)  # engine/ -> straightjacket/ -> src/ -> project root
_CONFIG_PATH = Path(os.environ.get("STRAIGHTJACKET_CONFIG", str(PROJECT_ROOT / "config.yaml")))


def _read_version() -> str:
    """Read version from pyproject.toml — single source of truth."""
    import re as _re

    pyproject = PROJECT_ROOT / "pyproject.toml"
    if pyproject.exists():
        m = _re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), _re.MULTILINE)
        if m:
            return m.group(1)
    return "0.0.0"


VERSION = _read_version()

# PATHS (used by logging_util, persistence, etc.)

USERS_DIR = PROJECT_ROOT / "users"
USERS_DIR.mkdir(exist_ok=True)
GLOBAL_CONFIG_FILE = _CONFIG_PATH


# ── Typed config dataclasses ─────────────────────────────────


@dataclass
class PerRoleInt:
    """Per-AI-role integer values (max_tokens, max_retries, max_tool_rounds)."""

    brain: int = 8192
    brain_setup: int = 8192
    narrator: int = 8192
    narrator_metadata: int = 8192
    opening_setup: int = 8192
    revelation_check: int = 8192
    recap: int = 8192
    architect: int = 8192
    director: int = 8192
    correction: int = 8192
    chapter_summary: int = 8192
    validator: int = 8192
    validator_architect: int = 8192

    def __getattr__(self, key: str) -> int:
        raise AttributeError(f"No per-role value for '{key}'")


@dataclass
class PerRoleFloat:
    """Per-AI-role float values (temperature, top_p)."""

    _data: dict[str, float] = field(default_factory=dict, repr=False)

    def __getattr__(self, key: str) -> float | None:
        if key == "_data":
            return super().__getattribute__(key)
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(f"No per-role value for '{key}'") from None

    def get(self, key: str, default: float | None = None) -> float | None:
        return self._data.get(key, default)


@dataclass
class ToolRounds:
    """Max tool calling rounds per AI role."""

    brain: int = 3
    director: int = 3


@dataclass
class PerRoleDict:
    """Per-AI-role dict values (extra_body). Default applies when no per-role override exists."""

    _data: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def get(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if key in self._data:
            return self._data[key]
        if "default" in self._data:
            return self._data["default"]
        return default or {}


@dataclass
class AIConfig:
    """AI provider and model configuration."""

    provider: str = "openai_compatible"
    api_base: str = ""
    api_key_env: str = ""
    prompts_file: str = "prompts.yaml"
    brain_model: str = ""
    narrator_model: str = ""
    director_model: str = ""
    validator_model: str = ""
    metadata_model: str = ""
    extra_body: PerRoleDict = field(default_factory=PerRoleDict)
    max_tokens: PerRoleInt = field(default_factory=PerRoleInt)
    max_retries: PerRoleInt = field(default_factory=PerRoleInt)
    max_tool_rounds: ToolRounds = field(default_factory=ToolRounds)
    temperature: PerRoleFloat = field(default_factory=PerRoleFloat)
    top_p: PerRoleFloat = field(default_factory=PerRoleFloat)


@dataclass
class ServerConfig:
    """Server bind settings."""

    host: str = "127.0.0.1"
    port: int = 8081


@dataclass
class LanguageConfig:
    """Language and naming defaults."""

    narration_language: str = "English"
    default_player_name: str = "Unnamed"


@dataclass
class AppConfig:
    """Complete typed application config from config.yaml."""

    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)


def _build_per_role_int(data: dict, defaults: PerRoleInt | None = None) -> PerRoleInt:
    """Build PerRoleInt from YAML dict, using defaults for missing keys."""
    base = defaults or PerRoleInt()
    kwargs: dict[str, int] = {}
    for f in PerRoleInt.__dataclass_fields__:
        if f in data:
            kwargs[f] = int(data[f])
        else:
            kwargs[f] = getattr(base, f)
    return PerRoleInt(**kwargs)


def _build_per_role_float(data: dict) -> PerRoleFloat:
    """Build PerRoleFloat from YAML dict."""
    return PerRoleFloat(_data={k: float(v) for k, v in data.items() if v is not None})


def _build_per_role_dict(data: dict | Any) -> PerRoleDict:
    """Build PerRoleDict from YAML. Accepts either a flat dict (becomes default) or a role-keyed dict of dicts."""
    if not isinstance(data, dict):
        return PerRoleDict()
    # If any value is a dict, treat as role-keyed
    if any(isinstance(v, dict) for v in data.values()):
        return PerRoleDict(_data={k: dict(v) for k, v in data.items() if isinstance(v, dict)})
    # Flat dict: use as default for all roles
    return PerRoleDict(_data={"default": dict(data)})


def _parse_config(data: dict) -> AppConfig:
    """Parse raw config.yaml dict into typed AppConfig."""
    c = AppConfig()

    if "server" in data:
        sd = data["server"]
        c.server = ServerConfig(host=sd.get("host", "127.0.0.1"), port=sd.get("port", 8081))

    if "ai" in data:
        ad = data["ai"]
        c.ai = AIConfig(
            provider=ad.get("provider", "openai_compatible"),
            api_base=ad.get("api_base", ""),
            api_key_env=ad.get("api_key_env", ""),
            prompts_file=ad.get("prompts_file", "prompts.yaml"),
            brain_model=ad.get("brain_model", ""),
            narrator_model=ad.get("narrator_model", ""),
            director_model=ad.get("director_model", ""),
            validator_model=ad.get("validator_model", ""),
            metadata_model=ad.get("metadata_model", ""),
            extra_body=_build_per_role_dict(ad.get("extra_body", {})),
            max_tokens=_build_per_role_int(ad.get("max_tokens", {})),
            max_retries=_build_per_role_int(
                ad.get("max_retries", {}), PerRoleInt(**{f: 3 for f in PerRoleInt.__dataclass_fields__})
            ),
            max_tool_rounds=ToolRounds(
                brain=ad.get("max_tool_rounds", {}).get("brain", 3),
                director=ad.get("max_tool_rounds", {}).get("director", 3),
            ),
            temperature=_build_per_role_float(ad.get("temperature", {})),
            top_p=_build_per_role_float(ad.get("top_p", {})),
        )

    if "language" in data:
        ld = data["language"]
        c.language = LanguageConfig(
            narration_language=ld.get("narration_language", "English"),
            default_player_name=ld.get("default_player_name", "Unnamed"),
        )

    return c


# ── Singleton ────────────────────────────────────────────────


def _load_config_file() -> dict:
    """Load config.yaml. Raises if missing or unreadable."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file not found: {_CONFIG_PATH}\n"
            f"The config.yaml file ships with the repo — if you deleted it, restore it from git.\n"
            f"To use a different config file, set the STRAIGHTJACKET_CONFIG environment variable."
        )
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config file is not a valid YAML dict: {_CONFIG_PATH}")
    _log(f"[Config] Loaded {_CONFIG_PATH}")
    return data


_cfg: AppConfig | None = None


def cfg() -> AppConfig:
    """Get the global config object. Loads on first access."""
    global _cfg
    if _cfg is None:
        data = _load_config_file()
        _cfg = _parse_config(data)
    return _cfg


def reload_config() -> AppConfig:
    """Force reload from disk. Use after external edits."""
    global _cfg
    _cfg = None
    return cfg()


# CONVENIENCE ACCESSORS — single source of truth for defaults
# These exist so that no module ever hardcodes "English",
# "Unnamed", etc. as a fallback. Every default comes from config.


def narration_language() -> str:
    """Narration language for AI prompts (English name, e.g. 'English', 'German')."""
    return cfg().language.narration_language


def default_player_name() -> str:
    """Default player name when none is provided."""
    return cfg().language.default_player_name


def sampling_params(role: str) -> dict:
    """Get sampling parameters (temperature, top_p, extra_body) for an AI role.

    Returns a dict suitable for unpacking into create_with_retry():
        create_with_retry(provider, ..., **sampling_params("narrator"))
    """
    _c = cfg()
    params: dict[str, Any] = {}
    try:
        val = getattr(_c.ai.temperature, role)
        if val is not None:
            params["temperature"] = float(val)
    except AttributeError:
        pass
    try:
        val = getattr(_c.ai.top_p, role)
        if val is not None:
            params["top_p"] = float(val)
    except AttributeError:
        # Fall back to default if no per-role override
        default = _c.ai.top_p.get("default")
        if default is not None:
            params["top_p"] = float(default)
    eb = _c.ai.extra_body.get(role)
    if eb:
        params["extra_body"] = eb
    return params
