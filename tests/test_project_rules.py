from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "straightjacket"
TESTS_ROOT = Path(__file__).resolve().parent


_AI_CALL_CARVE_OUT_FILES = {
    "engine/ai/brain.py",
    "engine/ai/narrator.py",
    "engine/ai/architect.py",
    "engine/ai/metadata.py",
    "engine/ai/provider_base.py",
    "engine/correction/analysis.py",
    "engine/director.py",
    "engine/game/director_runner.py",
    "engine/tools/handler.py",
    "web/handlers.py",
    "web/server.py",
    "web/serializers.py",
}


_AI_CALL_CARVE_OUT_TESTS = {
    "test_integration.py",
    "elvira/elvira_bot/creation.py",
    "elvira/elvira_bot/runner.py",
    "elvira/elvira_bot/drift_checks.py",
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
    if isinstance(decorator, ast.Call):
        f = decorator.func
        if isinstance(f, ast.Name) and f.id == "dataclass":
            return True
    return False


def _has_default(stmt: ast.AnnAssign) -> bool:
    return stmt.value is not None


def _check_no_dataclass_defaults_in_config_binding() -> tuple[str, list[Violation]]:
    path = SRC_ROOT / "engine" / "engine_config.py"
    if not path.exists():
        raise AssertionError(f"expected config binding at {path}")

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

    return "DATACLASS DEFAULT in config binding", violations


def _check_broad_except_inside_carve_out_only() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        violations.extend(_scan_broad_except(path, _rel(path), _AI_CALL_CARVE_OUT_FILES))
    for path in _iter_test_files():
        violations.extend(_scan_broad_except(path, _rel_test(path), _AI_CALL_CARVE_OUT_TESTS))
    return "BROAD except/catch", violations


def _scan_broad_except(path: Path, rel: str, carve_out: set[str]) -> list[Violation]:
    violations: list[Violation] = []
    _, lines, tree, _ = _load(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            violations.append(Violation(rel, node.lineno, f"bare except: {snippet}"))
            continue
        caught = node.type
        name = None
        if isinstance(caught, ast.Name):
            name = caught.id
        elif isinstance(caught, ast.Attribute):
            name = caught.attr
        if name != "Exception":
            continue
        if rel in carve_out:
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        violations.append(Violation(rel, node.lineno, f"except Exception outside carve-out: {snippet}"))
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


def _check_no_yaml_comments() -> tuple[str, list[Violation]]:
    yaml_root = SRC_ROOT.parent.parent
    violations: list[Violation] = []
    for path in yaml_root.rglob("*.yaml"):
        rel_parts = path.relative_to(yaml_root)
        if rel_parts.parts and rel_parts.parts[0] in {".github", ".pre-commit-config.yaml"}:
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
    ("engine/datasworn/loader.py", "list_available"),
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
    r"(qwen[-\d]|gpt-oss|gpt-\d|gpt-4|claude-\d|claude-opus|claude-sonnet|claude-haiku)",
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
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return ".setdefault() fallback (use direct subscript)", violations


def _check_no_get_raw_with_fallback() -> tuple[str, list[Violation]]:
    pattern = re.compile(r"\.get_raw\(\s*[^,)]+,\s*[^)]+\)")
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return "eng().get_raw(key, fallback) — domain config raises on miss", violations


def _check_no_warning_suppression() -> tuple[str, list[Violation]]:
    pattern = re.compile(r"#\s*(noqa|type:\s*ignore|pragma:\s*no\s*cover)")
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        for i, line in enumerate(path.read_text().splitlines(), 1):
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
