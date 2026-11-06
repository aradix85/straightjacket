import logging
import sys

_CONSOLE = logging.getLogger("elvira")


def show_on_console() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _CONSOLE.addHandler(handler)
    _CONSOLE.setLevel(logging.INFO)
    _CONSOLE.propagate = False


def say(text: str = "") -> None:
    _CONSOLE.info(text)
