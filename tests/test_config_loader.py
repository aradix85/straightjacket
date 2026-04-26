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
            "model_family": {"qwen": "qwen", "gpt-oss": "gpt_oss"},
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


def test_model_family_field_required() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    del data["ai"]["model_family"]
    with pytest.raises(KeyError):
        _parse_config(data)


def test_model_family_for_model_resolves(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_model

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    assert model_family_for_model("qwen") == "qwen"
    assert model_family_for_model("gpt-oss") == "gpt_oss"


def test_model_family_for_model_raises_on_unknown(monkeypatch) -> None:
    import pytest

    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_model

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    with pytest.raises(ValueError, match="no family mapping"):
        model_family_for_model("some-other-model")


def test_model_family_for_role_chains(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_role

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)

    assert model_family_for_role("recap") == "qwen"


def test_narrator_model_family_convenience(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, narrator_model_family

    data = _full_config_data()
    data["ai"]["clusters"]["narrator"] = {
        "model": "gpt-oss",
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 8192,
        "max_retries": 3,
    }
    data["ai"]["role_cluster"]["narrator"] = "narrator"
    config = _parse_config(data)
    monkeypatch.setattr(config_loader, "_cfg", config)
    assert narrator_model_family() == "gpt_oss"


def test_model_family_for_role_raises_on_unmapped_role(monkeypatch) -> None:
    import pytest

    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_role

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    with pytest.raises(ValueError, match="no cluster assignment"):
        model_family_for_role("nonexistent_role")
