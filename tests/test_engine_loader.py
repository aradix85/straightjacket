def test_miss_clock_ticks_cover_every_position(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    assert set(eng().clocks.miss_ticks_by_position) == set(eng().effect_resolver.position_weights)


def test_eng_returns_settings(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.engine_config import EngineSettings

    assert isinstance(eng(), EngineSettings)


def test_eng_is_cached(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    a = eng()
    b = eng()
    assert a is b
