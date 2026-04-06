"""Shared test fixtures: logging_util stub that all tests use.

This conftest.py runs before any test file, ensuring the stub
has all symbols the full import chain needs.
"""

import sys
import types
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Create package stubs
pkg = types.ModuleType("straightjacket")
pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "src" / "straightjacket")]
sys.modules.setdefault("straightjacket", pkg)

eng_pkg = types.ModuleType("straightjacket.engine")
eng_pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "src" / "straightjacket" / "engine")]
sys.modules.setdefault("straightjacket.engine", eng_pkg)

# Complete logging_util stub — covers all symbols used across the codebase
lm = types.ModuleType("straightjacket.engine.logging_util")
lm.log = lambda *a, **k: None
lm.setup_file_logging = lambda: None
lm.get_save_dir = lambda username: Path("/tmp/straightjacket_test") / username / "saves"
lm.load_global_config = lambda: {}
lm.save_global_config = lambda cfg: None
lm.load_user_config = lambda username: {}
lm.save_user_config = lambda username, cfg: None
lm.list_users = lambda: []
lm.create_user = lambda name: True
lm.delete_user = lambda name: True
sys.modules["straightjacket.engine.logging_util"] = lm
