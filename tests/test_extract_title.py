from __future__ import annotations


def test_path_and_asset_titles_are_the_datasworn_names(load_engine: None) -> None:
    from straightjacket.engine.setting.packages import load_package
    from straightjacket.web.serializers import build_creation_options

    for setting in build_creation_options()["settings"]:
        data = load_package(setting["id"]).data
        assert {p["title"] for p in setting["paths"]} == {a["name"] for a in data.paths()}
        assert all(a["title"] == data.asset(a["category"], a["id"])["name"] for a in setting["starting_assets"])


def test_an_oracle_tables_title_is_its_datasworn_name(load_engine: None) -> None:
    from straightjacket.engine.ruleset.moves import get_moves

    assert get_moves("classic")["fate/pay_the_price"].tables["pay_the_price"].title == "Pay the Price"
