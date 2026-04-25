"""Straightjacket config loader: yaml-driven configuration.

config.yaml is the single source of truth for all engine settings.
The file ships with the repo. If it's missing, the engine does not start.
Config path can be overridden via STRAIGHTJACKET_CONFIG environment variable.
"""

import os
import re
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
# STRAIGHTJACKET_CONFIG env var overrides the default config path. Fallback
# is a deployment-time mechanism, not a domain-rule fallback.
_CONFIG_PATH = Path(os.environ.get("STRAIGHTJACKET_CONFIG", str(PROJECT_ROOT / "config.yaml")))


def _read_version() -> str:
    """Read version from pyproject.toml — single source of truth."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        raise RuntimeError(f"pyproject.toml not found at {pyproject}; cannot determine version")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise RuntimeError(f'no `version = "..."` line in {pyproject}')
    return m.group(1)


VERSION = _read_version()

# PATHS (used by logging_util, persistence, etc.)

USERS_DIR = PROJECT_ROOT / "users"
USERS_DIR.mkdir(exist_ok=True)
GLOBAL_CONFIG_FILE = _CONFIG_PATH


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


@dataclass
class AIConfig:
    """AI provider and model configuration.

    Clusters are the single source of truth. No per-role overrides.
    To change a role's parameters, either change the cluster or remap
    the role to a different cluster via role_cluster.
    """

    provider: str
    api_base: str
    api_key_env: str
    prompts_dir: str
    clusters: dict[str, ClusterConfig]
    role_cluster: dict[str, str]


@dataclass
class ServerConfig:
    """Server bind settings."""

    host: str
    port: int


@dataclass
class LanguageConfig:
    """Language and naming defaults."""

    narration_language: str


@dataclass
class AppConfig:
    """Complete typed application config from config.yaml."""

    server: ServerConfig
    ai: AIConfig
    language: LanguageConfig


def _parse_config(data: dict) -> AppConfig:
    """Parse raw config.yaml dict into typed AppConfig. Strict — missing keys raise."""
    sd = data["server"]
    server = ServerConfig(host=sd["host"], port=sd["port"])

    ad = data["ai"]
    # Parse clusters — every field is required
    _REQUIRED_CLUSTER_FIELDS = ("model", "temperature", "top_p", "max_tokens", "max_retries")
    clusters: dict[str, ClusterConfig] = {}
    for cname, cdata in ad["clusters"].items():
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
            # extra_body holds provider-specific options (e.g. Cerebras
            # response_format hints). Genuinely optional per cluster.
            extra_body=cdata.get("extra_body", {}),
        )

    ai = AIConfig(
        provider=ad["provider"],
        api_base=ad["api_base"],
        api_key_env=ad["api_key_env"],
        prompts_dir=ad["prompts_dir"],
        clusters=clusters,
        role_cluster=ad["role_cluster"],
    )

    ld = data["language"]
    language = LanguageConfig(
        narration_language=ld["narration_language"],
    )

    return AppConfig(server=server, ai=ai, language=language)


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


def _cluster_for_role(role: str) -> ClusterConfig:
    """Get the cluster config for a role. Raises if role is not mapped.

    config.yaml must list every role under ai.role_cluster, pointing to a
    cluster defined in ai.clusters. No Python defaults — if a role is
    missing here, it must be added to config.yaml.
    """
    _c = cfg()
    if role not in _c.ai.role_cluster:
        raise ValueError(
            f"Role '{role}' has no cluster assignment in config.yaml. "
            f"Add '{role}: <cluster_name>' under ai.role_cluster."
        )
    cluster_name = _c.ai.role_cluster[role]
    if cluster_name not in _c.ai.clusters:
        raise ValueError(
            f"Role '{role}' maps to cluster '{cluster_name}', but no such cluster "
            f"is defined under ai.clusters in config.yaml."
        )
    return _c.ai.clusters[cluster_name]


def model_for_role(role: str) -> str:
    """Resolve the model for an AI role from its cluster."""
    cluster = _cluster_for_role(role)
    if not cluster.model:
        cluster_name = cfg().ai.role_cluster[role]
        raise ValueError(f"No model configured for role '{role}'. Set ai.clusters.{cluster_name}.model in config.yaml.")
    return cluster.model


def sampling_params(role: str) -> dict:
    """Get all call parameters for an AI role from its cluster.

    The cluster is the single source of truth.
    Returns a dict suitable for unpacking into create_with_retry().
    """
    cluster = _cluster_for_role(role)

    params: dict[str, Any] = {
        "max_tokens": cluster.max_tokens,
        "max_retries": cluster.max_retries,
        "temperature": cluster.temperature,
        "top_p": cluster.top_p,
    }
    if cluster.extra_body:
        params["extra_body"] = cluster.extra_body

    return params
