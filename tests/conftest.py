import sys
import types
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


_lm = types.ModuleType("straightjacket.engine.logging_util")
_lm.log = lambda *a, **k: None
_lm.setup_file_logging = lambda: None
_lm.get_logger = lambda component: type(
    "_L",
    (),
    {
        "info": lambda self, *a: None,
        "debug": lambda self, *a: None,
        "warning": lambda self, *a: None,
        "error": lambda self, *a: None,
    },
)()
sys.modules["straightjacket.engine.logging_util"] = _lm


from straightjacket.engine.ai.provider_base import set_backoff_sleep

set_backoff_sleep(lambda _: None)


@pytest.fixture(autouse=True)
def _reset_random() -> None:
    import random as _random

    yield
    _random.seed()


@pytest.fixture(scope="session")
def _real_engine():
    from straightjacket.engine.engine_loader import _ENGINE_DIR
    from straightjacket.engine.engine_config import parse_engine_yaml
    from straightjacket.engine.yaml_merge import load_yaml_dir

    data = load_yaml_dir(_ENGINE_DIR, missing_dir_hint="The engine/ directory ships with the repo.")
    return parse_engine_yaml(data)


@pytest.fixture(scope="session")
def _stub_engine_instance():
    from straightjacket.engine.engine_loader import _ENGINE_DIR
    from straightjacket.engine.engine_config import parse_engine_yaml
    from straightjacket.engine.yaml_merge import load_yaml_dir

    data = load_yaml_dir(_ENGINE_DIR, missing_dir_hint="The engine/ directory ships with the repo.")
    data["story"]["kishotenketsu_probability"] = {"dark_gritty": 0.15}
    data["creativity_seeds"] = ["amber", "glacier", "compass", "obsidian", "cedar"]
    return parse_engine_yaml(data)


@pytest.fixture()
def load_engine(_real_engine) -> None:
    from straightjacket.engine import engine_loader

    engine_loader._eng = _real_engine


@pytest.fixture()
def stub_engine(_stub_engine_instance) -> None:
    from straightjacket.engine import engine_loader

    engine_loader._eng = _stub_engine_instance


@pytest.fixture()
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
        "disposition_map": {
            "hostile": "hostile",
            "neutral": "neutral",
            "friendly": "friendly",
            "wary": "distrustful",
            "curious": "neutral",
            "loyal": "loyal",
        },
    }


@pytest.fixture()
def stub_all(stub_engine: None, stub_emotions: None) -> None:
    pass


def make_genre_constraints(
    forbidden_terms: list[str] | None = None,
    forbidden_concepts: list[str] | None = None,
    genre_test: str = "",
    atmospheric_drift: list[str] | None = None,
    atmospheric_drift_threshold: int = 3,
):
    from straightjacket.engine.datasworn.settings import GenreConstraints

    return GenreConstraints(
        forbidden_terms=forbidden_terms if forbidden_terms is not None else [],
        forbidden_concepts=forbidden_concepts if forbidden_concepts is not None else [],
        genre_test=genre_test,
        atmospheric_drift=atmospheric_drift if atmospheric_drift is not None else [],
        atmospheric_drift_threshold=atmospheric_drift_threshold,
    )
