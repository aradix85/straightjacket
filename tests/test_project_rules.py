from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "straightjacket"
TESTS_ROOT = Path(__file__).resolve().parent
ENGINE_YAML_ROOT = REPO_ROOT / "engine"
PROMPTS_YAML_ROOT = REPO_ROOT / "prompts"


_AI_CALL_CARVE_OUT_FILES = {
    "engine/ai/brain.py",
    "engine/ai/narrator.py",
    "engine/ai/recap.py",
    "engine/ai/chapter_summary.py",
    "engine/ai/blueprint_voicing.py",
    "engine/ai/provider_base.py",
    "engine/correction/analysis.py",
    "engine/director.py",
    "engine/game/director_runner.py",
    "engine/tools/handler.py",
    "web/handlers.py",
    "web/server.py",
}


_AI_CALL_CARVE_OUT_TESTS = {
    "test_integration.py",
    "elvira/elvira_bot/creation.py",
    "elvira/elvira_bot/runner.py",
    "elvira/elvira_bot/invariants.py",
    "elvira/elvira_bot/ws_runner.py",
}


_HARDCODED_MODEL_NAME_TEST_WHITELIST = {
    "test_config_loader.py",
    "test_project_rules.py",
}


_COMPLEXITY_TEST_WHITELIST = {
    ("elvira/elvira_bot/runner.py", "run_session"),
    ("elvira/elvira_bot/models.py", "to_compact_dict"),
    ("elvira/elvira_bot/ws_runner.py", "run_ws_session"),
}


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    snippet: str

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


def _format_report(category: str, violations: list[Violation]) -> str:
    header = f"{category}: {len(violations)} violation(s)\n"
    body = "\n".join(str(v) for v in violations)
    return header + body


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _ancestors(node: ast.AST, parents: dict[int, ast.AST]) -> Iterator[ast.AST]:
    cur = parents.get(id(node))
    while cur is not None:
        yield cur
        cur = parents.get(id(cur))


def _inside_fstring_or_logcall(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    for anc in _ancestors(node, parents):
        if isinstance(anc, ast.JoinedStr):
            return True
        if isinstance(anc, ast.Call):
            func = anc.func
            if isinstance(func, ast.Name) and func.id in {"log", "print"}:
                return True
            if isinstance(func, ast.Attribute) and func.attr in {
                "debug",
                "info",
                "warning",
                "error",
                "critical",
                "log",
                "exception",
            }:
                return True
    return False


def _inside_docstring(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    for anc in _ancestors(node, parents):
        if isinstance(anc, ast.Expr):
            doc_parent = parents.get(id(anc))
            if doc_parent is None:
                continue
            if not isinstance(
                doc_parent,
                ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
            ):
                continue
            body = getattr(doc_parent, "body", None)
            if not body:
                continue
            if body[0] is anc:
                return True
    return False


def _inside_arithmetic(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    parent = parents.get(id(node))
    if isinstance(parent, ast.BinOp):
        return True
    if isinstance(parent, ast.Call):
        func = parent.func
        if isinstance(func, ast.Attribute) and func.attr in {
            "sqrt",
            "log",
            "log2",
            "log10",
            "exp",
            "floor",
            "ceil",
            "trunc",
            "abs",
        }:
            return True
    return False


_NEUTRAL_CONSTANTS: tuple[object, ...] = (None, 0, "", False)


def _is_neutral_default(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and node.value in _NEUTRAL_CONSTANTS:
        return True
    if isinstance(node, ast.List) and not node.elts:
        return True
    if isinstance(node, ast.Dict) and not node.keys:
        return True
    if isinstance(node, ast.Tuple) and not node.elts:
        return True
    return bool(isinstance(node, ast.Set) and not node.elts)


def _run_scan_src_and_tests(scan_fn, *args) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        violations.extend(scan_fn(path, _rel(path), *args))
    for path in _iter_test_files():
        violations.extend(scan_fn(path, _rel_test(path), *args))
    return violations


def _check_no_domain_default_in_dict_get() -> tuple[str, list[Violation]]:
    return "DOMAIN DEFAULT in .get()", _run_scan_src_and_tests(_scan_dict_get)


def _scan_dict_get(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, parents = _load(path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        if len(node.args) != 2:
            continue
        key_arg = node.args[0]
        if not (isinstance(key_arg, ast.Constant) and isinstance(key_arg.value, str)):
            continue
        default_arg = node.args[1]
        if _is_neutral_default(default_arg):
            continue
        if not isinstance(default_arg, ast.Constant):
            continue
        if _inside_fstring_or_logcall(node, parents):
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, snippet))
    return violations


def _check_no_or_literal_fallback_on_lookups() -> tuple[str, list[Violation]]:
    return "`X or literal` FALLBACK on lookup", _run_scan_src_and_tests(_scan_or_fallback)


def _scan_or_fallback(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, parents = _load(path)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        if len(node.values) != 2:
            continue
        left, right = node.values
        if not isinstance(left, ast.Call | ast.Subscript | ast.Attribute):
            continue
        if not isinstance(right, ast.Constant):
            continue
        val = right.value
        if val in _NEUTRAL_CONSTANTS:
            continue
        if isinstance(val, int | float) and _inside_arithmetic(node, parents):
            continue
        if _inside_fstring_or_logcall(node, parents):
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, snippet))
    return violations


def _is_dataclass_decorator(decorator: ast.expr) -> bool:
    if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
        return True
    if isinstance(decorator, ast.Attribute) and decorator.attr == "dataclass":
        return True
    if isinstance(decorator, ast.Call):
        return _is_dataclass_decorator(decorator.func)
    return False


def _has_default(stmt: ast.AnnAssign) -> bool:
    return stmt.value is not None


_CONFIG_BINDING_FILES = ("engine_config.py", "engine_config_dataclasses.py")


def _check_no_dataclass_defaults_in_config_binding() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for fname in _CONFIG_BINDING_FILES:
        path = SRC_ROOT / "engine" / fname
        if not path.exists():
            raise AssertionError(f"expected config binding at {path}")
        violations.extend(_scan_dataclass_defaults(path))
    return "DATACLASS DEFAULT in config binding", violations


def _scan_dataclass_defaults(path: Path) -> list[Violation]:
    _, lines, tree, _ = _load(path)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_is_dataclass_decorator(d) for d in node.decorator_list):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not _has_default(stmt):
                continue
            field_name = stmt.target.id if isinstance(stmt.target, ast.Name) else "?"
            if field_name.startswith("_"):
                continue
            snippet = lines[stmt.lineno - 1].strip() if stmt.lineno <= len(lines) else ""
            violations.append(Violation(_rel(path), stmt.lineno, f"{node.name}.{field_name}: {snippet}"))
    return violations


def _check_broad_except_inside_carve_out_only() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        violations.extend(_scan_broad_except(path, _rel(path), _AI_CALL_CARVE_OUT_FILES))
    for path in _iter_test_files():
        violations.extend(_scan_broad_except(path, _rel_test(path), _AI_CALL_CARVE_OUT_TESTS))
    return "BROAD except/catch", violations


_BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})


def _exception_names(node: ast.expr) -> list[str]:
    elts = node.elts if isinstance(node, ast.Tuple) else [node]
    names: list[str] = []
    for elt in elts:
        if isinstance(elt, ast.Name):
            names.append(elt.id)
        elif isinstance(elt, ast.Attribute):
            names.append(elt.attr)
    return names


def _catches_broad(node: ast.expr) -> bool:
    return any(name in _BROAD_EXCEPTIONS for name in _exception_names(node))


def _is_broad_suppress(node: ast.Call) -> bool:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    return name == "suppress" and any(_catches_broad(arg) for arg in node.args)


def _scan_broad_except(path: Path, rel: str, carve_out: set[str]) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, _ = _load(path)
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)
        snippet = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            violations.append(Violation(rel, lineno, f"bare except: {snippet}"))
        elif rel in carve_out:
            continue
        elif isinstance(node, ast.ExceptHandler) and _catches_broad(node.type):
            violations.append(Violation(rel, lineno, f"broad except outside carve-out: {snippet}"))
        elif isinstance(node, ast.Call) and _is_broad_suppress(node):
            violations.append(Violation(rel, lineno, f"broad suppress() outside carve-out: {snippet}"))
    return violations


_COMMENT_LINE = re.compile(r"^\s*#")


def _module_has_docstring(tree: ast.AST) -> int:
    if not isinstance(tree, ast.Module) or not tree.body:
        return 0
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.lineno
    return 0


def _docstring_lines(tree: ast.AST) -> list[int]:
    out: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not isinstance(first, ast.Expr):
            continue
        v = first.value
        if not isinstance(v, ast.Constant) or not isinstance(v.value, str):
            continue
        out.append(first.lineno)
    return out


def _check_no_python_comments_or_docstrings() -> tuple[str, list[Violation]]:
    return "PYTHON COMMENT or DOCSTRING", _run_scan_src_and_tests(_scan_comments_docstrings)


def _scan_comments_docstrings(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, _ = _load(path)
    for i, line in enumerate(lines, start=1):
        if _COMMENT_LINE.match(line):
            violations.append(Violation(rel, i, f"# comment: {line.strip()}"))
    for lineno in _docstring_lines(tree):
        snippet = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
        violations.append(Violation(rel, lineno, f"docstring: {snippet[:60]}"))
    return violations


_NON_PROJECT_DIRS = frozenset({".github", ".git", "venv", ".venv", "node_modules", "build", "dist"})


def _check_no_yaml_comments() -> tuple[str, list[Violation]]:
    yaml_root = SRC_ROOT.parent.parent
    violations: list[Violation] = []
    for path in yaml_root.rglob("*.yaml"):
        rel_parts = path.relative_to(yaml_root)
        if rel_parts.parts and rel_parts.parts[0] in _NON_PROJECT_DIRS:
            continue
        if path.name == ".pre-commit-config.yaml":
            continue
        rel = rel_parts.as_posix()
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if _COMMENT_LINE.match(line):
                violations.append(Violation(rel, i, line.strip()))
    return "YAML COMMENT", violations


_INLINE_IMPORT_WHITELIST: set[tuple[str, str]] = {
    ("engine/models.py", "restore"),
    ("engine/npc/lifecycle.py", "_npc_eligible_for_desc_match"),
    ("engine/ai/api_client.py", "get_provider"),
    ("engine/ai/provider_base.py", "create_with_retry"),
    ("engine/mechanics/threats.py", "resolve_full_menace"),
    ("engine/mechanics/fate.py", "resolve_fate"),
    ("engine/mechanics/engine_memories.py", "generate_engine_memories"),
    ("engine/mechanics/world.py", "update_chaos_factor"),
    ("engine/mechanics/world.py", "apply_brain_location_time"),
    ("engine/mechanics/clock_consequences.py", "_try_complete_linked_track"),
}


def _check_inline_imports_only_in_whitelist() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        _, lines, tree, _ = _load(path)

        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(func):
                if node is func:
                    continue
                if not isinstance(node, ast.Import | ast.ImportFrom):
                    continue
                if (rel, func.name) in _INLINE_IMPORT_WHITELIST:
                    continue
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                violations.append(Violation(rel, node.lineno, f"{snippet}  [in {func.name}]"))
    return "INLINE IMPORT outside whitelist", violations


_MODELS_FILES = ("models.py", "models_base.py", "models_npc.py", "models_story.py")


def _class_inherits_mixin(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "SerializableMixin":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "SerializableMixin":
            return True
    return False


def _class_opts_out_serialization(node: ast.ClassDef) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "_NOT_SERIALIZED"
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is True
                ):
                    return True
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "_NOT_SERIALIZED"
            and stmt.value is not None
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is True
        ):
            return True
    return False


def _check_dataclasses_in_models_inherit_serializablemixin() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for fname in _MODELS_FILES:
        path = SRC_ROOT / "engine" / fname
        if not path.exists():
            continue
        _, lines, tree, _ = _load(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(_is_dataclass_decorator(d) for d in node.decorator_list):
                continue
            if _class_inherits_mixin(node):
                continue
            if _class_opts_out_serialization(node):
                continue
            snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            violations.append(Violation(_rel(path), node.lineno, f"{node.name}: {snippet}"))

    return "DATACLASS without SerializableMixin", violations


_PROVIDER_IMPORT_ALLOWED = {
    "engine/ai/provider_anthropic.py",
    "engine/ai/provider_openai.py",
    "engine/ai/api_client.py",
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
        violations.extend(_scan_provider_sdk(path, _rel_test(path)))
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


_MODEL_NAME_PATTERNS = re.compile(
    r"(qwen[-\d]|gpt-oss|gpt-\d|gpt-4|claude-\d|claude-opus|claude-sonnet|claude-haiku|glm-?\d|zai-|deepseek|kimi-|llama-?\d|mistral-)",
    re.IGNORECASE,
)


def _check_no_hardcoded_model_names_in_engine() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in {"engine/config_loader.py"}:
            continue
        violations.extend(_scan_model_names(path, rel))
    for path in _iter_test_files():
        rel = _rel_test(path)
        if rel in _HARDCODED_MODEL_NAME_TEST_WHITELIST:
            continue
        violations.extend(_scan_model_names(path, rel))

    return "HARDCODED MODEL NAME in engine code", violations


def _scan_model_names(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, parents = _load(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if not _MODEL_NAME_PATTERNS.search(node.value):
            continue
        if _inside_docstring(node, parents):
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, snippet))
    return violations


_COMPLEXITY_CEILING = 20


def _check_no_function_exceeds_complexity_ceiling() -> tuple[str, list[Violation]]:
    from radon.complexity import cc_visit

    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        violations.extend(_scan_complexity(path, rel, cc_visit, set()))
    for path in _iter_test_files():
        rel = _rel_test(path)
        violations.extend(_scan_complexity(path, rel, cc_visit, _COMPLEXITY_TEST_WHITELIST))

    return f"CYCLOMATIC COMPLEXITY above {_COMPLEXITY_CEILING} (decompose into sub-functions)", violations


def _scan_complexity(path: Path, rel: str, cc_visit, whitelist: set[tuple[str, str]]) -> list[Violation]:
    violations: list[Violation] = []
    try:
        text, _, _, _ = _load(path)
        blocks = cc_visit(text)
    except SyntaxError:
        return violations
    for block in blocks:
        if block.complexity <= _COMPLEXITY_CEILING:
            continue
        if (rel, block.name) in whitelist:
            continue
        snippet = f"{block.name} — complexity {block.complexity}"
        violations.append(Violation(rel, block.lineno, snippet))
    return violations


def _is_empty_collection(node: ast.expr) -> bool:
    if isinstance(node, ast.List) and not node.elts:
        return True
    if isinstance(node, ast.Dict) and not node.keys:
        return True
    if isinstance(node, ast.Tuple) and not node.elts:
        return True
    if isinstance(node, ast.Set) and not node.elts:
        return True
    return bool(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("list", "dict", "set", "tuple")
        and not node.args
        and not node.keywords
    )


def _check_no_name_or_empty_collection_fallback() -> tuple[str, list[Violation]]:
    return "`name or empty-collection` FALLBACK", _run_scan_src_and_tests(_scan_name_or_empty_collection)


def _scan_name_or_empty_collection(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, parents = _load(path)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        if len(node.values) != 2:
            continue
        left, right = node.values
        if not isinstance(left, ast.Name):
            continue
        if not _is_empty_collection(right):
            continue
        if _inside_fstring_or_logcall(node, parents):
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, snippet))
    return violations


def _is_optional_collection_annotation(node: ast.expr) -> bool:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = node.left, node.right
        none_on_right = isinstance(right, ast.Constant) and right.value is None
        none_on_left = isinstance(left, ast.Constant) and left.value is None
        other = left if none_on_right else right if none_on_left else None
        if other is None:
            return False
        return _is_collection_annotation(other)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Optional":
        return _is_collection_annotation(node.slice)
    return False


def _is_collection_annotation(node: ast.expr) -> bool:
    if isinstance(node, ast.Name) and node.id in ("list", "dict", "set", "tuple", "List", "Dict", "Set", "Tuple"):
        return True
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return node.value.id in ("list", "dict", "set", "tuple", "List", "Dict", "Set", "Tuple", "Sequence", "Mapping")
    return False


def _check_no_optional_collection_param_default_none() -> tuple[str, list[Violation]]:
    return "OPTIONAL COLLECTION param with `= None` default", _run_scan_src_and_tests(_scan_optional_collection_params)


def _scan_optional_collection_params(path: Path, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, _ = _load(path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        positional_args = list(node.args.posonlyargs) + list(node.args.args)
        kw_args = list(node.args.kwonlyargs)

        positional_with_defaults = list(
            zip(positional_args[-len(node.args.defaults) :], node.args.defaults, strict=False)
        )
        kw_with_defaults = list(zip(kw_args, node.args.kw_defaults, strict=False))

        for arg, default in positional_with_defaults + kw_with_defaults:
            if default is None:
                continue
            if not (isinstance(default, ast.Constant) and default.value is None):
                continue
            if arg.annotation is None:
                continue
            if not _is_optional_collection_annotation(arg.annotation):
                continue
            snippet = lines[arg.lineno - 1].strip() if arg.lineno <= len(lines) else ""
            violations.append(Violation(rel, arg.lineno, f"{node.name}({arg.arg}): {snippet}"))
    return violations


def _check_no_setdefault_calls() -> tuple[str, list[Violation]]:
    pattern = re.compile(r"\.setdefault\(")
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return ".setdefault() fallback (use direct subscript)", violations


def _check_no_get_raw_with_fallback() -> tuple[str, list[Violation]]:
    pattern = re.compile(r"\.get_raw\(\s*[^,)]+,\s*[^)]+\)")
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return "eng().get_raw(key, fallback) — domain config raises on miss", violations


def _check_no_warning_suppression() -> tuple[str, list[Violation]]:
    pattern = re.compile(r"#\s*(noqa|type:\s*ignore|pragma:\s*no\s*cover)")
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    for path in _iter_test_files():
        rel = _rel_test(path)
        for i, line in enumerate(_load(path)[1], 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return "warning-suppression comment (noqa / type: ignore / pragma)", violations


def _check_no_versioned_filenames() -> tuple[str, list[Violation]]:
    versioned = re.compile(r"_(v\d+|old|deprecated|new|backup|copy)\.py$")
    violations: list[Violation] = []
    for path in _iter_source_files():
        if versioned.search(path.name):
            violations.append(Violation(_rel(path), 0, path.name))
    return "versioned filename suffix (edit in place, no _v2.py / _old.py)", violations


def _check_ruff_format_clean() -> tuple[str, list[Violation]]:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(SRC_ROOT), str(TESTS_ROOT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode == 0:
        return "ruff format drift (delivery gate)", []
    violations: list[Violation] = []
    for line in result.stdout.splitlines():
        match = re.match(r"^Would reformat:\s+(.+)$", line)
        if match:
            file_path = Path(match.group(1))
            try:
                rel = file_path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                rel = str(file_path)
            violations.append(Violation(rel, 0, "would reformat"))
    if not violations:
        violations.append(Violation("<ruff>", 0, result.stdout.strip() or result.stderr.strip()))
    return "ruff format drift (delivery gate)", violations


_ORPHAN_SYMBOL_CARVE_OUT: set[tuple[str, str]] = {
    ("AppConfig", "engine/config_loader.py"),
    ("AIConfig", "engine/config_loader.py"),
    ("ServerConfig", "engine/config_loader.py"),
    ("ClusterConfig", "engine/config_loader.py"),
    ("LanguageConfig", "engine/config_loader.py"),
    ("OraclePaths", "engine/datasworn/settings.py"),
    ("CreationFlow", "engine/datasworn/settings.py"),
    ("VocabularyConfig", "engine/datasworn/settings.py"),
    ("OracleResult", "engine/datasworn/loader.py"),
    ("OracleRow", "engine/datasworn/loader.py"),
    ("RollOption", "engine/datasworn/moves.py"),
    ("TriggerCondition", "engine/datasworn/moves.py"),
    ("MoveEffect", "engine/mechanics/move_effects.py"),
    ("ActionOutcome", "engine/game/finalization.py"),
    ("homepage", "web/server.py"),
    ("websocket_endpoint", "web/server.py"),
    ("build_director_prompt", "engine/director.py"),
    ("build_stats_line", "engine/ai/brain.py"),
    ("apply_engine_memories", "engine/game/finalization.py"),
    ("set_backoff_sleep", "engine/ai/provider_base.py"),
    ("register_test_tool", "engine/tools/registry.py"),
    ("clear_cache", "engine/datasworn/moves.py"),
    ("clear_cache", "engine/datasworn/settings.py"),
    ("query_npc", "engine/tools/builtins.py"),
    ("query_active_threads", "engine/tools/builtins.py"),
    ("query_active_clocks", "engine/tools/builtins.py"),
    ("CharacterTraits", "engine/mechanics/adventure_crafter.py"),
    ("roll_character_traits", "engine/mechanics/adventure_crafter.py"),
    ("lookup_character_special_trait", "engine/mechanics/adventure_crafter.py"),
    ("lookup_character_identity", "engine/mechanics/adventure_crafter.py"),
    ("lookup_character_descriptor", "engine/mechanics/adventure_crafter.py"),
}


def _collect_public_symbols() -> dict[tuple[str, Path], None]:
    defs: dict[tuple[str, Path], None] = {}
    for path in _iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = _rel(path)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            if (node.name, rel) in _ORPHAN_SYMBOL_CARVE_OUT:
                continue
            defs[(node.name, path)] = None
    return defs


def _collect_src_uses() -> dict[Path, set[str]]:
    uses: dict[Path, set[str]] = {}
    for path in _iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                names.add(node.args[1].value)
        uses[path] = names
    return uses


def _check_no_orphan_public_symbols() -> tuple[str, list[Violation]]:
    defs = _collect_public_symbols()
    uses = _collect_src_uses()
    violations: list[Violation] = []
    for name, defining_file in defs:
        external_use = any(name in refs for f, refs in uses.items() if f != defining_file)
        if external_use:
            continue
        intra_uses = sum(
            1 for n in ast.walk(ast.parse(defining_file.read_text(encoding="utf-8"))) if _is_load_ref(n, name)
        )
        if intra_uses > 0:
            continue
        rel = _rel(defining_file)
        violations.append(Violation(rel, 0, f"public symbol {name!r} has no consumer"))
    return "orphan public symbol (defined but never used)", violations


def _is_load_ref(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name:
        return True
    if isinstance(node, ast.ImportFrom):
        return any(alias.name == name for alias in node.names)
    return False


_ORPHAN_YAML_KEY_CARVE_OUT: set[tuple[str, str]] = set()


def _check_no_orphan_yaml_keys() -> tuple[str, list[Violation]]:
    if not ENGINE_YAML_ROOT.exists():
        return "orphan engine yaml top-level key", []
    py_text = "\n".join(p.read_text(encoding="utf-8") for p in (*_iter_source_files(), *_iter_test_files()))
    violations: list[Violation] = []
    for yfile in sorted(ENGINE_YAML_ROOT.glob("*.yaml")):
        try:
            data = yaml.safe_load(yfile.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        for key in data:
            if not isinstance(key, str):
                continue
            if (yfile.name, key) in _ORPHAN_YAML_KEY_CARVE_OUT:
                continue
            literal_patterns = [f'"{key}"', f"'{key}'", f".{key}", f"['{key}']", f'["{key}"]']
            if any(p in py_text for p in literal_patterns):
                continue
            dotted_pattern = f'get_raw("{key}'
            dotted_pattern_alt = f"get_raw('{key}"
            if dotted_pattern in py_text or dotted_pattern_alt in py_text:
                continue
            violations.append(Violation(yfile.name, 0, f"top-level key {key!r} has no Python reader"))
    return "orphan engine yaml top-level key", violations


def _defines(path: Path, name: str) -> bool:
    if not path.exists():
        return False
    return any(
        isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and n.name == name
        for n in ast.walk(_load(path)[2])
    )


def _has_broad_except(path: Path) -> bool:
    return any(
        isinstance(n, ast.ExceptHandler) and n.type is not None and _catches_broad(n.type)
        for n in ast.walk(_load(path)[2])
    )


def _check_no_stale_carve_out_entries() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for rel in sorted(_AI_CALL_CARVE_OUT_FILES):
        path = SRC_ROOT / rel
        if not path.exists():
            violations.append(Violation(rel, 0, "AI-call carve-out file does not exist"))
        elif not _has_broad_except(path):
            violations.append(Violation(rel, 0, "AI-call carve-out file has no broad except to carve out"))
    for rel in sorted(_AI_CALL_CARVE_OUT_TESTS | _HARDCODED_MODEL_NAME_TEST_WHITELIST):
        if not (TESTS_ROOT / rel).exists():
            violations.append(Violation(rel, 0, "test carve-out file does not exist"))
    for rel in sorted(_PROVIDER_IMPORT_ALLOWED):
        if not (SRC_ROOT / rel).exists():
            violations.append(Violation(rel, 0, "provider-import allowance for a file that does not exist"))
    for name, rel in sorted(_ORPHAN_SYMBOL_CARVE_OUT):
        if not _defines(SRC_ROOT / rel, name):
            violations.append(Violation(rel, 0, f"orphan carve-out {name!r} is not defined there"))
    for rel, name in sorted(_INLINE_IMPORT_WHITELIST):
        if not _defines(SRC_ROOT / rel, name):
            violations.append(Violation(rel, 0, f"inline-import whitelist function {name!r} is not defined there"))
    for rel, name in sorted(_COMPLEXITY_TEST_WHITELIST):
        if not _defines(TESTS_ROOT / rel, name):
            violations.append(Violation(rel, 0, f"complexity whitelist function {name!r} is not defined there"))
    return "STALE carve-out or whitelist entry", violations


_SKIP_PATTERN = re.compile(r"pytest\.(mark\.)?(skip|skipif|xfail)\b")


def _check_no_skip_or_xfail_in_tests() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_test_files():
        rel = _rel_test(path)
        for i, line in enumerate(_load(path)[1], 1):
            if _SKIP_PATTERN.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return "pytest skip/xfail (a test that cannot run must fail, not disappear)", violations


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


_DOC_FILES = ("README.md", "ARCHITECTURE.md", "SECURITY.md", "ORIGINS.md", "AUDIT.md")
_DOC_PATH_PLACEHOLDERS = {
    "data/settings/your_setting.yaml",
    "ai/provider_yourname.py",
    "elvira_session.json",
    "tests/elvira/elvira_session.json",
}
_DOC_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|yaml|sql|json|html|toml|md))(?:::[A-Za-z_]\w*)?`")
_OWNERSHIP_REF = re.compile(r"`([\w/]+\.py)` → ((?:`\w+`(?:, )?)+)")
_OWNERSHIP_REF_COLON = re.compile(r"`([\w/]+\.py)::(\w+)`")
_CHANGELOG_HEADER = re.compile(r"^## \[(\d+(?:\.\d+)+)\]")
_NON_PROJECT_WALK_DIRS = frozenset(
    {".git", "venv", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
)


def _repo_files() -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _NON_PROJECT_WALK_DIRS and not d.endswith(".egg-info")]
        rel_dir = Path(dirpath).relative_to(REPO_ROOT).as_posix()
        out.extend(f if rel_dir == "." else f"{rel_dir}/{f}" for f in filenames)
    return out


def _check_doc_paths_exist() -> tuple[str, list[Violation]]:
    files = _repo_files()
    violations: list[Violation] = []
    used_placeholders: set[str] = set()
    for doc in _DOC_FILES:
        for lineno, line in enumerate((REPO_ROOT / doc).read_text(encoding="utf-8").splitlines(), 1):
            for match in _DOC_PATH.finditer(line):
                path = match.group(1)
                if path in _DOC_PATH_PLACEHOLDERS:
                    used_placeholders.add(path)
                    continue
                if not any(f == path or f.endswith("/" + path) for f in files):
                    violations.append(Violation(doc, lineno, f"`{path}` does not exist"))
    for placeholder in sorted(_DOC_PATH_PLACEHOLDERS - used_placeholders):
        violations.append(Violation("<placeholders>", 0, f"`{placeholder}` is no longer used in any md file"))
    return "DOC DRIFT: path named in an md file does not exist", violations


def _file_map_section() -> str:
    text = (REPO_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    start = text.index("## File Map")
    return text[start : text.index("\n## ", start + 1)]


def _check_file_map_complete() -> tuple[str, list[Violation]]:
    listed = set(re.findall(r"([A-Za-z_]\w*\.(?:py|sql|html))", _file_map_section()))
    existing = {p.name for p in SRC_ROOT.rglob("*") if p.suffix in (".py", ".sql", ".html")}
    violations: list[Violation] = []
    for path in sorted(_iter_source_files()):
        if path.name != "__init__.py" and path.name not in listed:
            violations.append(Violation(_rel(path), 0, "missing from the ARCHITECTURE.md file map"))
    for name in sorted(listed - existing):
        violations.append(Violation("ARCHITECTURE.md", 0, f"file map lists {name!r}, which does not exist"))
    return "DOC DRIFT: ARCHITECTURE.md file map", violations


def _defines_top_level(path: Path, name: str) -> bool:
    tree = _load(path)[2]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def _resolve_src_path(rel: str) -> Path | None:
    matches = [p for p in _iter_source_files() if p.as_posix().endswith("/" + rel)]
    return matches[0] if len(matches) == 1 else None


def _check_ownership_symbols_exist() -> tuple[str, list[Violation]]:
    text = (REPO_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    violations: list[Violation] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        refs = [(m.group(1), n) for m in _OWNERSHIP_REF.finditer(line) for n in re.findall(r"`(\w+)`", m.group(2))]
        refs += [(m.group(1), m.group(2)) for m in _OWNERSHIP_REF_COLON.finditer(line)]
        for rel, name in refs:
            path = _resolve_src_path(rel)
            if path is None:
                violations.append(Violation("ARCHITECTURE.md", lineno, f"`{rel}` does not resolve to one source file"))
            elif not _defines_top_level(path, name):
                violations.append(Violation("ARCHITECTURE.md", lineno, f"`{rel}` does not define {name!r}"))
    return "DOC DRIFT: ARCHITECTURE.md names a symbol that does not exist", violations


def _check_changelog_consistent() -> tuple[str, list[Violation]]:
    lines = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    violations: list[Violation] = []
    headers = [(i, m.group(1)) for i, line in enumerate(lines, 1) if (m := _CHANGELOG_HEADER.match(line))]
    if project_version is None or not headers or headers[0][1] != project_version.group(1):
        violations.append(Violation("CHANGELOG.md", 0, "newest entry does not match the pyproject.toml version"))
    for (_, newer), (lineno, older) in zip(headers, headers[1:], strict=False):
        if tuple(int(x) for x in older.split(".")) >= tuple(int(x) for x in newer.split(".")):
            violations.append(Violation("CHANGELOG.md", lineno, f"{older} is not older than {newer}"))
    for i, line in enumerate(lines):
        if line.strip() != "---":
            continue
        following = next((nxt for nxt in lines[i + 1 :] if nxt.strip()), None)
        if following is not None and not following.startswith("## "):
            violations.append(Violation("CHANGELOG.md", i + 1, "entry after a separator has no version header"))
    return "DOC DRIFT: CHANGELOG versions and headers", violations


_ALL_CHECKS = (
    _check_no_domain_default_in_dict_get,
    _check_no_or_literal_fallback_on_lookups,
    _check_no_name_or_empty_collection_fallback,
    _check_no_optional_collection_param_default_none,
    _check_no_dataclass_defaults_in_config_binding,
    _check_broad_except_inside_carve_out_only,
    _check_no_python_comments_or_docstrings,
    _check_no_yaml_comments,
    _check_inline_imports_only_in_whitelist,
    _check_dataclasses_in_models_inherit_serializablemixin,
    _check_no_direct_provider_sdk_imports,
    _check_no_hardcoded_model_names_in_engine,
    _check_no_function_exceeds_complexity_ceiling,
    _check_no_setdefault_calls,
    _check_no_get_raw_with_fallback,
    _check_no_warning_suppression,
    _check_no_versioned_filenames,
    _check_ruff_format_clean,
    _check_no_orphan_public_symbols,
    _check_no_orphan_yaml_keys,
    _check_no_stale_carve_out_entries,
    _check_no_skip_or_xfail_in_tests,
    _check_no_orphan_prompt_keys,
    _check_doc_paths_exist,
    _check_file_map_complete,
    _check_ownership_symbols_exist,
    _check_changelog_consistent,
)


def test_project_rules() -> None:
    failed: list[tuple[str, list[Violation]]] = []
    for check in _ALL_CHECKS:
        category, violations = check()
        if violations:
            failed.append((category, violations))

    if failed:
        report = "\n\n".join(_format_report(cat, vs) for cat, vs in failed)
        raise AssertionError("\n" + report)
