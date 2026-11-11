import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import yaml

from straightjacket.engine.config_binding import build_strict
from straightjacket.engine.logging_util import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


_CONFIG_PATH = Path(os.environ.get("STRAIGHTJACKET_CONFIG", str(PROJECT_ROOT / "config.yaml")))


def _read_version() -> str:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        msg = f'no `version = "..."` line in {pyproject}'
        raise RuntimeError(msg)
    return m.group(1)


VERSION = _read_version()


USERS_DIR = Path(os.environ.get("STRAIGHTJACKET_USERS_DIR", str(PROJECT_ROOT / "users")))
USERS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ProviderConfig:
    type: str
    api_base: str
    api_key_env: str
    timeout_seconds: float


@dataclass
class ClusterConfig:
    provider: str
    model: str
    temperature: float | None
    top_p: float | None
    max_tokens: int
    max_retries: int
    extra_body: dict[str, object]


@dataclass
class AIConfig:
    providers: dict[str, ProviderConfig]
    prompts_dir: str
    clusters: dict[str, ClusterConfig]
    role_cluster: dict[str, str]


@dataclass
class ServerConfig:
    host: str
    port: int
    stream_narration: bool


@dataclass
class LanguageConfig:
    narration_language: str


@dataclass
class AppConfig:
    server: ServerConfig
    ai: AIConfig
    language: LanguageConfig


_ROLES = (
    "narrator",
    "blueprint_voicing",
    "director",
    "recap",
    "brain",
    "correction",
    "narrator_metadata",
    "opening_setup",
)


def _check_roles(ai: AIConfig) -> None:
    if unknown := sorted(set(ai.role_cluster) - set(_ROLES)):
        msg = f"{_CONFIG_PATH.name}.ai.role_cluster: unknown keys {unknown}"
        raise ValueError(msg)
    if missing := sorted(set(_ROLES) - set(ai.role_cluster)):
        msg = f"{_CONFIG_PATH.name}.ai.role_cluster: missing keys {missing}"
        raise ValueError(msg)
    for role, cluster in ai.role_cluster.items():
        if cluster not in ai.clusters:
            msg = (
                f"Role '{role}' maps to cluster '{cluster}', which is not defined under ai.clusters. "
                f"Defined clusters: {sorted(ai.clusters)}."
            )
            raise ValueError(msg)


def _parse_config(data: object) -> AppConfig:
    config = build_strict(AppConfig, data, _CONFIG_PATH.name)
    for name, cluster in config.ai.clusters.items():
        if cluster.provider not in config.ai.providers:
            msg = (
                f"Cluster '{name}' uses provider '{cluster.provider}', which is not defined under ai.providers. "
                f"Defined providers: {sorted(config.ai.providers)}."
            )
            raise ValueError(msg)
    _check_roles(config.ai)
    return config


def _load_config_file() -> object:
    if not _CONFIG_PATH.exists():
        msg = (
            f"Config file not found: {_CONFIG_PATH}\n"
            f"The config.yaml file ships with the repo — if you deleted it, restore it from git.\n"
            f"To use a different config file, set the STRAIGHTJACKET_CONFIG environment variable."
        )
        raise FileNotFoundError(msg)
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data: object = yaml.safe_load(f)
    log(f"[Config] Loaded {_CONFIG_PATH}")
    return data


_cache: dict[Path, AppConfig] = {}


def cfg() -> AppConfig:
    if _CONFIG_PATH not in _cache:
        _cache[_CONFIG_PATH] = _parse_config(_load_config_file())
    return _cache[_CONFIG_PATH]


def narration_language() -> str:
    return cfg().language.narration_language


def _cluster_for_role(role: str) -> ClusterConfig:
    c = cfg()
    return c.ai.clusters[c.ai.role_cluster[role]]


def provider_for_role(role: str) -> str:
    return _cluster_for_role(role).provider


def model_for_role(role: str) -> str:
    cluster = _cluster_for_role(role)
    if not cluster.model:
        cluster_name = cfg().ai.role_cluster[role]
        msg = f"No model configured for role '{role}'. Set ai.clusters.{cluster_name}.model in config.yaml."
        raise ValueError(msg)
    return cluster.model


class SamplingParams(TypedDict):
    max_tokens: int
    max_retries: int
    temperature: float | None
    top_p: float | None
    extra_body: dict[str, object]


def sampling_params(role: str) -> SamplingParams:
    cluster = _cluster_for_role(role)

    return {
        "max_tokens": cluster.max_tokens,
        "max_retries": cluster.max_retries,
        "temperature": cluster.temperature,
        "top_p": cluster.top_p,
        "extra_body": cluster.extra_body,
    }
