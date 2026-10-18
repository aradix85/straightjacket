import logging
import sys


def log(msg: str, level: str = "info") -> None:
    logger = logging.getLogger("rpg_engine")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
        logger.addHandler(handler)
    getattr(logger, level)(msg)
