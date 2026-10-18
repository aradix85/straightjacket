from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState

Tool = Callable[[GameState], dict[str, Any]]

_registry: dict[str, tuple[Tool, dict[str, Any]]] = {}


def register(func: Tool) -> Tool:
    name = func.__name__
    definition = {
        "type": "function",
        "function": {
            "name": name,
            "description": eng().get_raw("tool_descriptions")[name],
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }
    _registry[name] = (func, definition)
    log(f"[Tools] Registered {name}")
    return func


def get_tools() -> list[dict[str, Any]]:
    return [definition for _, definition in _registry.values()]


def get_handler(name: str) -> Tool | None:
    entry = _registry.get(name)
    return entry[0] if entry else None
