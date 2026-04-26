from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "straightjacket"


_AI_CALL_CARVE_OUT_FILES = {
    "engine/ai/brain.py",
    "engine/ai/narrator.py",
    "engine/ai/validator.py",
    "engine/ai/chapter_validator.py",
    "engine/ai/architect.py",
    "engine/ai/architect_validator.py",
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


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    snippet: str

    def __str__(self) -> str:
        return f"  {self.file}:{self.line}  {self.snippet}"


def _iter_source_files() -> Iterator[Path]:
    yield from SRC_ROOT.rglob("*.py")


def _rel(path: Path) -> str:
    return path.relative_to(SRC_ROOT).as_posix()


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


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


def test_no_domain_default_in_dict_get() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _build_parent_map(tree)
        lines = _read_lines(path)

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
            violations.append(Violation(_rel(path), node.lineno, snippet))

    assert not violations, "\n" + _format_report("DOMAIN DEFAULT in .get()", violations)


def test_no_or_literal_fallback_on_lookups() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _build_parent_map(tree)
        lines = _read_lines(path)

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
            violations.append(Violation(_rel(path), node.lineno, snippet))

    assert not violations, "\n" + _format_report("`X or literal` FALLBACK on lookup", violations)


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


def test_no_dataclass_defaults_in_config_binding() -> None:
    path = SRC_ROOT / "engine" / "engine_config.py"
    if not path.exists():
        raise AssertionError(f"expected config binding at {path}")

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []
    lines = _read_lines(path)

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

    assert not violations, "\n" + _format_report("DATACLASS DEFAULT in config binding", violations)


def test_broad_except_inside_carve_out_only() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        lines = _read_lines(path)
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

            snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            if rel not in _AI_CALL_CARVE_OUT_FILES:
                violations.append(Violation(rel, node.lineno, f"except Exception outside carve-out: {snippet}"))

    assert not violations, "\n" + _format_report("BROAD except/catch", violations)


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


def test_no_python_comments_or_docstrings() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            if _COMMENT_LINE.match(line):
                violations.append(Violation(rel, i, f"# comment: {line.strip()}"))
        tree = ast.parse(text, filename=str(path))
        for lineno in _docstring_lines(tree):
            snippet = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            violations.append(Violation(rel, lineno, f"docstring: {snippet[:60]}"))
    assert not violations, "\n" + _format_report("PYTHON COMMENT or DOCSTRING", violations)


def test_no_yaml_comments() -> None:
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
    assert not violations, "\n" + _format_report("YAML COMMENT", violations)


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


def test_inline_imports_only_in_whitelist() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        lines = _read_lines(path)

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
    assert not violations, "\n" + _format_report("INLINE IMPORT outside whitelist", violations)


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


def test_dataclasses_in_models_inherit_serializablemixin() -> None:
    violations: list[Violation] = []
    for fname in _MODELS_FILES:
        path = SRC_ROOT / "engine" / fname
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        lines = _read_lines(path)
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

    assert not violations, "\n" + _format_report("DATACLASS without SerializableMixin", violations)


_PROVIDER_IMPORT_ALLOWED = {
    "engine/ai/provider_anthropic.py",
    "engine/ai/provider_openai.py",
    "engine/ai/api_client.py",
}

_FORBIDDEN_SDK_MODULES = ("anthropic", "openai")


def test_no_direct_provider_sdk_imports() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in _PROVIDER_IMPORT_ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        lines = _read_lines(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _FORBIDDEN_SDK_MODULES:
                        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        violations.append(Violation(rel, node.lineno, snippet))
            elif (
                isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _FORBIDDEN_SDK_MODULES
            ):
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                violations.append(Violation(rel, node.lineno, snippet))
    assert not violations, "\n" + _format_report("DIRECT PROVIDER SDK IMPORT outside adapter", violations)


_MODEL_NAME_PATTERNS = re.compile(
    r"(qwen[-\d]|gpt-oss|gpt-\d|gpt-4|claude-\d|claude-opus|claude-sonnet|claude-haiku)",
    re.IGNORECASE,
)


def test_no_hardcoded_model_names_in_engine() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel in {"engine/config_loader.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _build_parent_map(tree)
        lines = _read_lines(path)
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

    assert not violations, "\n" + _format_report("HARDCODED MODEL NAME in engine code", violations)


_COMPLEXITY_CEILING = 20


def test_no_function_exceeds_complexity_ceiling() -> None:
    from radon.complexity import cc_visit

    violations: list[Violation] = []
    for path in _iter_source_files():
        try:
            code = path.read_text(encoding="utf-8")
            blocks = cc_visit(code)
        except SyntaxError:
            continue
        rel = _rel(path)
        for block in blocks:
            if block.complexity > _COMPLEXITY_CEILING:
                snippet = f"{block.name} — complexity {block.complexity}"
                violations.append(Violation(rel, block.lineno, snippet))

    assert not violations, "\n" + _format_report(
        f"CYCLOMATIC COMPLEXITY above {_COMPLEXITY_CEILING} (decompose into sub-functions)", violations
    )
