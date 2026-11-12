from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tests._rules import (
    REPO_ROOT,
    SRC_ROOT,
    Violation,
    _iter_source_files,
    _iter_test_files,
    _load,
    _rel,
    _rel_test,
    _run_scan_src_and_tests,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_AI_CALL_CARVE_OUT_FILES = {
    "engine/ai/brain.py",
    "engine/ai/narrator.py",
    "engine/ai/recap.py",
    "engine/ai/blueprint_voicing.py",
    "engine/ai/provider_base.py",
    "engine/correction/analysis.py",
    "engine/director.py",
    "web/handlers.py",
    "web/server.py",
}

_AI_CALL_CARVE_OUT_TESTS = {
    "elvira/elvira_bot/runner.py",
    "elvira/elvira_bot/ws_runner.py",
    "elvira/elvira_bot/judge.py",
}

_HARDCODED_MODEL_NAME_TEST_WHITELIST = {
    "_rules_code.py",
}


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


_CONFIG_BINDING_FILES = frozenset(
    {
        "engine/config_loader.py",
        "engine/emotions_loader.py",
        "engine/engine_config.py",
        "engine/engine_config_dataclasses.py",
        "engine/gamemaster/config.py",
        "engine/gamemaster/config_types.py",
        "engine/crafters/config.py",
        "engine/ruleset/config.py",
        "engine/ruleset/config_types.py",
    }
)

_EXTERNAL_STRUCTURE_DATACLASSES: set[tuple[str, str]] = {
    ("engine/ai/provider_base.py", "AIResponse"),
}

_EMPTY_COLLECTION_FACTORIES = frozenset({"list", "dict", "set"})


def _field_without_default(value: ast.expr, *, empty_collection_allowed: bool) -> bool:
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "field"):
        return False
    keywords = {k.arg: k.value for k in value.keywords}
    if "default" in keywords:
        return False
    if "default_factory" not in keywords:
        return True
    factory = keywords["default_factory"]
    return empty_collection_allowed and isinstance(factory, ast.Name) and factory.id in _EMPTY_COLLECTION_FACTORIES


def _check_no_dataclass_defaults() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        _, lines, tree, _ = _load(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not any(_is_dataclass_decorator(d) for d in node.decorator_list):
                continue
            if (rel, node.name) in _EXTERNAL_STRUCTURE_DATACLASSES:
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or stmt.value is None:
                    continue
                field_name = stmt.target.id if isinstance(stmt.target, ast.Name) else "?"
                if _field_without_default(stmt.value, empty_collection_allowed=rel not in _CONFIG_BINDING_FILES):
                    continue
                snippet = lines[stmt.lineno - 1].strip()
                violations.append(Violation(rel, stmt.lineno, f"{node.name}.{field_name}: {snippet}"))
    return (
        "DATACLASS DEFAULT (none but empty collections, not on fields bound from yaml, and external structures)",
        violations,
    )


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
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                violations.append(Violation(rel, lineno, f"bare except: {snippet}"))
            elif rel not in carve_out and _catches_broad(node.type):
                violations.append(Violation(rel, lineno, f"broad except outside carve-out: {snippet}"))
        elif rel not in carve_out and isinstance(node, ast.Call) and _is_broad_suppress(node):
            violations.append(Violation(rel, lineno, f"broad suppress() outside carve-out: {snippet}"))
    return violations


_COMMENT_LINE = re.compile(r"^\s*#")


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


def _iter_root_scripts() -> Iterator[Path]:
    yield REPO_ROOT / "run.py"
    yield from sorted((REPO_ROOT / "data").glob("*.py"))


def _check_no_python_comments_or_docstrings() -> tuple[str, list[Violation]]:
    violations = _run_scan_src_and_tests(_scan_comments_docstrings)
    for path in _iter_root_scripts():
        violations.extend(_scan_comments_docstrings(path, path.relative_to(REPO_ROOT).as_posix()))
    return "PYTHON COMMENT or DOCSTRING", violations


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
        value: ast.expr | None
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets, value = [stmt.target], stmt.value
        else:
            continue
        named = any(isinstance(target, ast.Name) and target.id == "_NOT_SERIALIZED" for target in targets)
        if named and isinstance(value, ast.Constant) and value.value is True:
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


_MODEL_NAME_PATTERNS = re.compile(
    r"(qwen[-\d]|gpt-oss|gpt-\d|gpt-4|claude-\d|claude-opus|claude-sonnet|claude-haiku"
    r"|glm-?\d|zai-|deepseek|kimi-|llama-?\d|mistral-)",
    re.IGNORECASE,
)


def _check_no_hardcoded_model_names_in_engine() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel == "engine/config_loader.py":
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
        and node.func.id in {"list", "dict", "set", "tuple"}
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
    if isinstance(node, ast.Name) and node.id in {"list", "dict", "set", "tuple", "List", "Dict", "Set", "Tuple"}:
        return True
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return node.value.id in {"list", "dict", "set", "tuple", "List", "Dict", "Set", "Tuple", "Sequence", "Mapping"}
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
    violations = [Violation(_rel(path), 0, path.name) for path in _iter_source_files() if versioned.search(path.name)]
    return "versioned filename suffix (edit in place, no _v2.py / _old.py)", violations


def _check_ruff_format_clean() -> tuple[str, list[Violation]]:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(REPO_ROOT)],
        check=False,
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


_SKIP_PATTERN = re.compile(r"pytest\.(mark\.)?(skip|skipif|xfail)\b")


def _check_no_skip_or_xfail_in_tests() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for path in _iter_test_files():
        rel = _rel_test(path)
        for i, line in enumerate(_load(path)[1], 1):
            if _SKIP_PATTERN.search(line):
                violations.append(Violation(rel, i, line.strip()))
    return "pytest skip/xfail (a test that cannot run must fail, not disappear)", violations


def _check_ai_calls_route_by_their_role() -> tuple[str, list[Violation]]:
    config = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    roles = set(config["ai"]["role_cluster"])
    violations: list[Violation] = []
    for path in _iter_source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                not isinstance(node, ast.Call)
                or getattr(node.func, "id", getattr(node.func, "attr", "")) != "AICallSpec"
            ):
                continue
            keywords = {k.arg: k.value for k in node.keywords}
            role = keywords.get("log_role")
            if not (isinstance(role, ast.Constant) and role.value in roles):
                shown = ast.unparse(role) if role is not None else "missing"
                violations.append(Violation(_rel(path), node.lineno, f"log_role {shown} is not a role in role_cluster"))
                continue
            model = keywords.get("model")
            if (
                isinstance(model, ast.Call)
                and getattr(model.func, "id", "") == "model_for_role"
                and model.args
                and isinstance(model.args[0], ast.Constant)
                and model.args[0].value != role.value
            ):
                violations.append(
                    Violation(
                        _rel(path), node.lineno, f"model_for_role({model.args[0].value!r}) with log_role {role.value!r}"
                    )
                )
    return (
        "AI CALL ROUTING: log_role must be the call's own role (the routing provider picks the provider by it)",
        violations,
    )
