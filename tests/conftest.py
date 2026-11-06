from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests._helpers import SettingsSet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class _SilentLogging(types.ModuleType):
    @staticmethod
    def log(*_args: object, **_kwargs: object) -> None:
        return None


sys.modules["straightjacket.engine.logging_util"] = _SilentLogging("straightjacket.engine.logging_util")


@pytest.fixture(scope="session")
def _ruleset_answers() -> None:
    from straightjacket.engine.gamemaster.questions import install_answers
    from straightjacket.engine.ruleset import answers

    install_answers(answers)


@pytest.fixture
def _no_backoff_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.ai import provider_base

    monkeypatch.setattr(provider_base, "_time", types.SimpleNamespace(sleep=lambda _: None))


@pytest.fixture
def _reset_random() -> Iterator[None]:
    import random as _random

    yield
    _random.seed()


@pytest.fixture(scope="session")
def _real_engine() -> SettingsSet:
    from straightjacket.engine.crafters.config import crafter
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.gamemaster.config import gm
    from straightjacket.engine.ruleset.config import rules

    return eng(), gm(), crafter(), rules()


@pytest.fixture
def load_engine(_real_engine: SettingsSet) -> None:
    from tests._helpers import install_config

    install_config(_real_engine)
