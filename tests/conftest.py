import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


_lm = types.ModuleType("straightjacket.engine.logging_util")
_lm.log = lambda *a, **k: None
sys.modules["straightjacket.engine.logging_util"] = _lm


@pytest.fixture(scope="session", autouse=True)
def _ruleset_answers() -> None:
    from straightjacket.engine.gamemaster.questions import install_answers
    from straightjacket.engine.ruleset import answers

    install_answers(answers)


@pytest.fixture(autouse=True)
def _no_backoff_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ai import provider_base

    monkeypatch.setattr(provider_base, "_time", types.SimpleNamespace(sleep=lambda _: None))


@pytest.fixture(autouse=True)
def _reset_random() -> None:
    import random as _random

    yield
    _random.seed()


def _parse_config(stubbed: bool) -> tuple:
    from straightjacket.engine import engine_loader
    from straightjacket.engine.crafters import config as crafters_config
    from straightjacket.engine.engine_config import parse_engine_yaml
    from straightjacket.engine.gamemaster import config as gamemaster_config
    from straightjacket.engine.ruleset import config as ruleset_config
    from straightjacket.engine.yaml_merge import load_yaml_dir

    engine_data = load_yaml_dir(engine_loader._CONFIG_DIR, missing_dir_hint="")
    gamemaster_data = load_yaml_dir(gamemaster_config._CONFIG_DIR, missing_dir_hint="")
    if stubbed:
        gamemaster_data["story"]["kishotenketsu_probability"] = {"dark_gritty": 0.15}
        engine_data["creativity_seeds"] = ["amber", "glacier", "compass", "obsidian", "cedar"]
    return (
        parse_engine_yaml(engine_data),
        gamemaster_config.parse_gamemaster_yaml(gamemaster_data),
        crafters_config.parse_crafters_yaml(load_yaml_dir(crafters_config._CONFIG_DIR, missing_dir_hint="")),
        ruleset_config.parse_ruleset_yaml(load_yaml_dir(ruleset_config._CONFIG_DIR, missing_dir_hint="")),
    )


@pytest.fixture(scope="session")
def _real_engine():
    return _parse_config(stubbed=False)


@pytest.fixture(scope="session")
def _stub_engine_instance():
    return _parse_config(stubbed=True)


@pytest.fixture
def load_engine(_real_engine) -> None:
    from tests._helpers import install_config

    install_config(_real_engine)


@pytest.fixture
def stub_engine(_stub_engine_instance) -> None:
    from tests._helpers import install_config

    install_config(_stub_engine_instance)


@pytest.fixture
def stub_emotions() -> None:
    from straightjacket.engine import emotions_loader

    emotions_loader._data = {
        "importance": {
            "neutral": 2,
            "curious": 3,
            "angry": 5,
            "conflicted": 6,
            "terrified": 7,
            "betrayed": 9,
            "devastated": 9,
            "transformed": 10,
            "hostile": 5,
            "suspicious": 5,
            "trusting": 5,
            "friendly": 3,
            "reflective": 4,
        },
        "keyword_boosts": {
            7: ["death", "killed", "sacrifice"],
            5: ["secret", "betrayed", "trust"],
            3: ["gift", "helped", "fought"],
        },
    }


@pytest.fixture
def stub_all(stub_engine: None, stub_emotions: None) -> None:
    pass
