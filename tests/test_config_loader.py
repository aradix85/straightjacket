from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine import config_loader


def _full_config_data(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "server": {"host": "127.0.0.1", "port": 8081, "stream_narration": True},
        "language": {"narration_language": "English"},
        "ai": {
            "prompts_dir": "prompts",
            "providers": {
                "local": {
                    "type": "openai_compatible",
                    "api_base": "http://localhost:9/v1",
                    "api_key_env": "LOCAL_KEY",
                    "timeout_seconds": 30,
                },
            },
            "clusters": {
                "classification": {
                    "provider": "local",
                    "model": "qwen",
                    "temperature": 0.5,
                    "top_p": 0.95,
                    "max_tokens": 8192,
                    "max_retries": 3,
                    "extra_body": {"foo": "bar"},
                }
            },
            "role_cluster": {"recap": "classification"},
        },
    }
    base.update(overrides)
    return base


@pytest.fixture
def read_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[dict[str, Any]], None]:
    def read(data: dict[str, Any]) -> None:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_PATH", path)
        monkeypatch.setattr(config_loader, "_cfg", None)
        config_loader.cfg()

    return read


def test_a_role_reaches_the_settings_of_its_cluster_and_provider(read_config: Callable[[dict[str, Any]], None]) -> None:
    read_config(_full_config_data())
    assert (config_loader.provider_for_role("recap"), config_loader.model_for_role("recap")) == ("local", "qwen")
    assert config_loader.sampling_params("recap") == {
        "max_tokens": 8192,
        "max_retries": 3,
        "temperature": 0.5,
        "top_p": 0.95,
        "extra_body": {"foo": "bar"},
    }
    provider = config_loader.cfg().ai.providers["local"]
    assert (provider.type, provider.api_key_env, provider.timeout_seconds) == ("openai_compatible", "LOCAL_KEY", 30.0)


def test_a_sampling_value_set_to_null_is_not_sent(read_config: Callable[[dict[str, Any]], None]) -> None:
    data = _full_config_data()
    data["ai"]["clusters"]["classification"].update(temperature=None, top_p=None)
    read_config(data)
    assert not {"temperature", "top_p"} & set(config_loader.sampling_params("recap"))


def _cluster(data: dict[str, Any]) -> dict[str, Any]:
    cluster: dict[str, Any] = data["ai"]["clusters"]["classification"]
    return cluster


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data.clear(), "missing required fields"),
        (lambda data: data.update(colour="blue"), r"the top level has unknown keys \['colour'\]"),
        (
            lambda data: _cluster(data).update(temprature=0.4),
            r"cluster 'classification' has unknown keys \['temprature'\]",
        ),
        (lambda data: _cluster(data).pop("provider"), "missing required fields"),
        (lambda data: data["ai"]["clusters"].update(classification="qwen"), "must be a mapping"),
        (lambda data: _cluster(data).update(provider="elsewhere"), r"not defined under ai\.providers"),
    ],
    ids=["empty", "unknown_top_key", "unknown_cluster_key", "missing_field", "not_a_mapping", "unknown_provider"],
)
def test_a_config_file_that_does_not_fit_stops_loading(
    read_config: Callable[[dict[str, Any]], None], change: Callable[[dict[str, Any]], object], message: str
) -> None:
    data = _full_config_data()
    change(data)
    with pytest.raises(ValueError, match=message):
        read_config(data)


def _users_dirs_in_a_fresh_process(env: dict[str, str]) -> list[str]:
    import subprocess
    import sys

    code = "from straightjacket.engine import config_loader, user_management; print(config_loader.USERS_DIR); print(user_management.USERS_DIR)"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    return out.stdout.split()


def test_the_users_folder_follows_the_environment(tmp_path: Path) -> None:
    import os

    players = tmp_path / "elsewhere" / "players"
    env = {**os.environ, "STRAIGHTJACKET_USERS_DIR": str(players)}
    assert _users_dirs_in_a_fresh_process(env) == [str(players), str(players)]
    assert players.is_dir()


def test_the_users_folder_defaults_to_the_project() -> None:
    import os

    env = {key: value for key, value in os.environ.items() if key != "STRAIGHTJACKET_USERS_DIR"}
    expected = str(config_loader.PROJECT_ROOT / "users")
    assert _users_dirs_in_a_fresh_process(env) == [expected, expected]
