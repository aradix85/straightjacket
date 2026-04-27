def _full_config_data(**overrides: object) -> dict:
    base = {
        "server": {"host": "127.0.0.1", "port": 8081},
        "language": {"narration_language": "English"},
        "ai": {
            "provider": "openai_compatible",
            "api_base": "",
            "api_key_env": "",
            "prompts_dir": "prompts",
            "clusters": {
                "classification": {
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
    assert config.ai.provider == "openai_compatible"
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
