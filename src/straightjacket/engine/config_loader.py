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
class ClusterConfig:
    """AI model cluster: complete specification for a group of roles.

    Every cluster in config.yaml MUST specify all fields.
    No hidden defaults — if it's not configured, it's an error.
    """

    model: str
    temperature: float
    top_p: float
    max_tokens: int
    max_retries: int
    extra_body: dict[str, Any] = field(default_factory=dict)


# Default role → cluster mapping. Override via role_cluster in config.yaml.
_DEFAULT_ROLE_CLUSTER: dict[str, str] = {
    "narrator": "narrator",
    "architect": "creative",
    "brain": "classification",
    "correction": "classification",
    "director": "creative",
    "validator": "analytical",
    "validator_architect": "analytical",
    "narrator_metadata": "analytical",
    "opening_setup": "analytical",
    "revelation_check": "analytical",
    "chapter_summary": "analytical",
    "recap": "analytical",
}


@dataclass
class AIConfig:
    """AI provider and model configuration.

    Clusters are the single source of truth. No per-role overrides.
    To change a role's parameters, either change the cluster or remap
    the role to a different cluster via role_cluster.
    """

    provider: str = "openai_compatible"
    api_base: str = ""
    api_key_env: str = ""
    prompts_file: str = "prompts.yaml"
    clusters: dict[str, ClusterConfig] = field(default_factory=dict)
    role_cluster: dict[str, str] = field(default_factory=dict)


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


def _parse_config(data: dict) -> AppConfig:
    """Parse raw config.yaml dict into typed AppConfig."""
    c = AppConfig()

    if "server" in data:
        sd = data["server"]
        c.server = ServerConfig(host=sd.get("host", "127.0.0.1"), port=sd.get("port", 8081))

    if "ai" in data:
        ad = data["ai"]

        # Parse clusters — every field is required
        _REQUIRED_CLUSTER_FIELDS = ("model", "temperature", "top_p", "max_tokens", "max_retries")
        clusters: dict[str, ClusterConfig] = {}
        for cname, cdata in ad.get("clusters", {}).items():
            if not isinstance(cdata, dict):
                continue
            missing = [f for f in _REQUIRED_CLUSTER_FIELDS if f not in cdata]
            if missing:
                raise ValueError(
                    f"Cluster '{cname}' missing required fields: {missing}. "
                    f"Every cluster must specify: {list(_REQUIRED_CLUSTER_FIELDS)}."
                )
            clusters[cname] = ClusterConfig(
                model=cdata["model"],
                temperature=float(cdata["temperature"]),
                top_p=float(cdata["top_p"]),
                max_tokens=int(cdata["max_tokens"]),
                max_retries=int(cdata["max_retries"]),
                extra_body=cdata.get("extra_body", {}),
            )

        c.ai = AIConfig(
            provider=ad.get("provider", "openai_compatible"),
            api_base=ad.get("api_base", ""),
            api_key_env=ad.get("api_key_env", ""),
            prompts_file=ad.get("prompts_file", "prompts.yaml"),
            clusters=clusters,
            role_cluster=ad.get("role_cluster", {}),
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


def _cluster_for_role(role: str) -> ClusterConfig | None:
    """Get the cluster config for a role. Returns None if no cluster assigned."""
    _c = cfg()
    cluster_name = _c.ai.role_cluster.get(role, _DEFAULT_ROLE_CLUSTER.get(role, ""))
    return _c.ai.clusters.get(cluster_name) if cluster_name else None


def model_for_role(role: str) -> str:
    """Resolve the model for an AI role from its cluster."""
    cluster = _cluster_for_role(role)
    if cluster and cluster.model:
        return cluster.model
    _c = cfg()
    cluster_name = _c.ai.role_cluster.get(role, _DEFAULT_ROLE_CLUSTER.get(role, ""))
    raise ValueError(f"No model configured for role '{role}'. Set ai.clusters.{cluster_name}.model in config.yaml.")


def sampling_params(role: str) -> dict:
    """Get all call parameters for an AI role from its cluster.

    The cluster is the single source of truth.
    Returns a dict suitable for unpacking into create_with_retry().
    """
    cluster = _cluster_for_role(role)
    if not cluster:
        raise ValueError(
            f"No cluster configured for role '{role}'. Check ai.clusters and role_cluster mapping in config.yaml."
        )

    params: dict[str, Any] = {
        "max_tokens": cluster.max_tokens,
        "max_retries": cluster.max_retries,
        "temperature": cluster.temperature,
        "top_p": cluster.top_p,
    }
    if cluster.extra_body:
        params["extra_body"] = cluster.extra_body

    return params
