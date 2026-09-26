from pathlib import Path


def _full_config_data(**overrides: object) -> dict:
    base = {
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
                }
            },
            "role_cluster": {"recap": "classification"},
        },
    }
    base.update(overrides)
    return base


def test_appconfig_typed_access() -> None:
    from straightjacket.engine.config_loader import _parse_config

    config = _parse_config(_full_config_data())
    assert config.ai.providers["local"].type == "openai_compatible"
    assert config.ai.providers["local"].api_key_env == "LOCAL_KEY"
    assert config.ai.clusters["classification"].provider == "local"
    assert config.ai.clusters["classification"].model == "qwen"
    assert config.ai.clusters["classification"].temperature == 0.5


def test_appconfig_strict_on_empty() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    with pytest.raises(KeyError):
        _parse_config({})


def test_cluster_all_fields_accessible() -> None:
    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    data["ai"]["clusters"] = {
        "analytical": {
            "provider": "local",
            "model": "gpt-oss",
            "temperature": 0.3,
            "top_p": 0.95,
            "max_tokens": 4096,
            "max_retries": 2,
            "extra_body": {"foo": "bar"},
        }
    }
    data["ai"]["role_cluster"] = {"recap": "analytical"}
    config = _parse_config(data)
    c = config.ai.clusters["analytical"]
    assert c.model == "gpt-oss"
    assert c.temperature == 0.3
    assert c.top_p == 0.95
    assert c.max_tokens == 4096
    assert c.max_retries == 2
    assert c.extra_body == {"foo": "bar"}


def test_cluster_requires_all_fields() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    data["ai"]["clusters"] = {"creative": {"temperature": 0.9}}
    data["ai"]["role_cluster"] = {"recap": "creative"}
    with pytest.raises(ValueError, match="missing required fields"):
        _parse_config(data)


def test_role_cluster_override() -> None:
    from straightjacket.engine.config_loader import _parse_config

    config = _parse_config(_full_config_data())
    assert config.ai.role_cluster["recap"] == "classification"


def test_cluster_with_undefined_provider_raises() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    data["ai"]["clusters"]["classification"]["provider"] = "elsewhere"
    with pytest.raises(ValueError, match=r"not defined under ai\.providers"):
        _parse_config(data)


def test_cluster_without_provider_raises() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    del data["ai"]["clusters"]["classification"]["provider"]
    with pytest.raises(ValueError, match="missing required fields"):
        _parse_config(data)


def test_cluster_sampling_can_be_explicitly_unset() -> None:
    from straightjacket.engine import config_loader

    data = _full_config_data()
    data["ai"]["clusters"]["classification"]["temperature"] = None
    data["ai"]["clusters"]["classification"]["top_p"] = None
    config = config_loader._parse_config(data)
    cluster = config.ai.clusters["classification"]
    assert (cluster.temperature, cluster.top_p) == (None, None)


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

    from straightjacket.engine.config_loader import PROJECT_ROOT

    env = {key: value for key, value in os.environ.items() if key != "STRAIGHTJACKET_USERS_DIR"}
    expected = str(PROJECT_ROOT / "users")
    assert _users_dirs_in_a_fresh_process(env) == [expected, expected]
