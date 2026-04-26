import pytest

from straightjacket.engine.engine_config import EngineSettings


def _make_settings_with_raw(raw_validator: dict) -> EngineSettings:
    settings = EngineSettings.__new__(EngineSettings)
    settings._raw = {"validator": raw_validator}
    settings._compiled_patterns = {}
    return settings


def test_compiled_patterns_for_family_universal_only_when_overlays_empty() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\byou realize\b", r"\byou know\b"],
            "agency_patterns_overlays": {},
        }
    )
    patterns = s.compiled_patterns_for_family("validator", "agency_patterns", "glm")
    assert len(patterns) == 2


def test_compiled_patterns_for_family_combines_universal_and_overlay() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\byou realize\b"],
            "agency_patterns_overlays": {
                "glm": [r"\byou somehow\b", r"\byou inexplicably\b"],
            },
        }
    )
    patterns = s.compiled_patterns_for_family("validator", "agency_patterns", "glm")
    assert len(patterns) == 3

    assert patterns[0].search("you realize the truth")
    assert patterns[1].search("you somehow know")


def test_compiled_patterns_for_family_unknown_family_returns_universal() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\byou realize\b"],
            "agency_patterns_overlays": {"glm": [r"\byou somehow\b"]},
        }
    )

    patterns = s.compiled_patterns_for_family("validator", "agency_patterns", "qwen")
    assert len(patterns) == 1


def test_compiled_patterns_for_family_empty_overlay_list_returns_universal() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\byou realize\b"],
            "agency_patterns_overlays": {"glm": []},
        }
    )
    patterns = s.compiled_patterns_for_family("validator", "agency_patterns", "glm")
    assert len(patterns) == 1


def test_compiled_patterns_for_family_missing_universal_raises() -> None:
    s = _make_settings_with_raw({"agency_patterns_overlays": {"glm": [r"\byou somehow\b"]}})
    with pytest.raises(KeyError):
        s.compiled_patterns_for_family("validator", "agency_patterns", "glm")


def test_compiled_patterns_for_family_missing_overlays_dict_raises() -> None:
    s = _make_settings_with_raw({"agency_patterns_universal": [r"\byou realize\b"]})
    with pytest.raises(KeyError):
        s.compiled_patterns_for_family("validator", "agency_patterns", "glm")


def test_compiled_patterns_for_family_missing_section_raises() -> None:
    s = _make_settings_with_raw({"agency_patterns_universal": [], "agency_patterns_overlays": {}})
    with pytest.raises(KeyError):
        s.compiled_patterns_for_family("nonexistent", "agency_patterns", "glm")


def test_compiled_patterns_for_family_caches_overlay_per_family() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\byou realize\b"],
            "agency_patterns_overlays": {"glm": [r"\byou somehow\b"]},
        }
    )
    p1 = s.compiled_patterns_for_family("validator", "agency_patterns", "glm")
    p2 = s.compiled_patterns_for_family("validator", "agency_patterns", "glm")

    assert p1[0] is p2[0]
    assert p1[1] is p2[1]


def test_compiled_patterns_for_family_new_family_works_yaml_only() -> None:
    s = _make_settings_with_raw(
        {
            "agency_patterns_universal": [r"\buniversal_marker\b"],
            "agency_patterns_overlays": {
                "deepseek": [r"\bdeepseek_marker\b"],
                "kimi": [r"\bkimi_marker\b"],
            },
        }
    )
    p_deepseek = s.compiled_patterns_for_family("validator", "agency_patterns", "deepseek")
    p_kimi = s.compiled_patterns_for_family("validator", "agency_patterns", "kimi")
    assert len(p_deepseek) == 2
    assert len(p_kimi) == 2
    assert p_deepseek[1].search("deepseek_marker hits")
    assert p_kimi[1].search("kimi_marker hits")
