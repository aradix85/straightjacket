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


@pytest.fixture(scope="session")
def _real_engine() -> tuple:
    from straightjacket.engine.crafters.config import crafter
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.gamemaster.config import gm
    from straightjacket.engine.ruleset.config import rules

    return eng(), gm(), crafter(), rules()


@pytest.fixture
def load_engine(_real_engine) -> None:
    from tests._helpers import install_config

    install_config(_real_engine)
