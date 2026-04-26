import logging
import sys


def setup_file_logging() -> None:
    logger = logging.getLogger("rpg_engine")
    if logger.handlers:
        return
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("%(name)s %(message)s"))
    logger.addHandler(ch)


def log(msg: str, level: str = "info") -> None:
    logger = logging.getLogger("rpg_engine")
    if not logger.handlers:
        setup_file_logging()
    getattr(logger, level, logger.info)(msg)
