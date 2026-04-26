from tests._helpers import make_game_state, make_npc


def _full_config_data(**overrides: object) -> dict:
    base = {
        "server": {"host": "127.0.0.1", "port": 8081},
        "language": {"narration_language": "English"},
        "ai": {
            "provider": "openai_compatible",
            "api_base": "",
            "api_key_env": "",
            "prompts_dir": "prompts",
            "clusters": {
                "classification": {
                    "model": "qwen",
                    "temperature": 0.5,
                    "top_p": 0.95,
                    "max_tokens": 8192,
                    "max_retries": 3,
                }
            },
            "role_cluster": {"recap": "classification"},
            "model_family": {"qwen": "qwen", "gpt-oss": "gpt_oss"},
        },
    }
    base.update(overrides)
    return base


def test_appconfig_typed_access() -> None:
    from straightjacket.engine.config_loader import _parse_config

    config = _parse_config(_full_config_data())
    assert config.ai.provider == "openai_compatible"
    assert config.ai.clusters["classification"].model == "qwen"
    assert config.ai.clusters["classification"].temperature == 0.5


def test_appconfig_strict_on_empty() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    with pytest.raises(KeyError):
        _parse_config({})


def test_cluster_all_fields_accessible() -> None:
    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    data["ai"]["clusters"] = {
        "analytical": {
            "model": "gpt-oss",
            "temperature": 0.3,
            "top_p": 0.95,
            "max_tokens": 4096,
            "max_retries": 2,
            "extra_body": {"foo": "bar"},
        }
    }
    data["ai"]["role_cluster"] = {"recap": "analytical"}
    config = _parse_config(data)
    c = config.ai.clusters["analytical"]
    assert c.model == "gpt-oss"
    assert c.temperature == 0.3
    assert c.top_p == 0.95
    assert c.max_tokens == 4096
    assert c.max_retries == 2
    assert c.extra_body == {"foo": "bar"}


def test_cluster_requires_all_fields() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    data["ai"]["clusters"] = {"creative": {"temperature": 0.9}}
    data["ai"]["role_cluster"] = {"recap": "creative"}
    with pytest.raises(ValueError, match="missing required fields"):
        _parse_config(data)


def test_role_cluster_override() -> None:
    from straightjacket.engine.config_loader import _parse_config

    config = _parse_config(_full_config_data())
    assert config.ai.role_cluster["recap"] == "classification"


def test_model_family_field_required() -> None:
    import pytest

    from straightjacket.engine.config_loader import _parse_config

    data = _full_config_data()
    del data["ai"]["model_family"]
    with pytest.raises(KeyError):
        _parse_config(data)


def test_model_family_for_model_resolves(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_model

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    assert model_family_for_model("qwen") == "qwen"
    assert model_family_for_model("gpt-oss") == "gpt_oss"


def test_model_family_for_model_raises_on_unknown(monkeypatch) -> None:
    import pytest

    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_model

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    with pytest.raises(ValueError, match="no family mapping"):
        model_family_for_model("some-other-model")


def test_model_family_for_role_chains(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_role

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)

    assert model_family_for_role("recap") == "qwen"


def test_narrator_model_family_convenience(monkeypatch) -> None:
    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, narrator_model_family

    data = _full_config_data()
    data["ai"]["clusters"]["narrator"] = {
        "model": "gpt-oss",
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 8192,
        "max_retries": 3,
    }
    data["ai"]["role_cluster"]["narrator"] = "narrator"
    config = _parse_config(data)
    monkeypatch.setattr(config_loader, "_cfg", config)
    assert narrator_model_family() == "gpt_oss"


def test_model_family_for_role_raises_on_unmapped_role(monkeypatch) -> None:
    import pytest

    from straightjacket.engine import config_loader
    from straightjacket.engine.config_loader import _parse_config, model_family_for_role

    config = _parse_config(_full_config_data())
    monkeypatch.setattr(config_loader, "_cfg", config)
    with pytest.raises(ValueError, match="no cluster assignment"):
        model_family_for_role("nonexistent_role")


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


def _make_game_with_npcs():
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.npcs = [
        make_npc(id="npc_1", name="Kira Voss", disposition="friendly", description="Tall woman with red hair"),
        make_npc(id="npc_2", name="Old Borin", disposition="neutral", description="Grumpy dwarf blacksmith"),
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
    assert len(maren.memory) == 1


def test_process_new_npcs_skips_player_character(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Hero", "description": "The protagonist", "disposition": "neutral"}])

    assert len(game.npcs) == 2


def test_process_new_npcs_skips_existing(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game_with_npcs()

    process_new_npcs(game, [{"name": "Kira Voss", "description": "Same person", "disposition": "friendly"}])

    assert len(game.npcs) == 2


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
    assert npc.name == "Kira Voss"


def test_process_npc_details_extends_surname(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game_with_npcs()

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
