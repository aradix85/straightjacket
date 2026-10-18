import importlib.util
import logging
from pathlib import Path
from types import ModuleType

import pytest

_LOGGING_UTIL = Path(__file__).resolve().parent.parent / "src" / "straightjacket" / "engine" / "logging_util.py"


def _real_logging_util() -> ModuleType:
    spec = importlib.util.spec_from_file_location("real_logging_util", _LOGGING_UTIL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_level_the_logger_does_not_know_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = logging.getLogger("rpg_engine")
    monkeypatch.setattr(logger, "handlers", [logging.NullHandler()])
    with pytest.raises(AttributeError, match="warn_loudly"):
        _real_logging_util().log("message", level="warn_loudly")
