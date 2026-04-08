#!/usr/bin/env python3
"""Tests for engine logic: utilities, config, NPC processing.

Run: python -m pytest tests/test_engine.py -v
"""


# Stubs are set up in conftest.py

# ── _ConfigNode tests ────────────────────────────────────────


def test_confignode_dot_access() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"ai": {"model": "qwen", "temp": 0.7}}, "cfg")
    assert node.ai.model == "qwen"
    assert node.ai.temp == 0.7


def test_confignode_error_shows_path() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"ai": {"model": "qwen"}}, "cfg")
    try:
        _ = node.ai.brain_modle  # typo
        raise AssertionError("Should have raised")
    except AttributeError as e:
        msg = str(e)
        assert "cfg.ai.brain_modle" in msg
        assert "model" in msg  # shows available keys


def test_confignode_error_shows_available_keys() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"server": {"port": 8081}, "ai": {"model": "x"}}, "config")
    try:
        _ = node.database
        raise AssertionError("Should have raised")
    except AttributeError as e:
        msg = str(e)
        assert "config.database" in msg
        assert "ai" in msg
        assert "server" in msg


def test_confignode_getitem_error() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"a": 1}, "root")
    try:
        _ = node["b"]
        raise AssertionError("Should have raised")
    except KeyError as e:
        assert "root" in str(e)


def test_confignode_get_default() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"a": 1}, "root")
    assert node.get("a") == 1
    assert node.get("missing", 42) == 42


def test_confignode_contains() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"a": 1, "b": 2}, "root")
    assert "a" in node
    assert "c" not in node


def test_confignode_repr() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"x": 1}, "engine")
    r = repr(node)
    assert "engine" in r
    assert "x" in r


def test_confignode_nested_path_tracking() -> None:
    from straightjacket.engine.config_loader import _ConfigNode

    node = _ConfigNode({"a": {"b": {"c": 1}}}, "cfg")
    try:
        _ = node.a.b.typo
        raise AssertionError()
    except AttributeError as e:
        assert "cfg.a.b.typo" in str(e)


# ── locations_match tests ─────────────────────────────────────


def test_locations_match_identical() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("Tavern", "Tavern")


def test_locations_match_case_insensitive() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("Old Tavern", "old tavern")


def test_locations_match_stopwords() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("the dark forest", "dark forest")


def test_locations_match_subset() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("market square", "the old market square")


def test_locations_match_different() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert not locations_match("tavern", "castle")


def test_locations_match_empty() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("", "anywhere")
    assert locations_match("anywhere", "")


def test_locations_match_underscore() -> None:
    from straightjacket.engine.mechanics import locations_match

    assert locations_match("dark_forest", "dark forest")


# ── salvage_truncated_narration tests ─────────────────────────


def test_salvage_clean_text() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = "The door opened. She stepped inside."
    assert salvage_truncated_narration(text) == text


def test_salvage_strips_incomplete_game_data() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = 'The door opened. She stepped inside.<game_data>{"npcs": ['
    result = salvage_truncated_narration(text)
    assert "<game_data>" not in result
    assert "stepped inside." in result


def test_salvage_trims_mid_word() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = "The door opened. She stepped inside. The light was fadi"
    result = salvage_truncated_narration(text)
    assert result.endswith("inside.")


def test_salvage_preserves_complete_game_data() -> None:
    from straightjacket.engine.parser import salvage_truncated_narration

    text = 'Story text here.<game_data>{"npcs": []}</game_data>'
    result = salvage_truncated_narration(text)
    assert "<game_data>" in result


# ── NPC processing tests ──────────────────────────────────────


def _make_game_with_npcs():  # type: ignore[no-untyped-def]
    """Create a minimal GameState with some NPCs for processing tests."""
    from straightjacket.engine.models import GameState, NpcData

    game = GameState(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.npcs = [
        NpcData(id="npc_1", name="Kira Voss", disposition="friendly", bond=2, description="Tall woman with red hair"),
        NpcData(id="npc_2", name="Old Borin", disposition="neutral", bond=0, description="Grumpy dwarf blacksmith"),
    ]
    return game


def _stub_engine() -> None:
    """Stub eng() so processing.py can call eng().bonds.start etc."""
    from straightjacket.engine.config_loader import _ConfigNode
    from straightjacket.engine import engine_loader

    engine_loader._eng = _ConfigNode(
        {
            "bonds": {"start": 0, "max": 4},
            "npc": {
                "max_active": 12,
                "reflection_threshold": 30,
                "max_memory_entries": 25,
                "max_observations": 15,
                "max_reflections": 8,
                "memory_recency_decay": 0.92,
            },
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
        },
        "engine",
    )


def test_process_new_npcs_adds_npc() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()
    assert len(game.npcs) == 2

    process_new_npcs(game, [{"name": "Maren", "description": "Young scout", "disposition": "curious"}])

    assert len(game.npcs) == 3
    maren = next(n for n in game.npcs if n.name == "Maren")
    assert maren.description == "Young scout"
    assert maren.id == "npc_3"
    assert len(maren.memory) == 1  # seed memory


def test_process_new_npcs_skips_player_character() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Hero", "description": "The protagonist", "disposition": "neutral"}])

    assert len(game.npcs) == 2  # unchanged


def test_process_new_npcs_skips_existing() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Kira Voss", "description": "Same person", "disposition": "friendly"}])

    assert len(game.npcs) == 2  # no duplicate


def test_process_npc_renames_updates_name() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game_with_npcs()

    process_npc_renames(game, [{"npc_id": "npc_1", "new_name": "Kira von Asten"}])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira von Asten"
    assert "Kira Voss" in npc.aliases


def test_process_npc_renames_rejects_player_name() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game_with_npcs()

    process_npc_renames(game, [{"npc_id": "npc_1", "new_name": "Hero"}])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira Voss"  # unchanged


def test_process_npc_details_extends_surname() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game_with_npcs()

    # "Old Borin" gets a surname: "Old Borin Ironhand"
    process_npc_details(game, [{"npc_id": "npc_2", "full_name": "Old Borin Ironhand"}])

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert npc.name == "Old Borin Ironhand"
    assert "Old Borin" in npc.aliases


def test_process_npc_details_updates_description() -> None:
    _stub_engine()
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game_with_npcs()

    process_npc_details(
        game, [{"npc_id": "npc_2", "description": "Grumpy dwarf blacksmith with burn scars, secretly loyal."}]
    )

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert "burn scars" in npc.description


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
