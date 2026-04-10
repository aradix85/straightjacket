#!/usr/bin/env python3
"""Straightjacket tools package — tool calling infrastructure.

Public API:
    register(...)           — decorator to register a tool function
    get_tools(role)         — tool definitions for a role
    get_handler(role, name) — handler function for a specific tool
    execute_tool_call(...)  — execute a single tool call
    run_tool_loop(...)      — iterative tool-call loop
"""

# Import builtins to trigger @register decorators
from . import builtins as _builtins  # noqa: F401
from .handler import execute_tool_call, run_tool_loop
from .registry import clear_registry, get_handler, get_tools, list_tools, register

__all__ = [
    "clear_registry",
    "execute_tool_call",
    "get_handler",
    "get_tools",
    "list_tools",
    "register",
    "run_tool_loop",
]
