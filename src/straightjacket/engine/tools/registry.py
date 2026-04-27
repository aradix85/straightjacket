from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, get_type_hints

from ..engine_loader import eng
from ..logging_util import log


_registry: dict[str, dict[str, tuple[Callable, dict]]] = {}


def register(*roles: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        definition = _build_definition_from_yaml(func)
        for role in roles:
            if role not in _registry:
                _registry[role] = {}
            _registry[role][definition["function"]["name"]] = (func, definition)
        log(f"[Tools] Registered {func.__name__} for {', '.join(roles)}")
        return func

    return decorator


def register_test_tool(*roles: str, description: str, params: Mapping[str, str] = MappingProxyType({})) -> Callable:
    def decorator(func: Callable) -> Callable:
        definition = _build_definition_from_overrides(func, description=description, param_docs=params)
        for role in roles:
            if role not in _registry:
                _registry[role] = {}
            _registry[role][definition["function"]["name"]] = (func, definition)
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


def _build_definition_from_yaml(func: Callable) -> dict:
    descriptions = eng().get_raw("tool_descriptions")
    entry = descriptions[func.__name__]
    return _assemble_definition(func, description=entry["description"], param_docs=entry["params"])


def _build_definition_from_overrides(func: Callable, *, description: str, param_docs: Mapping[str, str]) -> dict:
    return _assemble_definition(func, description=description, param_docs=param_docs)


def _assemble_definition(func: Callable, *, description: str, param_docs: Mapping[str, str]) -> dict:
    name = func.__name__
    hints = get_type_hints(func)
    sig = inspect.signature(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("game", "conn", "db"):
            continue

        if param_name not in hints:
            raise TypeError(f"Tool {name!r} parameter {param_name!r} has no type hint")
        param_type = hints[param_name]
        if param_type not in _TYPE_MAP:
            raise TypeError(f"Tool {name!r} parameter {param_name!r} has unsupported type {param_type!r}")
        json_type = _TYPE_MAP[param_type]

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
