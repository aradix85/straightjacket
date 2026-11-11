from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import yaml

from tests._rules import REPO_ROOT, SRC_ROOT, TESTS_ROOT, Violation, _defines, _iter_source_files, _load, _rel
from tests._rules_code import (
    _AI_CALL_CARVE_OUT_FILES,
    _AI_CALL_CARVE_OUT_TESTS,
    _CONFIG_BINDING_FILES,
    _EXTERNAL_STRUCTURE_DATACLASSES,
    _HARDCODED_MODEL_NAME_TEST_WHITELIST,
    _catches_broad,
    _scan_model_names,
)
from tests._rules_imports import (
    _CORE_BASE,
    _PROVIDER_IMPORT_ALLOWED,
    _PROVIDER_IMPORT_ALLOWED_TESTS,
    _scan_provider_sdk,
)

if TYPE_CHECKING:
    from pathlib import Path

ENGINE_YAML_ROOTS = tuple(REPO_ROOT / name for name in ("engine", "gamemaster", "crafters", "ruleset"))
PROMPTS_YAML_ROOT = REPO_ROOT / "prompts"

_ORPHAN_SYMBOL_CARVE_OUT: set[tuple[str, str]] = {
    ("check_configured_models", "engine/ai/api_client.py"),
    ("roll_character_traits", "engine/crafters/character_traits.py"),
    ("dispatch_meta", "engine/crafters/meta_plot_points.py"),
    ("lookup_characters_template", "engine/crafters/adventure_crafter.py"),
}


def _collect_public_symbols() -> dict[tuple[str, Path], None]:
    defs: dict[tuple[str, Path], None] = {}
    for path in _iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            defs[node.name, path] = None
    return defs


def _names_a_node_uses(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return [node.id]
    if isinstance(node, ast.ImportFrom):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ClassDef) and any(isinstance(b, ast.Name) and b.id == "Protocol" for b in node.bases):
        return [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
    match node:
        case ast.Call(func=ast.Name(id="getattr"), args=[_, ast.Constant(value=str() as attribute), *_]):
            return [attribute]
        case _:
            return []


def _collect_src_uses() -> dict[Path, set[str]]:
    uses: dict[Path, set[str]] = {}
    for path in _iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        uses[path] = {name for node in ast.walk(tree) for name in _names_a_node_uses(node)}
    return uses


def _orphan_public_symbols() -> set[tuple[str, str]]:
    defs = _collect_public_symbols()
    uses = _collect_src_uses()
    orphans: set[tuple[str, str]] = set()
    for name, defining_file in defs:
        external_use = any(name in refs for f, refs in uses.items() if f != defining_file)
        if external_use:
            continue
        intra_uses = sum(
            1 for n in ast.walk(ast.parse(defining_file.read_text(encoding="utf-8"))) if _is_load_ref(n, name)
        )
        if intra_uses > 0:
            continue
        orphans.add((name, _rel(defining_file)))
    return orphans


def _check_no_orphan_public_symbols() -> tuple[str, list[Violation]]:
    violations = [
        Violation(rel, 0, f"public symbol {name!r} has no consumer")
        for name, rel in sorted(_orphan_public_symbols() - _ORPHAN_SYMBOL_CARVE_OUT)
    ]
    return "orphan public symbol (defined but never used)", violations


def _is_load_ref(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name:
        return True
    if isinstance(node, ast.ImportFrom):
        return any(alias.name == name for alias in node.names)
    return False


def _check_no_orphan_yaml_keys() -> tuple[str, list[Violation]]:
    py_text = "\n".join(
        line
        for p in _iter_source_files()
        for line in p.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith(("from ", "import "))
    )
    violations: list[Violation] = []
    for yfile in sorted(y for root in ENGINE_YAML_ROOTS for y in root.glob("*.yaml")):
        try:
            data = yaml.safe_load(yfile.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        for key in data:
            if not isinstance(key, str):
                continue
            literal_patterns = [f'"{key}"', f"'{key}'", f".{key}", f"['{key}']", f'["{key}"]']
            if any(p in py_text for p in literal_patterns):
                continue
            violations.append(
                Violation(yfile.relative_to(REPO_ROOT).as_posix(), 0, f"top-level key {key!r} has no Python reader")
            )
    return "orphan config yaml top-level key", violations


def _has_broad_except(path: Path) -> bool:
    return any(
        isinstance(n, ast.ExceptHandler) and n.type is not None and _catches_broad(n.type)
        for n in ast.walk(_load(path)[2])
    )


def _stale_broad_except_carve_outs() -> list[Violation]:
    violations: list[Violation] = []
    for rel in sorted(_AI_CALL_CARVE_OUT_FILES):
        path = SRC_ROOT / rel
        if not path.exists():
            violations.append(Violation(rel, 0, "AI-call carve-out file does not exist"))
        elif not _has_broad_except(path):
            violations.append(Violation(rel, 0, "AI-call carve-out file has no broad except to carve out"))
    for rel in sorted(_AI_CALL_CARVE_OUT_TESTS):
        path = TESTS_ROOT / rel
        if not path.exists() or not _has_broad_except(path):
            violations.append(Violation(rel, 0, "test carve-out file has no broad except to carve out"))
    return violations


def _stale_scan_allowances() -> list[Violation]:
    violations: list[Violation] = []
    for rel in sorted(_HARDCODED_MODEL_NAME_TEST_WHITELIST):
        path = TESTS_ROOT / rel
        if not path.exists() or not _scan_model_names(path, rel):
            violations.append(Violation(rel, 0, "model-name whitelist file names no model"))
    for rel in sorted(_PROVIDER_IMPORT_ALLOWED):
        path = SRC_ROOT / rel
        if not path.exists() or not _scan_provider_sdk(path, rel):
            violations.append(Violation(rel, 0, "provider-import allowance for a file that imports no provider SDK"))
    for rel in sorted(_PROVIDER_IMPORT_ALLOWED_TESTS):
        path = TESTS_ROOT / rel
        if not path.exists() or not _scan_provider_sdk(path, rel):
            violations.append(Violation(rel, 0, "provider-import allowance for a test that imports no provider SDK"))
    return violations


def _missing_listed_files() -> list[Violation]:
    return [
        *(
            Violation(rel, 0, "config binding file does not exist")
            for rel in sorted(_CONFIG_BINDING_FILES)
            if not (SRC_ROOT / rel).exists()
        ),
        *(
            Violation(f"engine/{stem}.py", 0, "import-layer base file does not exist")
            for stem in sorted(_CORE_BASE)
            if not (SRC_ROOT / "engine" / f"{stem}.py").exists()
        ),
    ]


def _stale_symbol_entries() -> list[Violation]:
    violations: list[Violation] = []
    for name, rel in sorted(_ORPHAN_SYMBOL_CARVE_OUT - _orphan_public_symbols()):
        violations.append(Violation(rel, 0, f"orphan carve-out {name!r} is not an orphan, or not defined there"))
    for rel, name in sorted(_EXTERNAL_STRUCTURE_DATACLASSES):
        if not _defines(SRC_ROOT / rel, name):
            violations.append(Violation(rel, 0, f"external-structure dataclass {name!r} is not defined there"))
    return violations


def _check_no_stale_carve_out_entries() -> tuple[str, list[Violation]]:
    return "STALE carve-out or whitelist entry", [
        *_stale_broad_except_carve_outs(),
        *_stale_scan_allowances(),
        *_missing_listed_files(),
        *_stale_symbol_entries(),
    ]


def _check_no_orphan_prompt_keys() -> tuple[str, list[Violation]]:
    src_text = "\n".join(_load(p)[0] for p in _iter_source_files())
    violations: list[Violation] = []
    for yfile in sorted(PROMPTS_YAML_ROOT.glob("*.yaml")):
        data = yaml.safe_load(yfile.read_text(encoding="utf-8"))
        for key in data:
            if f'"{key}"' in src_text or f"'{key}'" in src_text:
                continue
            violations.append(Violation(f"prompts/{yfile.name}", 0, f"prompt key {key!r} has no reader in src"))
    return "orphan prompt key", violations
