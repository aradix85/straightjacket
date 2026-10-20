import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .logging_util import log

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


_CONFIG_PATH = Path(os.environ.get("STRAIGHTJACKET_CONFIG", str(PROJECT_ROOT / "config.yaml")))


def _read_version() -> str:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise RuntimeError(f'no `version = "..."` line in {pyproject}')
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
    extra_body: dict[str, Any]


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


def _check_keys(where: str, data: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"config.yaml: {where} must be a mapping")
    unknown = sorted(set(data) - set(keys))
    if unknown:
        raise ValueError(f"config.yaml: {where} has unknown keys {unknown}")
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"config.yaml: {where} missing required fields: {missing}")
    return data


_TOP_KEYS = ("server", "ai", "language")
_SERVER_KEYS = ("host", "port", "stream_narration")
_AI_KEYS = ("prompts_dir", "providers", "clusters", "role_cluster")
_PROVIDER_KEYS = ("type", "api_base", "api_key_env", "timeout_seconds")
_CLUSTER_KEYS = ("provider", "model", "temperature", "top_p", "max_tokens", "max_retries", "extra_body")
_LANGUAGE_KEYS = ("narration_language",)
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


def _parse_config(data: dict[str, Any]) -> AppConfig:
    _check_keys("the top level", data, _TOP_KEYS)
    sd = _check_keys("server", data["server"], _SERVER_KEYS)
    server = ServerConfig(host=sd["host"], port=sd["port"], stream_narration=bool(sd["stream_narration"]))

    ad = _check_keys("ai", data["ai"], _AI_KEYS)

    providers = {
        name: ProviderConfig(
            type=_check_keys(f"provider '{name}'", pd, _PROVIDER_KEYS)["type"],
            api_base=pd["api_base"],
            api_key_env=pd["api_key_env"],
            timeout_seconds=float(pd["timeout_seconds"]),
        )
        for name, pd in ad["providers"].items()
    }

    clusters: dict[str, ClusterConfig] = {}
    for cname, cdata in ad["clusters"].items():
        _check_keys(f"cluster '{cname}'", cdata, _CLUSTER_KEYS)
        if cdata["provider"] not in providers:
            raise ValueError(
                f"Cluster '{cname}' uses provider '{cdata['provider']}', which is not defined under ai.providers. "
                f"Defined providers: {sorted(providers)}."
            )
        clusters[cname] = ClusterConfig(
            provider=cdata["provider"],
            model=cdata["model"],
            temperature=None if cdata["temperature"] is None else float(cdata["temperature"]),
            top_p=None if cdata["top_p"] is None else float(cdata["top_p"]),
            max_tokens=int(cdata["max_tokens"]),
            max_retries=int(cdata["max_retries"]),
            extra_body=dict(cdata["extra_body"]),
        )

    _check_keys("ai.role_cluster", ad["role_cluster"], _ROLES)
    for role, cname in ad["role_cluster"].items():
        if cname not in clusters:
            raise ValueError(
                f"Role '{role}' maps to cluster '{cname}', which is not defined under ai.clusters. "
                f"Defined clusters: {sorted(clusters)}."
            )

    ai = AIConfig(
        providers=providers,
        prompts_dir=ad["prompts_dir"],
        clusters=clusters,
        role_cluster=ad["role_cluster"],
    )

    ld = _check_keys("language", data["language"], _LANGUAGE_KEYS)
    language = LanguageConfig(
        narration_language=ld["narration_language"],
    )

    return AppConfig(server=server, ai=ai, language=language)


def _load_config_file() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file not found: {_CONFIG_PATH}\n"
            f"The config.yaml file ships with the repo — if you deleted it, restore it from git.\n"
            f"To use a different config file, set the STRAIGHTJACKET_CONFIG environment variable."
        )
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config file is not a valid YAML dict: {_CONFIG_PATH}")
    log(f"[Config] Loaded {_CONFIG_PATH}")
    return data


_cfg: AppConfig | None = None


def cfg() -> AppConfig:
    global _cfg
    if _cfg is None:
        data = _load_config_file()
        _cfg = _parse_config(data)
    return _cfg


def narration_language() -> str:
    return cfg().language.narration_language


def _cluster_for_role(role: str) -> ClusterConfig:
    _c = cfg()
    return _c.ai.clusters[_c.ai.role_cluster[role]]


def provider_for_role(role: str) -> str:
    return _cluster_for_role(role).provider


def model_for_role(role: str) -> str:
    cluster = _cluster_for_role(role)
    if not cluster.model:
        cluster_name = cfg().ai.role_cluster[role]
        raise ValueError(f"No model configured for role '{role}'. Set ai.clusters.{cluster_name}.model in config.yaml.")
    return cluster.model


def sampling_params(role: str) -> dict[str, Any]:
    cluster = _cluster_for_role(role)

    return {
        "max_tokens": cluster.max_tokens,
        "max_retries": cluster.max_retries,
        "temperature": cluster.temperature,
        "top_p": cluster.top_p,
        "extra_body": cluster.extra_body,
    }
