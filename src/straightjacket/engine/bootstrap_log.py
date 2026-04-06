#!/usr/bin/env python3
"""Bootstrap logger for modules that load before logging_util is ready.

config_loader, prompt_loader, and emotions_loader all run during import,
before logging_util's handler chain is set up. They need a logger that
won't create circular imports. This module has zero internal dependencies.
"""


def bootstrap_log(msg: str, level: str = "info") -> None:
    """Print-based logger for early initialization. No dependencies."""
    print(msg)
