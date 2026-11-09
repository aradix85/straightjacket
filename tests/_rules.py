from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "straightjacket"
TESTS_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    snippet: str

    @override
    def __str__(self) -> str:
        return f"  {self.file}:{self.line}  {self.snippet}"


def _iter_source_files() -> Iterator[Path]:
    yield from SRC_ROOT.rglob("*.py")


def _iter_test_files() -> Iterator[Path]:
    for p in TESTS_ROOT.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        yield p


def _rel(path: Path) -> str:
    return path.relative_to(SRC_ROOT).as_posix()


def _rel_test(path: Path) -> str:
    return path.relative_to(TESTS_ROOT).as_posix()


_FILE_CACHE: dict[Path, tuple[str, list[str], ast.AST, dict[int, ast.AST]]] = {}


def _load(path: Path) -> tuple[str, list[str], ast.AST, dict[int, ast.AST]]:
    cached = _FILE_CACHE.get(path)
    if cached is not None:
        return cached
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    parents = _build_parent_map(tree)
    cached = (text, lines, tree, parents)
    _FILE_CACHE[path] = cached
    return cached


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _run_scan_src_and_tests(scan_fn: Callable[[Path, str], list[Violation]]) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        violations.extend(scan_fn(path, _rel(path)))
    for path in _iter_test_files():
        violations.extend(scan_fn(path, _rel_test(path)))
    return violations


def _defines(path: Path, name: str) -> bool:
    if not path.exists():
        return False
    for node in ast.walk(_load(path)[2]):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False
