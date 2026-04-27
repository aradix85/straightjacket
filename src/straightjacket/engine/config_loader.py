import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


from .bootstrap_log import bootstrap_log as _log


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


_CONFIG_PATH = Path(os.environ.get("STRAIGHTJACKET_CONFIG", str(PROJECT_ROOT / "config.yaml")))


def _read_version() -> str:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        raise RuntimeError(f"pyproject.toml not found at {pyproject}; cannot determine version")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise RuntimeError(f'no `version = "..."` line in {pyproject}')
    return m.group(1)


VERSION = _read_version()


USERS_DIR = PROJECT_ROOT / "users"
USERS_DIR.mkdir(exist_ok=True)
GLOBAL_CONFIG_FILE = _CONFIG_PATH


@dataclass
class ClusterConfig:
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    max_retries: int
    extra_body: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIConfig:
    provider: str
    api_base: str
    api_key_env: str
    prompts_dir: str
    clusters: dict[str, ClusterConfig]
    role_cluster: dict[str, str]


@dataclass
class ServerConfig:
    host: str
    port: int


@dataclass
class LanguageConfig:
    narration_language: str


@dataclass
class AppConfig:
    server: ServerConfig
    ai: AIConfig
    language: LanguageConfig


def _parse_config(data: dict) -> AppConfig:
    sd = data["server"]
    server = ServerConfig(host=sd["host"], port=sd["port"])

    ad = data["ai"]

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
    global _cfg
    if _cfg is None:
        data = _load_config_file()
        _cfg = _parse_config(data)
    return _cfg


def narration_language() -> str:
    return cfg().language.narration_language


def _cluster_for_role(role: str) -> ClusterConfig:
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
    cluster = _cluster_for_role(role)
    if not cluster.model:
        cluster_name = cfg().ai.role_cluster[role]
        raise ValueError(f"No model configured for role '{role}'. Set ai.clusters.{cluster_name}.model in config.yaml.")
    return cluster.model


def sampling_params(role: str) -> dict:
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
