#!/usr/bin/env python3
"""
Straightjacket Launcher
===================
Run from project root: python run.py

First run: creates venv, installs dependencies, starts the server.
Subsequent runs: checks venv exists, starts the server.
Works on Windows, macOS, Linux.
"""

import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    """Return path to the venv's Python executable."""
    if sys.platform == "win32":
        return ROOT / "venv" / "Scripts" / "python.exe"
    return ROOT / "venv" / "bin" / "python"


def _in_venv() -> bool:
    """Check if we're already running inside the project venv."""
    return sys.prefix != sys.base_prefix


def _bootstrap():
    """Create venv if needed, install dependencies, re-launch inside venv."""
    venv_py = _venv_python()

    if not venv_py.exists():
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / "venv")])
        print("venv created.")

    # Upgrade pip + setuptools first — stale pip on Windows tries to compile
    # packages from source instead of using pre-built wheels
    subprocess.check_call(
        [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade",
         "pip", "setuptools", "wheel"]
    )

    # Install/check dependencies — only-binary prevents Rust compilation attempts
    print("Checking dependencies...")
    deps = [
        "nicegui", "anthropic", "openai",
        "cryptography", "PyYAML",
    ]
    subprocess.check_call(
        [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade",
         "--only-binary", ":all:"] + deps
    )

    # Re-launch this script inside the venv
    os.execv(str(venv_py), [str(venv_py), str(ROOT / "run.py")])


def _ensure_data():
    """Check Datasworn JSON files exist, download if missing."""
    data_dir = ROOT / "data"
    needed = ["classic.json", "starforged.json", "sundered_isles.json", "delve.json"]
    missing = [f for f in needed if not (data_dir / f).exists()]
    if not missing:
        return
    print(f"Downloading game data ({len(missing)} files)...")
    subprocess.check_call([sys.executable, str(data_dir / "download_datasworn.py")])


def _start():
    """Add src/ to path and start Straightjacket."""
    _ensure_data()
    sys.path.insert(0, str(ROOT / "src"))
    import straightjacket.app  # noqa: F401


if __name__ == "__main__":
    if _in_venv():
        _start()
    else:
        _bootstrap()
