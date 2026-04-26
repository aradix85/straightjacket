from __future__ import annotations

import inspect
from typing import Any, get_type_hints
from collections.abc import Callable

from ..engine_loader import eng
from ..logging_util import log


_registry: dict[str, dict[str, tuple[Callable, dict]]] = {}


def register(*roles: str, description: str | None = None, params: dict[str, str] | None = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        definition = _build_definition(func, override_description=description, override_params=params)
        for role in roles:
            if role not in _registry:
                _registry[role] = {}
            _registry[role][definition["function"]["name"]] = (func, definition)
        log(f"[Tools] Registered {func.__name__} for {', '.join(roles)}")
        return func

    return decorator


def get_tools(role: str) -> list[dict]:
    entries = _registry.get(role, {})
    return [defn for _, defn in entries.values()]


def get_handler(role: str, name: str) -> Callable | None:
    entries = _registry.get(role, {})
    entry = entries.get(name)
    return entry[0] if entry else None


def list_tools(role: str) -> list[str]:
    return list(_registry.get(role, {}).keys())


def clear_registry() -> None:
    _registry.clear()


_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _build_definition(
    func: Callable,
    *,
    override_description: str | None = None,
    override_params: dict[str, str] | None = None,
) -> dict:
    name = func.__name__
    if override_description is not None:
        description = override_description
        param_docs = override_params or {}
    else:
        descriptions = eng().get_raw("tool_descriptions")
        entry = descriptions[name]
        description = entry["description"]
        param_docs = entry.get("params", {})

    hints = get_type_hints(func)
    sig = inspect.signature(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("game", "conn", "db"):
            continue

        param_type = hints.get(param_name, str)
        json_type = _TYPE_MAP.get(param_type, "string")

        prop: dict[str, Any] = {"type": json_type}
        if param_name in param_docs:
            prop["description"] = param_docs[param_name]

        properties[param_name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
