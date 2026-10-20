import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.setting.packages import load_package
from tests._creation import TurnProvider, brain_answer, force_result, library_game
from tests._helpers import fix_dice


@pytest.fixture
def miss(monkeypatch: pytest.MonkeyPatch) -> None:
    force_result(monkeypatch, "MISS")


def test_an_automatic_roll_replaces_its_link(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_oracle

    fix_dice(monkeypatch, 81, 1, 1)
    assert roll_oracle(load_package("starforged"), "character/goal").text == "Abandon + Ability"


def test_roll_twice_takes_two_different_rows(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_oracle

    fix_dice(monkeypatch, 96, 1, 1, 6)
    assert roll_oracle(load_package("starforged"), "creature/encountered_behavior").text == "Ambusher; Apex predator"


def test_a_role_rolls_the_table_an_earlier_role_points_to(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.setting.oracle_rolls import plain_text, roll_generator_tables

    starforged, isles = load_package("starforged"), load_package("sundered_isles")
    fix_dice(monkeypatch, 1, 1)
    linked = roll_generator_tables(starforged, starforged.generator_tables("location"))
    feature = starforged.oracle_table("location_theme/chaotic/feature").rows[0].text
    assert linked == {"theme": "Chaotic", "feature": plain_text(feature)}
    fix_dice(monkeypatch, 1)
    named = roll_generator_tables(isles, isles.generator_tables("settlement"))
    assert named["location"] == "Shore"
    assert named["focus"] in {plain_text(row.text) for row in isles.oracle_table("settlement/focus/shore").rows}


def test_the_place_categories_are_registered(load_engine: None) -> None:
    generation = gm().generation
    assert "fact" in generation.categories
    assert set(generation.place_categories) <= set(generation.categories)
    assert gm().naming.category in generation.categories


@pytest.mark.parametrize("setting", ["classic", "delve", "starforged", "sundered_isles"])
def test_every_setting_rolls_every_entity_category(load_engine: None, setting: str) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_generator_tables
    from straightjacket.engine.setting.packages import load_package

    pkg = load_package(setting)
    for category in gm().generation.categories:
        if category == "fact":
            continue
        tables = pkg.generator_tables(category)
        for _ in range(40):
            results = roll_generator_tables(pkg, tables)
            assert list(results) == list(tables)
            assert all(value and "](" not in value for value in results.values()), results


def test_a_category_the_setting_lacks_raises(load_engine: None) -> None:
    from straightjacket.engine.setting.packages import load_package

    with pytest.raises(KeyError, match="No generator tables for 'encounter'"):
        load_package("classic").generator_tables("encounter")


def test_an_unregistered_category_raises(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.generation import generate_entity

    with pytest.raises(KeyError, match="Unknown generation category"):
        generate_entity(library_game(), "encounter")
    with pytest.raises(ValueError, match="generate_fact"):
        generate_entity(library_game(), "fact")


def test_an_npc_name_comes_from_the_setting_tables(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
    from straightjacket.engine.setting.packages import load_package

    game = library_game()
    [table] = load_package(game.setting_id).name_tables("npc").values()
    assert roll_oracle_name(game) in {row.text for row in table.rows}


def test_a_move_to_an_unknown_place_generates_it(load_engine: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    provider = TurnProvider(brain_answer(location_change={"name": "Archive Vault", "kind": "settlement"}))
    game = library_game()
    _n, _r, _o, _d = process_turn(provider, game, "I slip past Mira into the archive vault", stream=None)

    [place] = game.world.places
    assert place.name == "Archive Vault"
    assert place.entity.category == "settlement"
    assert list(place.entity.results) == ["trouble"]
    assert '<generated category="settlement" place="Archive Vault">' in provider.prompts[-1]
    assert f'<detail role="trouble">{place.entity.results["trouble"]}</detail>' in provider.prompts[-1]


def test_a_place_already_seen_is_not_generated(load_engine: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    game = library_game()
    game.world.location_history = ["Archive Vault"]
    provider = TurnProvider(brain_answer())
    _n, _r, _o, _d = process_turn(provider, game, "I go back to the vault", stream=None)

    assert game.world.current_location == "Archive Vault"
    assert game.world.places == []
    assert "<generated" not in provider.prompts[-1]


def test_staying_put_generates_nothing(load_engine: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    provider = TurnProvider(brain_answer(location_change=None))
    game = library_game()
    _n, _r, _o, _d = process_turn(provider, game, "I search the shelves", stream=None)
    assert game.world.places == []


def test_a_misread_correction_keeps_the_generated_place(load_engine: None, miss: None) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn

    provider = TurnProvider(brain_answer(), brain_answer(stat="iron"))
    game = library_game()
    _n, _r, _o, _d = process_turn(provider, game, "I slip into the vault", stream=None)
    before = [p.to_dict() for p in game.world.places]
    _narration, _offer, _director = process_correction(provider, game, "I meant I use force")

    assert [p.to_dict() for p in game.world.places] == before


def test_a_roll_twice_row_keeps_or_worsens_a_repeated_result(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_rows

    weapons = load_package("sundered_isles").oracle_table("character/trademark_weapons")
    fix_dice(monkeypatch, 98, 1, 1)
    kept = roll_rows(weapons)
    twist = load_package("classic").oracle_table("turning_point/major_plot_twist")
    fix_dice(monkeypatch, 96, 1, 1)
    worse = roll_rows(twist)
    assert ([row.text for row in kept.rows], kept.worse) == (["Barbed gaff hook", "Barbed gaff hook"], False)
    assert ([row.text for row in worse.rows], worse.worse) == (["It was all a diversion."], True)
