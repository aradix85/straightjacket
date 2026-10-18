import pytest

from straightjacket import i18n


def test_a_string_without_a_value_for_its_placeholder_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "_strings", {"advance.upgraded": "{asset} upgraded for {cost}."})
    with pytest.raises(KeyError, match="cost"):
        i18n.t("advance.upgraded", asset="Blade")


def test_a_string_is_filled_with_its_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "_strings", {"advance.upgraded": "{asset} upgraded for {cost}."})
    assert i18n.t("advance.upgraded", asset="Blade", cost=2) == "Blade upgraded for 2."


def test_a_strings_file_with_a_value_that_is_not_text_stops_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine import yaml_merge

    monkeypatch.setattr(i18n, "_strings", None)
    monkeypatch.setattr(yaml_merge, "load_yaml_dir", lambda directory, missing_dir_hint: {"ui.send": "Send", "ui.n": 3})
    with pytest.raises(ValueError, match=r"'ui\.n'"):
        i18n.t("ui.send")
