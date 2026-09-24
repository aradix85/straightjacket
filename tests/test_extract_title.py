from __future__ import annotations

import pytest

from straightjacket.engine.datasworn.loader import extract_title


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ({"title": {"canonical": "Iron Vow", "standard": "Vow"}}, "Iron Vow"),
        ({"title": {"standard": "Sworn Vow"}}, "Sworn Vow"),
        ({"title": {}}, "fallback"),
        ({"title": "Plain Title"}, "Plain Title"),
        ({"title": "", "_id": "starforged/assets/path/ace_pilot"}, "Ace Pilot"),
        ({"_id": "classic/oracles/settlement_trouble"}, "Settlement Trouble"),
        ({}, "fallback"),
    ],
)
def test_extract_title_prefers_title_then_id_then_fallback(obj: dict[str, object], expected: str) -> None:
    assert extract_title(obj, "fallback") == expected
