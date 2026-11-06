import pytest

from straightjacket.engine import logging_util


def test_a_level_the_logger_does_not_know_raises() -> None:
    with pytest.raises(AttributeError, match="warn_loudly"):
        logging_util.log("message", level="warn_loudly")
