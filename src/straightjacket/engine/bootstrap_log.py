#!/usr/bin/env python3
"""Bootstrap logger for modules that load before logging_util is ready.

config_loader, prompt_loader, and emotions_loader all run during import,
before logging_util's handler chain is set up. They need a logger that
won't create circular imports. This module has zero internal dependencies.

Once setup_file_logging() has been called, bootstrap_log transparently
forwards to the real rpg_engine logger instead of print().
"""

import logging as _logging


def bootstrap_log(msg: str, level: str = "info") -> None:
    """Log a message. Uses print() during early init, real logger after setup."""
    logger = _logging.getLogger("rpg_engine")
    if logger.handlers:
        getattr(logger, level, logger.info)(msg)
    else:
        print(msg)
