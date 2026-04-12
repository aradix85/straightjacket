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
_lm.get_save_dir = lambda username: Path("/tmp/straightjacket_test") / username / "saves"  # type: ignore[attr-defined]
_lm._safe_name = lambda name: (  # type: ignore[attr-defined]
    name.replace("/", "").replace("\\", "").replace("\0", "").replace("..", "").strip() or "invalid"
)
_lm.load_global_config = lambda: {}  # type: ignore[attr-defined]
_lm.save_global_config = lambda cfg: None  # type: ignore[attr-defined]
_lm.load_user_config = lambda username: {}  # type: ignore[attr-defined]
_lm.save_user_config = lambda username, cfg: None  # type: ignore[attr-defined]
_lm.list_users = lambda: []  # type: ignore[attr-defined]
_lm.create_user = lambda name: True  # type: ignore[attr-defined]
_lm.delete_user = lambda name: True  # type: ignore[attr-defined]
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
    """Stub eng() with known values for predictable assertions."""
    from straightjacket.engine import engine_loader
    from straightjacket.engine.engine_config import parse_engine_yaml

    engine_loader._eng = parse_engine_yaml(
        {
            "bonds": {"start": 0, "max": 4},
            "npc": {
                "max_active": 12,
                "reflection_threshold": 30,
                "max_memory_entries": 25,
                "max_observations": 15,
                "max_reflections": 8,
                "memory_recency_decay": 0.92,
                "activation_threshold": 0.7,
                "mention_threshold": 0.3,
                "max_activated": 3,
                "reflection_importance": 8,
                "death_corroboration_min_importance": 9,
                "seed_importance_floor": 3,
                "reflection_recency_floor": 0.6,
                "about_npc_relevance_boost": 0.6,
                "consolidation_recency_ratio": 0.6,
                "monologue_max_chars": 200,
                "description_max_chars": 200,
                "arc_max_chars": 300,
                "gate_memory_counts": {0: 0, 1: 0, 2: 3, 3: 5, 4: 5},
                "activated_memory_count": 2,
            },
            "activation_scores": {
                "target": 1.0,
                "name_match": 0.8,
                "name_part": 0.6,
                "alias_match": 0.7,
                "location_match": 0.3,
                "recent_interaction": 0.2,
                "max_recursive": 1,
            },
            "resources": {
                "health_max": 5,
                "spirit_max": 5,
                "supply_max": 5,
                "health_start": 5,
                "spirit_start": 5,
                "supply_start": 5,
            },
            "momentum": {
                "floor": -6,
                "max": 10,
                "start": 2,
                "gain": {"weak_hit": 1, "strong_hit": {"standard": 2, "great": 3}},
                "loss": {"risky": 2, "desperate": 3},
            },
            "chaos": {"min": 3, "max": 9, "start": 5, "interrupt_types": ["twist"]},
            "pacing": {
                "window_size": 5,
                "intense_threshold": 3,
                "calm_threshold": 2,
                "max_narration_history": 5,
                "max_session_log": 50,
                "director_interval": 3,
                "autonomous_clock_tick_chance": 0.20,
                "weak_hit_clock_tick_chance": 0.50,
                "fired_clock_keep_scenes": 3,
            },
            "location": {"history_size": 5},
            "move_categories": {
                "combat": ["combat/clash", "combat/strike"],
                "social": ["adventure/compel", "connection/make_a_connection", "connection/test_your_relationship"],
                "endure": ["suffer/endure_harm", "suffer/endure_stress"],
                "recovery": ["suffer/endure_harm", "suffer/endure_stress", "recover/resupply"],
            },
            "disposition_shifts": {
                "hostile": "distrustful",
                "distrustful": "neutral",
                "neutral": "friendly",
                "friendly": "loyal",
            },
            "disposition_to_seed_emotion": {
                "hostile": "hostile",
                "distrustful": "suspicious",
                "neutral": "neutral",
                "friendly": "curious",
                "loyal": "trusting",
            },
            "death_emotions": ["betrayed", "devastated"],
            "narrative_direction": {
                "intensity": {"critical_below": 1, "high_below": 3, "moderate_below": 4},
                "result_map": {
                    "MISS": {"tempo": "slow", "perspective": "sensory_loss"},
                    "WEAK_HIT": {"tempo": "moderate", "perspective": "action_detail"},
                    "STRONG_HIT": {"tempo": "brisk", "perspective": "action_detail"},
                    "dialog": {"tempo": "measured", "perspective": "dialogue_rhythm"},
                    "_default": {"tempo": "moderate", "perspective": "action_detail"},
                },
            },
            "story": {
                "kishotenketsu_probability": {"dark_gritty": 0.15},
                "kishotenketsu_default": 0.50,
            },
            "creativity_seeds": ["amber", "glacier", "compass", "obsidian", "cedar"],
            "scene_range_default": [1, 20],
            "position_resolver": {
                "desperate_below": -3,
                "controlled_above": 3,
                "weights": {
                    "resource_critical_below": 2,
                    "resource_low_below": 3,
                    "resource_critical": -2,
                    "resource_low": -1,
                    "npc_hostile": -2,
                    "npc_distrustful": -1,
                    "npc_friendly": 1,
                    "npc_loyal": 2,
                    "npc_bond_high": 1,
                    "npc_bond_low": -1,
                    "chaos_high": -1,
                    "chaos_low": 1,
                    "consecutive_misses": -2,
                    "consecutive_strong": 1,
                    "threat_clock_critical": -1,
                    "secured_advantage": 2,
                },
                "move_baselines": {"combat": -1, "social": 0, "endure": 0, "recovery": 1, "other": 0},
                "overrides": [],
            },
            "effect_resolver": {
                "limited_below": -2,
                "great_above": 2,
                "weights": {"desperate": -1, "controlled": 1, "bond_high": 1, "bond_low": -1, "secured_advantage": 1},
                "move_baselines": {"combat/strike": 1, "other": 0},
            },
            "time_progression_map": {
                "dialog": "none",
                "adventure/gather_information": "short",
                "adventure/face_danger": "short",
                "combat/clash": "short",
                "combat/strike": "short",
                "recover/resupply": "moderate",
                "_with_location_change": "long",
                "_default": "short",
            },
            "memory_templates": {
                "action": "scene {scene}: {player} {move_verb} — {result_text}",
                "action_targeted": "scene {scene}: {player} {move_verb} involving {npc} — {result_text}",
                "dialog": "scene {scene}: {player} spoke with {npc} about {intent}",
                "dialog_no_target": "scene {scene}: {player} engaged in conversation — {intent}",
            },
            "memory_result_text": {
                "combat_MISS": "it went badly",
                "combat_STRONG_HIT": "struck true",
                "social_MISS": "was rebuffed",
                "social_STRONG_HIT": "connected",
                "other_MISS": "failed",
                "other_STRONG_HIT": "succeeded",
                "dialog": "exchanged words",
            },
            "memory_move_verbs": {
                "adventure/face_danger": "faced danger",
                "combat/clash": "fought",
                "combat/strike": "attacked",
                "adventure/compel": "pressed someone",
                "dialog": "spoke",
                "_default": "acted",
            },
            "scene_context_template": "{result} on {move_label} at {location} — {npc_summary}",
            "scene_context_dialog": "conversation at {location} with {npc_summary}",
            "enums": {
                "time_phases": [
                    "early_morning",
                    "morning",
                    "midday",
                    "afternoon",
                    "evening",
                    "late_evening",
                    "night",
                    "deep_night",
                ],
                "npc_statuses": ["active", "background", "deceased", "lore"],
                "dispositions": ["hostile", "distrustful", "neutral", "friendly", "loyal"],
                "memory_types": ["observation", "reflection"],
                "clock_types": ["threat", "scheme", "progress"],
                "thread_types": ["vow", "goal", "tension", "subplot"],
                "story_structures": ["3act", "kishotenketsu"],
                "positions": ["controlled", "risky", "desperate"],
            },
            "memory_retrieval_weights": {
                "recency": 0.40,
                "importance": 0.35,
                "relevance": 0.25,
            },
            "opening": {
                "time_of_day": "morning",
                "clock_segments": 6,
                "clock_filled": 1,
                "clock_fallback_name": "Looming threat",
                "clock_trigger_template": "Threat escalates beyond {player}'s control",
            },
            "move_routing": {
                "miss_endure": {"suffer/endure_harm": "health", "suffer/endure_stress": "spirit"},
                "recovery": {
                    "suffer/endure_harm": {"track": "health", "cap": "health_max"},
                    "suffer/endure_stress": {"track": "spirit", "cap": "spirit_max"},
                    "recover/resupply": {"track": "supply", "cap": "supply_max"},
                },
            },
            "architect": {
                "forbidden_moods": [
                    "surreal",
                    "disorienting",
                    "revelatory",
                    "haunted",
                    "spectral",
                    "ethereal",
                    "otherworldly",
                    "eldritch",
                    "supernatural",
                    "dreamlike",
                    "hallucinatory",
                    "phantasmagoric",
                    "uncanny",
                ],
            },
        }
    )


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
