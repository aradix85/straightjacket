import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_CONSOLE = logging.getLogger("straightjacket.run")
_CONSOLE_HANDLER = logging.StreamHandler(sys.stdout)
_CONSOLE_HANDLER.setFormatter(logging.Formatter("%(message)s"))
_CONSOLE.addHandler(_CONSOLE_HANDLER)
_CONSOLE.setLevel(logging.INFO)
_CONSOLE.propagate = False


def _say(text: str = "") -> None:
    _CONSOLE.info(text)


def _venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / "venv" / "Scripts" / "python.exe"
    return ROOT / "venv" / "bin" / "python"


def _in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def _bootstrap() -> None:
    venv_py = _venv_python()

    if not venv_py.exists():
        _say("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / "venv")])

    subprocess.check_call([str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip", "setuptools", "wheel"])

    _say("Checking dependencies...")
    subprocess.check_call([str(venv_py), "-m", "pip", "install", "--quiet", "-r", str(ROOT / "requirements.txt")])

    os.execv(str(venv_py), [str(venv_py), str(ROOT / "run.py")])


def _ensure_data() -> None:
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
    _say(f"Downloading game data ({len(missing)} files)...")
    subprocess.check_call([sys.executable, str(data_dir / "data.py")])


def _start() -> None:
    _ensure_data()
    sys.path.insert(0, str(ROOT / "src"))

    from straightjacket.engine.ai.api_client import check_configured_models
    from straightjacket.engine.config_loader import cfg
    from straightjacket.engine.logging_util import log

    try:
        check_configured_models()
    except (RuntimeError, TypeError, ValueError) as e:
        log(f"[Server] Startup check failed: {e}", level="error")
        _say(f"\n  Startup check failed:\n{e}\n")
        sys.exit(1)

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
