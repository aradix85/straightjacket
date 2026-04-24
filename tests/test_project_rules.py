"""Mechanical enforcement of the project's absolute rules.

These tests scan src/straightjacket/ with AST and regex and fail on any
violation of the patterns the handwritten audits were supposed to catch.
The tests are the arbiter; no audit report is trusted on faith.

Each test emits a full list of offending (file, line, snippet) tuples so
a failure points straight at the offending code.

Carve-outs are expressed by allowlisted modules or by a comment marker
near the offending line — never by skipping the test.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "straightjacket"

# Modules where try/except Exception is a documented carve-out.
# Policy lives in engine/ai/provider_base.py module docstring.
#  - AI-call sites: transient API faults must degrade gracefully.
#  - Tool-boundary: handler returns structured error dicts to AI caller.
#  - Web handlers: WebSocket boundary — dead sockets, stale clients.
_AI_CALL_CARVE_OUT_FILES = {
    "engine/ai/brain.py",
    "engine/ai/narrator.py",
    "engine/ai/validator.py",
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

# Policy-marker tokens that sanction a broad except or an inline import.
# Presence of any of these in a comment on or near the offending line
# tells the test the carve-out is acknowledged and intentional.
_CARVE_OUT_MARKERS = (
    "policy",
    "carve-out",
    "carve out",
    "provider_base",
    "ai-call",
    "ai call",
    "graceful degradation",
    "transient",
    "tool_boundary",
    "tool boundary",
    "cycle",
    "circular",
    "lazy",
    "lazy-load",
    "lazy load",
    "optional dep",
    "heavy",
    "deferred",
    "avoid import",
)


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    snippet: str

    def __str__(self) -> str:
        return f"  {self.file}:{self.line}  {self.snippet}"


def _iter_source_files() -> Iterator[Path]:
    """Yield every .py file under src/straightjacket/."""
    yield from SRC_ROOT.rglob("*.py")


def _rel(path: Path) -> str:
    """Path relative to SRC_ROOT, posix-style, for readable reports."""
    return path.relative_to(SRC_ROOT).as_posix()


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _format_report(category: str, violations: list[Violation]) -> str:
    header = f"{category}: {len(violations)} violation(s)\n"
    body = "\n".join(str(v) for v in violations)
    return header + body


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Map id(child_node) → parent_node for every node in the tree."""
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
    """True if node is lexically inside an f-string or a log/logger call."""
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
    """True if node is a string literal in docstring position."""
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
    """True if node is an operand of arithmetic or a numeric function.

    Used to let `len(x) or 1` and `norm or 1.0` through — those are
    divide-by-zero guards, not silent domain defaults.
    """
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


# ---------------------------------------------------------------------------
# Check 1: dict.get(key, literal) with a non-neutral literal fallback.
# ---------------------------------------------------------------------------

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
    """`.get("key", <domain literal>)` smuggles a silent default into code."""
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


# ---------------------------------------------------------------------------
# Check 2: `X or "literal"` fallback pattern on config/domain lookups.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Check 3: dataclass field defaults in the config-binding module.
# ---------------------------------------------------------------------------


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
    """engine_config.py is the yaml binding. Every public field must be required.

    Underscore-prefixed fields (`_raw`, `_compiled_patterns`) are internal
    caches, not yaml-loaded config — defaults on those are allowed.
    """
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


# ---------------------------------------------------------------------------
# Check 4: broad try/except Exception outside the AI-call carve-out.
# ---------------------------------------------------------------------------


def _except_has_marker(lines: list[str], except_lineno: int) -> bool:
    start = except_lineno
    end = min(len(lines), except_lineno + 5)
    for i in range(start, end):
        line_lower = lines[i].lower()
        if "#" not in line_lower:
            continue
        comment = line_lower[line_lower.index("#") :]
        if any(marker in comment for marker in _CARVE_OUT_MARKERS):
            return True
    return False


def test_broad_except_requires_policy_marker() -> None:
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
                continue
            if not _except_has_marker(lines, node.lineno):
                violations.append(Violation(rel, node.lineno, f"except Exception missing policy marker: {snippet}"))

    assert not violations, "\n" + _format_report("BROAD except/catch", violations)


# ---------------------------------------------------------------------------
# Check 5: TODO comments without a concrete trigger tag.
# ---------------------------------------------------------------------------

_TODO_OK = re.compile(r"#\s*(TODO|FIXME)\(\S[^)]*\)\s*:")
_TODO_ANY = re.compile(r"#\s*(TODO|FIXME)\b")


def test_no_untagged_todo_comments() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        for lineno, line in enumerate(_read_lines(path), start=1):
            if not _TODO_ANY.search(line):
                continue
            if _TODO_OK.search(line):
                continue
            violations.append(Violation(_rel(path), lineno, line.strip()))
    assert not violations, "\n" + _format_report("UNTAGGED TODO", violations)


# ---------------------------------------------------------------------------
# Check 6: ceremonial banner comments.
# ---------------------------------------------------------------------------


def _is_banner_comment(stripped: str) -> bool:
    if not stripped.startswith("#"):
        return False
    body = stripped.lstrip("#").strip()
    if not body:
        return False
    decorative = sum(1 for ch in body if not ch.isalnum() and not ch.isspace())
    total = len(body)
    if total < 6:
        return False
    if decorative / total < 0.6:
        return False
    return re.search(r"(─{3,}|━{3,}|═{3,}|-{3,}|={3,}|#{3,}|\*{3,}|_{3,})", body) is not None


def test_no_banner_comments() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
        for lineno, line in enumerate(_read_lines(path), start=1):
            if _is_banner_comment(line.strip()):
                violations.append(Violation(_rel(path), lineno, line.strip()))
    assert not violations, "\n" + _format_report("BANNER COMMENT", violations)


# ---------------------------------------------------------------------------
# Check 7: inline imports without a carve-out marker comment.
# ---------------------------------------------------------------------------


def _line_has_marker(lines: list[str], lineno: int) -> bool:
    same = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    if "#" in same:
        comment = same[same.index("#") :].lower()
        if any(m in comment for m in _CARVE_OUT_MARKERS):
            return True
    if lineno >= 2:
        above = lines[lineno - 2].strip().lower()
        if above.startswith("#") and any(m in above for m in _CARVE_OUT_MARKERS):
            return True
    return False


def test_inline_imports_have_marker_comment() -> None:
    violations: list[Violation] = []
    for path in _iter_source_files():
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
                if _line_has_marker(lines, node.lineno):
                    continue
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                violations.append(Violation(_rel(path), node.lineno, snippet))
    assert not violations, "\n" + _format_report("INLINE IMPORT without marker", violations)


# ---------------------------------------------------------------------------
# Check 8: every @dataclass in models*.py inherits SerializableMixin.
# ---------------------------------------------------------------------------
#
# Save-format coverage. The `SceneLogEntry.oracle_answer` bug from 0.64
# was this class of problem: a field in the dataclass and savefile but
# not in the DB. A stricter variant: adding a @dataclass to models*.py
# without SerializableMixin means the type silently doesn't persist.
#
# Exempt: classes whose docstring says "not serialized" / "not persisted".


_MODELS_FILES = ("models.py", "models_base.py", "models_npc.py", "models_story.py")


def _class_inherits_mixin(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "SerializableMixin":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "SerializableMixin":
            return True
    return False


def _class_docstring(node: ast.ClassDef) -> str:
    if not node.body:
        return ""
    first = node.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value
    return ""


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
            doc = _class_docstring(node).lower()
            if "not serialized" in doc or "not persisted" in doc:
                continue
            snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            violations.append(Violation(_rel(path), node.lineno, f"{node.name}: {snippet}"))

    assert not violations, "\n" + _format_report("DATACLASS without SerializableMixin", violations)


# ---------------------------------------------------------------------------
# Check 9: no direct provider SDK imports outside the provider adapters.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Check 10: no hardcoded model-name strings in engine code.
# ---------------------------------------------------------------------------
#
# Models are assigned via clusters in config.yaml; resolved via
# model_for_role(role). A literal model-name in engine code is a sign
# the cluster abstraction has been bypassed. Docstrings are exempt.


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


# ── Cyclomatic complexity ceiling ──────────────────────────────────
# No function may have cyclomatic complexity above 20 (radon C-rank
# upper bound). D-rank and worse (21+) mean too many branches in one
# function — the fix is decomposition into named phase-helpers, not
# a higher threshold. A hit here is a signal that the function has
# grown a new responsibility that deserves its own sub-function.
_COMPLEXITY_CEILING = 20


def test_no_function_exceeds_complexity_ceiling() -> None:
    # inline import: radon is a test-only dependency, not needed at runtime
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
