import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine import config_loader
from tests._helpers import config_data, every_role


def _full_config_data() -> dict[str, Any]:
    return config_data(
        providers={
            "local": {
                "type": "openai_compatible",
                "api_base": "http://localhost:9/v1",
                "api_key_env": "LOCAL_KEY",
                "timeout_seconds": 30,
            },
        },
        clusters={
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
        role_cluster=every_role("classification"),
    )


@pytest.fixture(name="read_config")
def fixture_read_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[dict[str, Any]], None]:
    def read(data: dict[str, Any]) -> None:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        monkeypatch.setattr(config_loader, "_CONFIG_PATH", path)
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


def test_a_sampling_value_set_to_null_stays_unset(read_config: Callable[[dict[str, Any]], None]) -> None:
    data = _full_config_data()
    data["ai"]["clusters"]["classification"].update(temperature=None, top_p=None)
    read_config(data)
    params = config_loader.sampling_params("recap")
    assert (params["temperature"], params["top_p"]) == (None, None)


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
        (lambda data: _cluster(data).update(provider="elsewhere"), r"not defined under ai\.providers"),
        (lambda data: data["ai"]["role_cluster"].update(recap="creative"), r"not defined under ai\.clusters"),
        (
            lambda data: data["ai"]["role_cluster"].update(narator="classification"),
            r"ai\.role_cluster has unknown keys \['narator'\]",
        ),
        (
            lambda data: data["ai"]["role_cluster"].pop("recap"),
            r"ai\.role_cluster missing required fields: \['recap'\]",
        ),
    ],
    ids=[
        "empty",
        "unknown_top_key",
        "unknown_cluster_key",
        "missing_field",
        "unknown_provider",
        "unknown_cluster",
        "unknown_role",
        "missing_role",
    ],
)
def test_a_config_file_that_does_not_fit_stops_loading(
    read_config: Callable[[dict[str, object]], None], change: Callable[[dict[str, object]], object], message: str
) -> None:
    data = _full_config_data()
    change(data)
    with pytest.raises(ValueError, match=message):
        read_config(data)


def test_a_config_section_that_is_not_a_mapping_stops_loading(read_config: Callable[[dict[str, object]], None]) -> None:
    data = _full_config_data()
    data["ai"]["clusters"]["classification"] = "qwen"
    with pytest.raises(TypeError, match="must be a mapping"):
        read_config(data)


def _users_dirs_in_a_fresh_process(env: dict[str, str]) -> list[str]:
    code = (
        "from straightjacket.engine import config_loader, user_management; "
        "print(config_loader.USERS_DIR); print(user_management.USERS_DIR)"
    )
    source = {"PYTHONPATH": str(config_loader.PROJECT_ROOT / "src")}
    out = subprocess.run([sys.executable, "-c", code], env=env | source, capture_output=True, text=True, check=True)
    return out.stdout.split()


def test_the_users_folder_follows_the_environment(tmp_path: Path) -> None:
    players = tmp_path / "elsewhere" / "players"
    env = {**os.environ, "STRAIGHTJACKET_USERS_DIR": str(players)}
    assert _users_dirs_in_a_fresh_process(env) == [str(players), str(players)]
    assert players.is_dir()


def test_the_users_folder_defaults_to_the_project() -> None:
    env = {key: value for key, value in os.environ.items() if key != "STRAIGHTJACKET_USERS_DIR"}
    expected = str(config_loader.PROJECT_ROOT / "users")
    assert _users_dirs_in_a_fresh_process(env) == [expected, expected]


def test_a_missing_config_file_says_how_to_restore_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_loader, "_CONFIG_PATH", tmp_path / "config.yaml")
    with pytest.raises(FileNotFoundError, match="restore it from git"):
        config_loader.cfg()


def test_a_config_file_that_is_not_a_mapping_stops_loading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("- server\n", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_PATH", path)
    with pytest.raises(TypeError, match="not a valid YAML dict"):
        config_loader.cfg()


def test_a_role_whose_cluster_names_no_model_is_refused(read_config: Callable[[dict[str, object]], None]) -> None:
    data = _full_config_data()
    data["ai"]["clusters"]["classification"]["model"] = ""
    read_config(data)
    role = next(name for name, cluster in data["ai"]["role_cluster"].items() if cluster == "classification")
    with pytest.raises(ValueError, match=f"No model configured for role '{role}'"):
        config_loader.model_for_role(role)
