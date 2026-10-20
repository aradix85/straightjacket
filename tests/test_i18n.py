from pathlib import Path

import pytest

from straightjacket import i18n


@pytest.fixture
def strings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    strings_file = tmp_path / "strings" / "test.yaml"
    strings_file.parent.mkdir()
    monkeypatch.setattr(i18n, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(i18n, "_strings", None)
    return strings_file


def test_a_string_is_filled_with_its_values_and_raises_without_one(strings: Path) -> None:
    strings.write_text('advance.upgraded: "{asset} upgraded for {cost}."\n', encoding="utf-8")
    assert i18n.t("advance.upgraded", asset="Blade", cost=2) == "Blade upgraded for 2."
    with pytest.raises(KeyError, match="cost"):
        i18n.t("advance.upgraded", asset="Blade")


def test_a_strings_file_with_a_value_that_is_not_text_stops_loading(strings: Path) -> None:
    strings.write_text('ui.send: "Send"\nui.n: 3\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"'ui\.n'"):
        i18n.t("ui.send")
