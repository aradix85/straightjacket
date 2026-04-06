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
_lm.log = lambda *a, **k: None
_lm.setup_file_logging = lambda: None
_lm.get_logger = lambda component: type("_L", (), {
    "info": lambda self, *a: None, "debug": lambda self, *a: None,
    "warning": lambda self, *a: None, "error": lambda self, *a: None,
})()
_lm.get_save_dir = lambda username: Path("/tmp/straightjacket_test") / username / "saves"
_lm.load_global_config = lambda: {}
_lm.save_global_config = lambda cfg: None
_lm.load_user_config = lambda username: {}
_lm.save_user_config = lambda username, cfg: None
_lm.list_users = lambda: []
_lm.create_user = lambda name: True
_lm.delete_user = lambda name: True
sys.modules["straightjacket.engine.logging_util"] = _lm


# ── Reusable fixtures ────────────────────────────────────────

@pytest.fixture()
def load_engine():
    """Load real engine.yaml."""
    from straightjacket.engine import engine_loader
    engine_loader._eng = None
    engine_loader.eng()


@pytest.fixture()
def stub_engine():
    """Stub eng() with known values for predictable assertions."""
    from straightjacket.engine import engine_loader
    from straightjacket.engine.config_loader import _ConfigNode
    engine_loader._eng = _ConfigNode({
        "bonds": {"start": 0, "max": 4},
        "npc": {
            "max_active": 12, "reflection_threshold": 30,
            "max_memory_entries": 25, "max_observations": 15,
            "max_reflections": 8, "memory_recency_decay": 0.92,
            "activation_threshold": 0.7, "mention_threshold": 0.3,
            "max_activated": 3,
        },
        "activation_scores": {
            "target": 1.0, "name_match": 0.8, "name_part": 0.6,
            "alias_match": 0.7, "location_match": 0.3,
            "recent_interaction": 0.2, "max_recursive": 1,
        },
        "resources": {"health_max": 5, "spirit_max": 5, "supply_max": 5,
                       "health_start": 5, "spirit_start": 5, "supply_start": 5},
        "momentum": {"floor": -6, "max": 10, "start": 2,
                      "gain": {"weak_hit": 1, "strong_hit": {"standard": 2, "great": 3}},
                      "loss": {"risky": 2, "desperate": 3}},
        "chaos": {"min": 3, "max": 9, "start": 5, "interrupt_types": ["twist"]},
        "pacing": {"window_size": 5, "intense_threshold": 3, "calm_threshold": 2,
                    "max_narration_history": 5, "max_session_log": 50,
                    "director_interval": 3, "autonomous_clock_tick_chance": 0.20,
                    "weak_hit_clock_tick_chance": 0.50},
        "location": {"history_size": 5},
        "move_categories": {
            "combat": ["clash", "strike"],
            "social": ["compel", "make_connection", "test_bond"],
            "endure": ["endure_harm", "endure_stress"],
            "recovery": ["endure_harm", "endure_stress", "resupply"],
            "bond_on_weak_hit": ["make_connection"],
            "bond_on_strong_hit": ["make_connection", "compel", "test_bond"],
            "disposition_shift_on_strong_hit": ["make_connection", "test_bond"],
        },
        "disposition_shifts": {
            "hostile": "distrustful", "distrustful": "neutral",
            "neutral": "friendly", "friendly": "loyal",
        },
        "disposition_to_seed_emotion": {
            "hostile": "hostile", "distrustful": "suspicious",
            "neutral": "neutral", "friendly": "curious", "loyal": "trusting",
        },
    }, "engine")


@pytest.fixture()
def stub_emotions():
    """Stub emotions_loader with minimal importance map."""
    from straightjacket.engine import emotions_loader
    emotions_loader._data = {
        "importance": {
            "neutral": 2, "curious": 3, "angry": 5, "terrified": 7,
            "betrayed": 9, "devastated": 9, "transformed": 10,
            "hostile": 5, "suspicious": 5, "trusting": 5,
            "friendly": 3, "reflective": 4,
        },
        "keyword_boosts": {
            7: ["death", "killed", "sacrifice"],
            5: ["secret", "betrayed", "trust"],
            3: ["gift", "helped", "fought"],
        },
        "disposition_map": {
            "hostile": "hostile", "neutral": "neutral",
            "friendly": "friendly", "wary": "distrustful",
            "curious": "neutral", "loyal": "loyal",
        },
    }
