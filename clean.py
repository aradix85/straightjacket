#!/usr/bin/env python3
"""Clean up generated files before creating a zip for distribution.

Usage: python clean.py

Removes __pycache__ directories, .pyc files, and tool caches.
Run this before zipping the project to share it.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REMOVE_DIRS = ["__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"]
REMOVE_EXTENSIONS = {".pyc", ".pyo"}

removed_dirs = 0
removed_files = 0

for pattern in REMOVE_DIRS:
    for d in ROOT.rglob(pattern):
        if d.is_dir():
            shutil.rmtree(d)
            removed_dirs += 1

for f in ROOT.rglob("*"):
    if f.is_file() and f.suffix in REMOVE_EXTENSIONS:
        f.unlink()
        removed_files += 1

print(f"Cleaned: {removed_dirs} directories, {removed_files} files removed.")
