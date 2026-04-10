#!/usr/bin/env python3
"""Tool registry: Python functions → OpenAI tool definitions.

Tools are registered with @register("brain"), @register("director"), or
@register("brain", "director") for shared tools. The registry produces
provider-compatible tool definition lists per role.

Tool functions must have type-hinted parameters and a docstring.
The docstring becomes the tool description. Parameter types map to
JSON schema types (str→string, int→integer, float→number, bool→boolean).
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints
from collections.abc import Callable

from ..logging_util import log

# role → {name → (func, definition)}
_registry: dict[str, dict[str, tuple[Callable, dict]]] = {}


def register(*roles: str) -> Callable:
    """Decorator: register a function as a tool for the given roles."""

    def decorator(func: Callable) -> Callable:
        definition = _build_definition(func)
        for role in roles:
            if role not in _registry:
                _registry[role] = {}
            _registry[role][definition["function"]["name"]] = (func, definition)
        log(f"[Tools] Registered {func.__name__} for {', '.join(roles)}")
        return func

    return decorator


def get_tools(role: str) -> list[dict]:
    """Get tool definitions for a role (OpenAI function calling format)."""
    entries = _registry.get(role, {})
    return [defn for _, defn in entries.values()]


def get_handler(role: str, name: str) -> Callable | None:
    """Get the handler function for a tool by role and name."""
    entries = _registry.get(role, {})
    entry = entries.get(name)
    return entry[0] if entry else None


def list_tools(role: str) -> list[str]:
    """List registered tool names for a role."""
    return list(_registry.get(role, {}).keys())


def clear_registry() -> None:
    """Clear all registrations. Used in tests."""
    _registry.clear()


# ── Schema builder ────────────────────────────────────────────

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _build_definition(func: Callable) -> dict:
    """Build OpenAI function calling tool definition from a Python function."""
    name = func.__name__
    description = (func.__doc__ or "").strip().split("\n")[0]
    if not description:
        raise ValueError(f"Tool {name} must have a docstring")

    hints = get_type_hints(func)
    sig = inspect.signature(func)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Skip non-tool parameters (injected by handler)
        if param_name in ("game", "conn", "db"):
            continue

        param_type = hints.get(param_name, str)
        json_type = _TYPE_MAP.get(param_type, "string")

        prop: dict[str, Any] = {"type": json_type}

        # Extract parameter description from docstring (param: description)
        param_desc = _extract_param_doc(func, param_name)
        if param_desc:
            prop["description"] = param_desc

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


def _extract_param_doc(func: Callable, param_name: str) -> str:
    """Extract a parameter description from the function docstring."""
    doc = func.__doc__ or ""
    for line in doc.split("\n"):
        stripped = line.strip()
        if stripped.startswith(f"{param_name}:"):
            return stripped[len(param_name) + 1 :].strip()
    return ""
