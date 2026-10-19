from typing import Any

import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.setting.loader import OracleTable, Setting
from tests._creation import force_miss
from tests.test_correction_replay import _Provider as _ReplayProvider
from tests.test_momentum_burn import _brain, _game, _Provider


@pytest.fixture
def miss(monkeypatch: pytest.MonkeyPatch) -> None:
    force_miss(monkeypatch)


def _row(low: int, text: str, rolls: list[dict[str, Any]]) -> dict[str, Any]:
    return {"roll": {"min": low, "max": low}, "text": text, "oracle_rolls": rolls}


def _auto(oracle: str | None, times: int = 1) -> dict[str, Any]:
    return {"oracle": oracle, "auto": True, "number_of_rolls": times, "duplicates": "reroll", "dice": None}


class _Pkg:
    id = "probe"

    def __init__(self) -> None:
        pair = "[A](datasworn:oracle_rollable:probe/t/a) + [B](datasworn:oracle_rollable:probe/t/b)"
        self.data = Setting(
            {
                "_id": "probe",
                "type": "ruleset",
                "truths": {},
                "oracles": {
                    "t": {
                        "contents": {
                            "pair": {
                                "name": "Probe",
                                "rows": [
                                    _row(
                                        1,
                                        pair,
                                        [_auto("oracle_rollable:probe/t/a"), _auto("oracle_rollable:probe/t/b")],
                                    )
                                ],
                            },
                            "a": {"name": "Probe", "rows": [_row(1, "Alpha", [])]},
                            "b": {"name": "Probe", "rows": [_row(1, "Beta", [])]},
                            "twice": {
                                "name": "Probe",
                                "rows": [
                                    _row(1, "Roll twice", [_auto(None, 2)]),
                                    _row(2, "One", []),
                                    _row(3, "Two", []),
                                ],
                            },
                            "type": {
                                "name": "Probe",
                                "rows": [_row(1, "[Ruined](datasworn:oracle_collection:probe/t/ruined)", [])],
                            },
                            "kind": {"name": "Probe", "rows": [_row(1, "Shore", [])]},
                        },
                        "collections": {
                            "ruined": {"contents": {"feature": {"name": "Probe", "rows": [_row(1, "Rubble", [])]}}},
                            "shore": {"contents": {"feature": {"name": "Probe", "rows": [_row(1, "Driftwood", [])]}}},
                        },
                    }
                },
            }
        )

    def oracle_table(self, path: str) -> OracleTable:
        table = self.data.oracle(path)
        if table is None:
            raise KeyError(path)
        return table


def test_an_automatic_roll_replaces_its_link(load_engine: None) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_oracle

    assert roll_oracle(_Pkg(), "t/pair").text == "Alpha + Beta"


def test_roll_twice_takes_two_different_rows(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.setting import loader
    from straightjacket.engine.setting.oracle_rolls import roll_oracle

    dice = iter([1, 2, 2, 3])
    monkeypatch.setattr(loader.random, "randint", lambda low, high: next(dice))
    assert roll_oracle(_Pkg(), "t/twice").text == "One; Two"


def test_a_role_rolls_the_table_an_earlier_role_points_to(load_engine: None) -> None:
    from straightjacket.engine.setting.oracle_rolls import roll_generator_tables

    linked = {"theme": "t/type", "feature": "t/{theme}/feature"}
    named = {"kind": "t/kind", "feature": "t/{kind}/feature"}
    assert roll_generator_tables(_Pkg(), linked) == {"theme": "Ruined", "feature": "Rubble"}
    assert roll_generator_tables(_Pkg(), named) == {"kind": "Shore", "feature": "Driftwood"}


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
        generate_entity(_game(), "encounter")
    with pytest.raises(ValueError, match="generate_fact"):
        generate_entity(_game(), "fact")


def test_an_npc_name_comes_from_the_setting_tables(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
    from straightjacket.engine.setting.packages import load_package

    game = _game()
    [table] = load_package(game.setting_id).name_tables("npc").values()
    assert roll_oracle_name(game) in {row.text for row in table.rows}


def test_a_move_to_an_unknown_place_generates_it(load_engine: None, stub_emotions: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    provider = _Provider(_brain(location_change={"name": "Archive Vault", "kind": "settlement"}))
    game = _game()
    _n, _r, _o, _d = process_turn(provider, game, "I slip past Mira into the archive vault", stream=None)

    [place] = game.world.places
    assert place.name == "Archive Vault"
    assert place.entity.category == "settlement"
    assert list(place.entity.results) == ["trouble"]
    assert '<generated category="settlement" place="Archive Vault">' in provider.prompts[-1]
    assert f'<detail role="trouble">{place.entity.results["trouble"]}</detail>' in provider.prompts[-1]


def test_a_place_already_seen_is_not_generated(load_engine: None, stub_emotions: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    game = _game()
    game.world.location_history = ["Archive Vault"]
    provider = _Provider(_brain())
    _n, _r, _o, _d = process_turn(provider, game, "I go back to the vault", stream=None)

    assert game.world.current_location == "Archive Vault"
    assert game.world.places == []
    assert "<generated" not in provider.prompts[-1]


def test_staying_put_generates_nothing(load_engine: None, stub_emotions: None, miss: None) -> None:
    from straightjacket.engine.game import process_turn

    provider = _Provider(_brain(location_change=None))
    game = _game()
    _n, _r, _o, _d = process_turn(provider, game, "I search the shelves", stream=None)
    assert game.world.places == []


def test_a_misread_correction_keeps_the_generated_place(load_engine: None, stub_emotions: None, miss: None) -> None:
    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn

    provider = _ReplayProvider(_brain(), _brain(stat="iron"))
    game = _game()
    _n, _r, _o, _d = process_turn(provider, game, "I slip into the vault", stream=None)
    before = [p.to_dict() for p in game.world.places]
    _narration, _offer, _director = process_correction(provider, game, "I meant I use force")

    assert [p.to_dict() for p in game.world.places] == before


def test_a_roll_twice_row_keeps_or_worsens_a_repeated_result(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.setting import loader
    from straightjacket.engine.setting.loader import OracleRow, OracleTable
    from straightjacket.engine.setting.oracle_rolls import roll_rows

    outcomes = {}
    for rule in ("keep", "make_it_worse"):
        twice = OracleRow(min=1, max=1, text="Roll twice", oracle_rolls=[{**_auto(None, 2), "duplicates": rule}])
        rows = [twice, OracleRow(min=2, max=2, text="One"), OracleRow(min=3, max=3, text="Two")]
        dice = [1, 2, 2]
        monkeypatch.setattr(loader.random, "randint", lambda low, high, queue=dice: queue.pop(0))
        rolled = roll_rows(OracleTable(id="t/twice", title="Twice", rows=rows))
        outcomes[rule] = ([row.text for row in rolled.rows], rolled.worse)
    assert outcomes == {"keep": (["One", "One"], False), "make_it_worse": (["One"], True)}


def test_an_unknown_duplicates_rule_raises(load_engine: None) -> None:
    from straightjacket.engine.setting.loader import OracleRow, OracleTable
    from straightjacket.engine.setting.oracle_rolls import roll_rows

    twice = OracleRow(min=1, max=1, text="Roll twice", oracle_rolls=[{**_auto(None, 2), "duplicates": "merge"}])
    with pytest.raises(ValueError, match="merge"):
        roll_rows(OracleTable(id="t/twice", title="Twice", rows=[twice]))
