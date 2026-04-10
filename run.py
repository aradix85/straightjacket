#!/usr/bin/env python3
"""
Straightjacket Launcher
=======================
Run from project root: python run.py

First run: creates venv, installs dependencies, starts the server.
Subsequent runs: checks venv exists, starts the server.
Works on Windows, macOS, Linux.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / "venv" / "Scripts" / "python.exe"
    return ROOT / "venv" / "bin" / "python"


def _in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def _bootstrap():
    """Create venv if needed, install dependencies, re-launch inside venv."""
    venv_py = _venv_python()

    if not venv_py.exists():
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / "venv")])

    subprocess.check_call([str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip", "setuptools", "wheel"])

    print("Checking dependencies...")
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "--quiet", "-r", str(ROOT / "requirements.txt")])

    os.execv(str(venv_py), [str(venv_py), str(ROOT / "run.py")])


def _ensure_data():
    """Download game data files if missing."""
    data_dir = ROOT / "data"
    needed = [
        "classic.json",
        "starforged.json",
        "sundered_isles.json",
        "delve.json",
        "mythic_gme_2e.json",
        "adventure_crafter.json",
    ]
    missing = [f for f in needed if not (data_dir / f).exists()]
    if not missing:
        return
    print(f"Downloading game data ({len(missing)} files)...")
    subprocess.check_call([sys.executable, str(data_dir / "data.py")])


def _start():
    """Start the Straightjacket server."""
    _ensure_data()
    sys.path.insert(0, str(ROOT / "src"))

    from straightjacket.engine import cfg, log, setup_file_logging

    setup_file_logging()

    # Early warning: check API key env var exists before starting server
    env_var = cfg().ai.api_key_env
    if not os.environ.get(env_var):
        log(f"[Server] WARNING: ${env_var} is not set. AI calls will fail.", level="warning")
        print(f"\n  ⚠ No API key: ${env_var} is not set. Set it before playing.\n")

    port = cfg().server.port
    host = cfg().server.host
    log(f"[Server] Starting Straightjacket on http://{host}:{port}")

    import uvicorn
    from straightjacket.web.server import app

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    if _in_venv():
        _start()
    else:
        _bootstrap()
