from __future__ import annotations

import logging
import random as _random
import types
from typing import TYPE_CHECKING

import pytest

from straightjacket.engine.ai import provider_base
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.questions import install_answers
from straightjacket.engine.ruleset import answers
from straightjacket.engine.ruleset.config import rules
from tests._helpers import install_config

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests._helpers import SettingsSet

logging.getLogger("rpg_engine").addHandler(logging.NullHandler())


@pytest.fixture(scope="session")
def _ruleset_answers() -> None:
    install_answers(answers)


@pytest.fixture
def _no_backoff_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provider_base, "_time", types.SimpleNamespace(sleep=lambda _: None))


@pytest.fixture
def _reset_random() -> Iterator[None]:
    yield
    _random.seed()


@pytest.fixture(scope="session")
def _real_engine() -> SettingsSet:
    return eng(), gm(), crafter(), rules()


@pytest.fixture
def load_engine(_real_engine: SettingsSet) -> None:
    install_config(_real_engine)
