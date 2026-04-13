#!/usr/bin/env python3
"""Tests for engine logic: utilities, config, NPC processing.

Run: python -m pytest tests/test_engine.py -v
"""


# Stubs are set up in conftest.py

# ── AppConfig tests ──────────────────────────────────────────


def test_appconfig_typed_access() -> None:
    from straightjacket.engine.config_loader import _parse_config

    data = {
        "ai": {
            "provider": "openai_compatible",
            "clusters": {
                "classification": {
                    "model": "qwen",
                    "temperature": 0.5,
                    "top_p": 0.95,
                    "max_tokens": 8192,
                    "max_retries": 3,
                    "max_tool_rounds": 0,
                }
            },
            "temperature": {"brain": 0.6},
        }
    }
    config = _parse_config(data)
    assert config.ai.provider == "openai_compatible"
    assert config.ai.clusters["classification"].model == "qwen"
    assert config.ai.temperature.get("brain") == 0.6


def test_appconfig_defaults() -> None:
    from straightjacket.engine.config_loader import _parse_config

    config = _parse_config({})
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8081
    assert config.language.narration_language == "English"
    assert config.ai.prompts_file == "prompts.yaml"


def test_appconfig_per_role_int() -> None:
    from straightjacket.engine.config_loader import _parse_config

    data = {"ai": {"max_tokens": {"brain": 4096, "narrator": 2048}}}
    config = _parse_config(data)
    assert config.ai.max_tokens["brain"] == 4096
    assert config.ai.max_tokens["narrator"] == 2048
    assert "architect" not in config.ai.max_tokens  # no hidden defaults


def test_appconfig_per_role_float_missing() -> None:
    from straightjacket.engine.config_loader import _parse_config

    data = {"ai": {"temperature": {"brain": 0.6}}}
    config = _parse_config(data)
    assert config.ai.temperature["brain"] == 0.6
    assert "narrator" not in config.ai.temperature  # no hidden defaults


def test_appconfig_extra_body() -> None:
    from straightjacket.engine.config_loader import _parse_config

    # Per-role extra_body overrides
    data = {"ai": {"extra_body": {"narrator": {"reasoning_effort": "none"}, "validator": {}}}}
    config = _parse_config(data)
    assert config.ai.extra_body["narrator"] == {"reasoning_effort": "none"}
    assert config.ai.extra_body["validator"] == {}
    assert "brain" not in config.ai.extra_body  # not configured = not present


def test_cluster_requires_all_fields() -> None:
    from straightjacket.engine.config_loader import _parse_config
    import pytest

    # Missing model field should raise
    data = {"ai": {"clusters": {"creative": {"temperature": 0.9}}}}
    with pytest.raises(ValueError, match="missing required fields"):
        _parse_config(data)


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
        NpcData(id="npc_1", name="Kira Voss", disposition="friendly", description="Tall woman with red hair"),
        NpcData(id="npc_2", name="Old Borin", disposition="neutral", description="Grumpy dwarf blacksmith"),
    ]
    return game


def test_process_new_npcs_adds_npc(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()
    assert len(game.npcs) == 2

    process_new_npcs(game, [{"name": "Maren", "description": "Young scout", "disposition": "curious"}])

    assert len(game.npcs) == 3
    maren = next(n for n in game.npcs if n.name == "Maren")
    assert maren.description == "Young scout"
    assert maren.id == "npc_3"
    assert len(maren.memory) == 1  # seed memory


def test_process_new_npcs_skips_player_character(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Hero", "description": "The protagonist", "disposition": "neutral"}])

    assert len(game.npcs) == 2  # unchanged


def test_process_new_npcs_skips_existing(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Kira Voss", "description": "Same person", "disposition": "friendly"}])

    assert len(game.npcs) == 2  # no duplicate


def test_process_npc_renames_updates_name(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game_with_npcs()

    process_npc_renames(game, [{"npc_id": "npc_1", "new_name": "Kira von Asten"}])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira von Asten"
    assert "Kira Voss" in npc.aliases


def test_process_npc_renames_rejects_player_name(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game_with_npcs()

    process_npc_renames(game, [{"npc_id": "npc_1", "new_name": "Hero"}])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira Voss"  # unchanged


def test_process_npc_details_extends_surname(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game_with_npcs()

    # "Old Borin" gets a surname: "Old Borin Ironhand"
    process_npc_details(game, [{"npc_id": "npc_2", "full_name": "Old Borin Ironhand"}])

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert npc.name == "Old Borin Ironhand"
    assert "Old Borin" in npc.aliases


def test_process_npc_details_updates_description(stub_engine: None) -> None:
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
