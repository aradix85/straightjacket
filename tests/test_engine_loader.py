import pytest


def test_damage_returns_int_for_position_dict(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import damage

    assert damage("damage.miss.endure", "risky") == 1
    assert damage("damage.miss.endure", "desperate") == 2


def test_damage_returns_int_for_direct_numeric(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import damage

    assert damage("damage.miss.social.bond") == 1


def test_damage_default_position_is_risky(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import damage

    assert damage("damage.miss.combat") == 2


def test_damage_unknown_position_raises(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import damage

    with pytest.raises(KeyError, match="no entry for position"):
        damage("damage.miss.endure", "absurd_position")


def test_damage_unknown_category_raises(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import damage

    with pytest.raises(KeyError):
        damage("damage.miss.does_not_exist")


def test_eng_returns_settings(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.engine_config import EngineSettings

    assert isinstance(eng(), EngineSettings)


def test_eng_is_cached(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    a = eng()
    b = eng()
    assert a is b
