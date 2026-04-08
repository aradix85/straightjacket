"""Straightjacket — AI-powered narrative solo RPG engine."""

import re as _re
from pathlib import Path as _Path


def _read_version() -> str:
    pyproject = _Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if pyproject.exists():
        m = _re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), _re.MULTILINE)
        if m:
            return m.group(1)
    return "0.0.0"


__version__ = _read_version()
