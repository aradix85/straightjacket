from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests._rules import SRC_ROOT, Violation, _iter_source_files, _iter_test_files, _load, _rel, _rel_test

if TYPE_CHECKING:
    from pathlib import Path

_PROVIDER_IMPORT_ALLOWED = {
    "engine/ai/provider_anthropic.py",
    "engine/ai/provider_openai.py",
}

_PROVIDER_IMPORT_ALLOWED_TESTS = {
    "test_providers.py",
}

_FORBIDDEN_SDK_MODULES = ("anthropic", "openai")


def _check_no_direct_provider_sdk_imports() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in _PROVIDER_IMPORT_ALLOWED:
            continue
        violations.extend(_scan_provider_sdk(path, rel))
    for path in _iter_test_files():
        rel = _rel_test(path)
        if rel in _PROVIDER_IMPORT_ALLOWED_TESTS:
            continue
        violations.extend(_scan_provider_sdk(path, rel))
    return "DIRECT PROVIDER SDK IMPORT outside adapter", violations


def _scan_provider_sdk(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, _ = _load(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _FORBIDDEN_SDK_MODULES:
                    snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    violations.append(Violation(rel, node.lineno, snippet))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _FORBIDDEN_SDK_MODULES:
            snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            violations.append(Violation(rel, node.lineno, snippet))
    return violations


_ENGINE_SUBPACKAGES = frozenset({"ai", "correction", "crafters", "game", "gamemaster", "ruleset", "setting", "tools"})
_LAYERS = frozenset({"gamemaster", "crafters", "ruleset"})
_CORE_BASE = frozenset(
    {
        "config_loader",
        "emotions_loader",
        "engine_config",
        "engine_config_dataclasses",
        "engine_loader",
        "format_utils",
        "ids",
        "logging_util",
        "models",
        "models_base",
        "models_npc",
        "models_story",
        "prompt_loader",
        "serialization",
        "xml_utils",
        "yaml_merge",
    }
)
_UPPER = frozenset({"correction", "game", "web"})
_LAYER_FORBIDDEN: dict[str, frozenset[str]] = {
    "base": frozenset({"core", "setting", "ai", "tools"}) | _LAYERS | _UPPER,
    "setting": frozenset({"core", "ai", "tools"}) | _LAYERS | _UPPER,
    "gamemaster": frozenset({"core", "ai", "tools", "crafters", "ruleset"}) | _UPPER,
    "crafters": frozenset({"core", "ai", "tools", "ruleset"}) | _UPPER,
    "ruleset": frozenset({"core", "ai", "tools"}) | _UPPER,
    "tools": frozenset({"core", "ai"}) | _UPPER,
    "ai": _UPPER,
    "core": _UPPER,
    "game": frozenset({"correction", "web"}),
    "correction": frozenset({"web"}),
    "web": frozenset(),
    "top": frozenset(),
}


def _layer(parts: list[str]) -> str:
    if parts[:1] == ["web"]:
        return "web"
    if parts[:1] == ["engine"]:
        if len(parts) >= 2 and parts[1] in _ENGINE_SUBPACKAGES:
            return parts[1]
        return "base" if len(parts) >= 2 and parts[1] in _CORE_BASE else "core"
    return "top"


def _import_target(node: ast.ImportFrom) -> list[str] | None:
    module = node.module or ""
    return module.split(".")[1:] if module.startswith("straightjacket.") else None


def _check_import_layers() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        parts = path.relative_to(SRC_ROOT).parts
        own = _layer([*parts[:-1], path.stem])
        _, lines, tree, _ = _load(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _import_target(node)
            if target is None:
                continue
            other = _layer(target)
            if other in _LAYER_FORBIDDEN[own]:
                snippet = lines[node.lineno - 1].strip()
                violations.append(Violation(_rel(path), node.lineno, f"{own} -> {other}: {snippet}"))
    return "IMPORT LAYER violated (dependencies point downward)", violations


_HUB_PACKAGES = frozenset({"correction", "game", "tools"})


def _check_hub_packages_imported_through_init() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        parts = path.relative_to(SRC_ROOT).parts
        _, lines, tree, _ = _load(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _import_target(node)
            if target is None or len(target) < 3 or target[0] != "engine" or target[1] not in _HUB_PACKAGES:
                continue
            if parts[:2] != ("engine", target[1]):
                snippet = lines[node.lineno - 1].strip()
                violations.append(Violation(_rel(path), node.lineno, snippet))
    return "HUB IMPORT: code outside game, tools, or correction imports them through their __init__.py", violations
