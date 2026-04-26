import logging as _logging


def bootstrap_log(msg: str, level: str = "info") -> None:
    logger = _logging.getLogger("rpg_engine")
    if logger.handlers:
        getattr(logger, level, logger.info)(msg)
    else:
        print(msg)
