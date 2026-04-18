"""Shared test fixtures: logging_util stub and reusable engine fixtures.

The logging_util stub silences file logging during tests. It must be in
sys.modules BEFORE any engine module import (every engine module does
`from .logging_util import log` at the top level).

Strategy: inject only the logging_util stub, then let Python import the
real packages normally. No package-level stubs needed.
"""

import sys
import types
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Install logging_util stub BEFORE any engine import.
# This is the ONLY module we fake. Every other module is real.
_lm = types.ModuleType("straightjacket.engine.logging_util")
_lm.log = lambda *a, **k: None  # type: ignore[attr-defined]
_lm.setup_file_logging = lambda: None  # type: ignore[attr-defined]
_lm.get_logger = lambda component: type(  # type: ignore[attr-defined]
    "_L",
    (),
    {
        "info": lambda self, *a: None,
        "debug": lambda self, *a: None,
        "warning": lambda self, *a: None,
        "error": lambda self, *a: None,
    },
)()
sys.modules["straightjacket.engine.logging_util"] = _lm

# Skip retry backoff sleeps in tests — saves ~13 seconds per full run.
from straightjacket.engine.ai.provider_base import set_backoff_sleep

set_backoff_sleep(lambda _: None)


# ── Reusable fixtures ────────────────────────────────────────


@pytest.fixture()
def load_engine() -> None:
    """Load real engine.yaml."""
    from straightjacket.engine import engine_loader

    engine_loader._eng = None
    engine_loader.eng()


@pytest.fixture()
def stub_engine() -> None:
    """Stub eng() with known values for predictable assertions.

    The stub starts from the real engine.yaml so every required key is present,
    then overrides a small set of fields for deterministic assertions. This
    keeps the stub in sync with engine_config.py automatically — when a new
    field is added, tests continue to work as long as the yaml file is updated.
    """
    from pathlib import Path

    import yaml as _yaml

    from straightjacket.engine import engine_loader
    from straightjacket.engine.config_loader import PROJECT_ROOT
    from straightjacket.engine.engine_config import parse_engine_yaml

    with open(Path(PROJECT_ROOT) / "engine.yaml", encoding="utf-8") as f:
        data = _yaml.safe_load(f)

    # Test-only overrides: deterministic values for assertions.
    data["story"]["kishotenketsu_probability"] = {"dark_gritty": 0.15}
    data["creativity_seeds"] = ["amber", "glacier", "compass", "obsidian", "cedar"]

    engine_loader._eng = parse_engine_yaml(data)


@pytest.fixture()
def stub_emotions() -> None:
    """Stub emotions_loader with minimal importance map."""
    from straightjacket.engine import emotions_loader

    emotions_loader._data = {
        "importance": {
            "neutral": 2,
            "curious": 3,
            "angry": 5,
            "conflicted": 6,
            "terrified": 7,
            "betrayed": 9,
            "devastated": 9,
            "transformed": 10,
            "hostile": 5,
            "suspicious": 5,
            "trusting": 5,
            "friendly": 3,
            "reflective": 4,
        },
        "keyword_boosts": {
            7: ["death", "killed", "sacrifice"],
            5: ["secret", "betrayed", "trust"],
            3: ["gift", "helped", "fought"],
        },
        "disposition_map": {
            "hostile": "hostile",
            "neutral": "neutral",
            "friendly": "friendly",
            "wary": "distrustful",
            "curious": "neutral",
            "loyal": "loyal",
        },
    }


@pytest.fixture()
def stub_all(stub_engine: None, stub_emotions: None) -> None:
    """Combined stub: engine + emotions. Use for tests that need both."""


# ── Domain-config factories for tests ─────────────────────────

# Production domain-config dataclasses (GenreConstraints, CreationFlow, etc.)
# have no defaults on purpose — the parse layer enforces that every field is
# resolved via yaml + parent-chain. Tests that construct these objects in
# isolation (to exercise validator logic without a yaml) use these helpers
# to fill in the fields the test does not care about.


def make_genre_constraints(
    forbidden_terms: list[str] | None = None,
    forbidden_concepts: list[str] | None = None,
    genre_test: str = "",
    atmospheric_drift: list[str] | None = None,
    atmospheric_drift_threshold: int = 3,
):  # type: ignore[no-untyped-def]
    """Build a fully-specified GenreConstraints for tests."""
    from straightjacket.engine.datasworn.settings import GenreConstraints

    return GenreConstraints(
        forbidden_terms=forbidden_terms if forbidden_terms is not None else [],
        forbidden_concepts=forbidden_concepts if forbidden_concepts is not None else [],
        genre_test=genre_test,
        atmospheric_drift=atmospheric_drift if atmospheric_drift is not None else [],
        atmospheric_drift_threshold=atmospheric_drift_threshold,
    )
