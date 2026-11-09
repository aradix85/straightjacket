from __future__ import annotations

import itertools
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from tests._rules import REPO_ROOT, SRC_ROOT, Violation, _defines, _iter_source_files

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT_DOC_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "SECURITY.md",
    "ORIGINS.md",
    "AUDIT.md",
)
_DOC_PATH_PLACEHOLDERS = {
    "ai/provider_yourname.py",
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


def _doc_files() -> list[Path]:
    return [REPO_ROOT / name for name in _ROOT_DOC_FILES] + sorted((REPO_ROOT / "docs").glob("*.md"))


def _doc_name(doc: Path) -> str:
    return doc.relative_to(REPO_ROOT).as_posix()


def _check_doc_paths_exist() -> tuple[str, list[Violation]]:
    files = _repo_files()
    violations: list[Violation] = []
    used_placeholders: set[str] = set()
    for doc in _doc_files():
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for match in _DOC_PATH.finditer(line):
                path = match.group(1)
                if path in _DOC_PATH_PLACEHOLDERS:
                    used_placeholders.add(path)
                    continue
                if not any(f == path or f.endswith("/" + path) for f in files):
                    violations.append(Violation(_doc_name(doc), lineno, f"`{path}` does not exist"))
    violations.extend(
        Violation("<placeholders>", 0, f"`{placeholder}` is no longer used in any md file")
        for placeholder in sorted(_DOC_PATH_PLACEHOLDERS - used_placeholders)
    )
    return "DOC DRIFT: path named in an md file does not exist", violations


_CODE_MAP_ENTRY = re.compile(r"^- `([\w/]+)/`")


def _code_map_packages() -> set[str]:
    text = (REPO_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    start = text.index("## Code map")
    section = text[start : text.index("\n## ", start + 1)]
    return {m.group(1) for line in section.splitlines() if (m := _CODE_MAP_ENTRY.match(line))}


def _check_code_map_complete() -> tuple[str, list[Violation]]:
    listed = _code_map_packages()
    existing = {
        path.parent.relative_to(SRC_ROOT).as_posix() for path in _iter_source_files() if path.parent != SRC_ROOT
    }
    violations = [
        Violation(package, 0, "package missing from the ARCHITECTURE.md code map")
        for package in sorted(existing - listed)
    ]
    violations.extend(
        Violation("ARCHITECTURE.md", 0, f"code map lists {package!r}, which is not a package")
        for package in sorted(listed - existing)
    )
    return "DOC DRIFT: ARCHITECTURE.md code map", violations


def _resolve_src_path(rel: str) -> Path | None:
    matches = [p for p in _iter_source_files() if p.as_posix().endswith("/" + rel)]
    return matches[0] if len(matches) == 1 else None


def _check_doc_symbols_exist() -> tuple[str, list[Violation]]:
    violations: list[Violation] = []
    for doc in _doc_files():
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            refs = [(m.group(1), n) for m in _OWNERSHIP_REF.finditer(line) for n in re.findall(r"`(\w+)`", m.group(2))]
            refs += [(m.group(1), m.group(2)) for m in _OWNERSHIP_REF_COLON.finditer(line)]
            for rel, name in refs:
                path = _resolve_src_path(rel)
                if path is None:
                    violations.append(Violation(_doc_name(doc), lineno, f"`{rel}` does not resolve to one source file"))
                elif not _defines(path, name):
                    violations.append(Violation(_doc_name(doc), lineno, f"`{rel}` does not define {name!r}"))
    return "DOC DRIFT: an md file names a symbol that does not exist", violations


_PAREN_GROUP = re.compile(r"\(([^()]*)\)")
_FILE_SECTION = re.compile(r"`?((?:docs/)?[A-Za-z]+\.md)`?, ([^`]+)$")
_FILE_PAREN_SECTION = re.compile(r"\b([A-Z]+\.md) \(([^()`]+)\)")
_SELF_SECTION = re.compile(r"^(.+) (?:below|above)$")
_REGISTER_TITLE_REF = re.compile(r'register(?: entry)? "([^"]+)"|"([^"]+)" in `docs/divergences\.md`')
_ROADMAP_STEP_REF = re.compile(r"\broadmap(?:'s)?,? (?:step )?(\d+[a-z]?)(?:\.(\w+))?")
_HEADING = re.compile(r"^#+ (.+)$")
_BOLD_LEAD = re.compile(r"^\s*(?:- |\d+\. )?\*\*([^*]+)\*\*")
_STEP_SUFFIX = re.compile(r",? step \d+$")


def _anchor(text: str) -> str:
    return re.sub(r" \([^()]*\)$", "", text.strip().rstrip(".:")).lower()


def _anchors(doc: Path) -> list[str]:
    anchors: list[str] = []
    for line in doc.read_text(encoding="utf-8").splitlines():
        match = _HEADING.match(line) or _BOLD_LEAD.match(line)
        if match:
            anchors.append(_anchor(match.group(1)))
    return anchors


def _matches_anchor(anchors: list[str], section: str) -> bool:
    return any(a == section or a.startswith(section + " ") for a in anchors)


def _names_section(anchors: list[str], section: str) -> bool:
    wanted = _anchor(_STEP_SUFFIX.sub("", section))
    if _matches_anchor(anchors, wanted):
        return True
    parts = [part for part in wanted.split(", ") if not re.fullmatch(r"step \d+", part)]
    return len(parts) > 1 and all(_matches_anchor(anchors, part) for part in parts)


def _section_refs(line: str) -> Iterator[tuple[str | None, str]]:
    for group in _PAREN_GROUP.findall(line):
        for raw_segment in group.split(";"):
            segment = raw_segment.strip()
            if match := _FILE_SECTION.search(segment):
                yield match.group(1), match.group(2)
            elif match := _SELF_SECTION.match(segment):
                yield None, match.group(1)
    for match in _FILE_PAREN_SECTION.finditer(line):
        yield match.group(1), match.group(2)


def _roadmap_steps(roadmap: str) -> tuple[set[str], set[str]]:
    done = set(re.findall(r"^- \*\*(\d+[a-z]?)\b", roadmap[roadmap.index("\n## DONE") :], re.MULTILINE))
    open_steps = set(re.findall(r"^### (\S+) — ", roadmap, re.MULTILINE)) | set(
        re.findall(r"NEXT STEP — (\S+):", roadmap)
    )
    substeps = set(re.findall(r"\*\*(\d+[a-z]?\.\w+)\*\*", roadmap))
    return open_steps | done, substeps | {f"{step}." for step in done}


def _register_titles() -> set[str]:
    text = (REPO_ROOT / "docs" / "divergences.md").read_text(encoding="utf-8")
    return {_anchor(m.group(1)) for line in text.splitlines() if (m := re.match(r"^- \*\*([^*]+)\*\*", line))}


def _section_problems(doc: Path, own: list[str], line: str) -> Iterator[str]:
    for target, section in _section_refs(line):
        path = doc if target is None else REPO_ROOT / target
        if not path.is_file():
            yield f"names {target}, which does not exist"
        elif not _names_section(own if target is None else _anchors(path), section):
            yield f"{path.name} has no section {section!r}"


def _register_problems(line: str, titles: set[str]) -> Iterator[str]:
    for match in _REGISTER_TITLE_REF.finditer(line):
        title = match.group(1) or match.group(2)
        if _anchor(title) not in titles:
            yield f"no register entry {title!r}"


def _step_problems(line: str, steps: set[str], substeps: set[str]) -> Iterator[str]:
    for step, sub in _ROADMAP_STEP_REF.findall(line):
        if step not in steps or (sub and not {f"{step}.{sub}", f"{step}."} & substeps):
            yield f"roadmap has no step {step}.{sub}".rstrip(".")


def _check_doc_references_resolve() -> tuple[str, list[Violation]]:
    roadmap_path = REPO_ROOT / "roadmap.md"
    steps, substeps = _roadmap_steps(roadmap_path.read_text(encoding="utf-8"))
    titles = _register_titles()
    violations: list[Violation] = []
    for doc in [*_doc_files(), roadmap_path]:
        own = _anchors(doc)
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            problems = [*_section_problems(doc, own, line), *_register_problems(line, titles)]
            if doc != roadmap_path:
                problems.extend(_step_problems(line, steps, substeps))
            violations.extend(Violation(_doc_name(doc), lineno, problem) for problem in problems)
    return "DOC DRIFT: a reference to a section, register entry, or roadmap step that does not exist", violations


_DIVERGENCE_ENTRY = re.compile(r"^(?:- )?\*\*[^*]+\*\*")
_DIVERGENCE_STATUS = re.compile(r"Status: (?:Permanent|Open|Until step (\S+?))[.,;]")


def _check_divergences_have_a_status() -> tuple[str, list[Violation]]:
    lines = (REPO_ROOT / "docs" / "divergences.md").read_text(encoding="utf-8").splitlines()
    roadmap = (REPO_ROOT / "roadmap.md").read_text(encoding="utf-8")
    violations: list[Violation] = []
    for lineno, line in enumerate(lines, 1):
        if not _DIVERGENCE_ENTRY.match(line):
            continue
        status = _DIVERGENCE_STATUS.search(line)
        if status is None:
            violations.append(
                Violation("docs/divergences.md", lineno, "entry without Status: Permanent, Open, or Until step N")
            )
            continue
        step = status.group(1)
        if step is not None and f"### {step} — " not in roadmap and f"NEXT STEP — {step}:" not in roadmap:
            violations.append(
                Violation("docs/divergences.md", lineno, f"Until step {step}: no such step in roadmap.md")
            )
    return "DIVERGENCE without a status or with an unknown roadmap step", violations


def _check_changelog_consistent() -> tuple[str, list[Violation]]:
    lines = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    violations: list[Violation] = []
    headers = [(i, m.group(1)) for i, line in enumerate(lines, 1) if (m := _CHANGELOG_HEADER.match(line))]
    if project_version is None or not headers or headers[0][1] != project_version.group(1):
        violations.append(Violation("CHANGELOG.md", 0, "newest entry does not match the pyproject.toml version"))
    for (_, newer), (lineno, older) in itertools.pairwise(headers):
        if tuple(int(x) for x in older.split(".")) >= tuple(int(x) for x in newer.split(".")):
            violations.append(Violation("CHANGELOG.md", lineno, f"{older} is not older than {newer}"))
    for i, line in enumerate(lines):
        if line.strip() != "---":
            continue
        following = next((nxt for nxt in lines[i + 1 :] if nxt.strip()), None)
        if following is not None and not following.startswith("## "):
            violations.append(Violation("CHANGELOG.md", i + 1, "entry after a separator has no version header"))
    return "DOC DRIFT: CHANGELOG versions and headers", violations
