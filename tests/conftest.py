from __future__ import annotations

import logging
import random as _random
import types
from typing import TYPE_CHECKING

import pytest

from straightjacket.engine.ai import provider_base
from straightjacket.engine.gamemaster.questions import install_answers
from straightjacket.engine.ruleset import answers

if TYPE_CHECKING:
    from collections.abc import Iterator

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
