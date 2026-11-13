from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import GameState

Tool = Callable[[GameState], dict[str, object]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, object]


_registry: dict[str, tuple[Tool, ToolDefinition]] = {}


def register(func: Tool) -> Tool:
    name = func.__name__
    definition = ToolDefinition(
        name=name,
        description=eng().tool_descriptions[name],
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    )
    _registry[name] = (func, definition)
    log(f"[Tools] Registered {name}")
    return func


def get_tools() -> list[ToolDefinition]:
    return [definition for _, definition in _registry.values()]


def get_handler(name: str) -> Tool | None:
    entry = _registry.get(name)
    return entry[0] if entry else None
