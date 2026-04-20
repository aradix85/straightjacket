"""Straightjacket logging: console logger setup and log() entry point.

User/save directory management and config load/save live in user_management.py.
"""

import logging
import sys


def setup_file_logging() -> None:
    """Set up console logging. Safe to call multiple times."""
    logger = logging.getLogger("rpg_engine")
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("%(name)s %(message)s"))
    logger.addHandler(ch)


def log(msg: str, level: str = "info") -> None:
    """Log a message via the root engine logger."""
    logger = logging.getLogger("rpg_engine")
    if not logger.handlers:
        setup_file_logging()
    getattr(logger, level, logger.info)(msg)
