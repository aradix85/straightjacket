from __future__ import annotations

from typing import Any
import inspect
import json

from ..logging_util import log
from ..models import GameState
from .registry import get_handler


def _unknown_arguments(handler: Any, arguments: dict[str, Any]) -> list[str]:
    params = inspect.signature(handler).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return []
    return sorted(key for key in arguments if key not in params or key == "game")


def execute_tool_call(role: str, tool_call: dict[str, Any], game: GameState) -> str:
    name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})

    handler = get_handler(role, name)
    if handler is None:
        log(f"[Tools] Unknown tool: {name} (role={role})", level="warning")
        return json.dumps({"error": f"unknown tool: {name}"})

    unknown = _unknown_arguments(handler, arguments)
    if unknown:
        log(f"[Tools] {name}: ignored arguments it does not take: {', '.join(unknown)}", level="warning")
        arguments = {key: value for key, value in arguments.items() if key not in unknown}

    try:
        result = handler(game=game, **arguments)
        if isinstance(result, dict):
            if unknown:
                result = {**result, "ignored_arguments": unknown}
            return json.dumps(result, ensure_ascii=False)
        return str(result)
    except Exception as e:
        log(f"[Tools] {name} failed: {e}", level="warning")
        return json.dumps({"error": f"{name} failed: {e}"})
