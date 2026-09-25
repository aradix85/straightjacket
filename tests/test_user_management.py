import pytest

from straightjacket.engine.user_management import InvalidNameError, _safe_name


@pytest.mark.parametrize("name", ["Elvira", "ws_succ", "Anouk van Dijk", "Kira-2", "Console", "Nullah", "con man"])
def test_ordinary_names_pass(name: str) -> None:
    assert _safe_name(name) == name


@pytest.mark.parametrize("name", ["D:", "D:elders", "Elvira:stream", "a?b", 'x"y', "a<b", "a|b", "a*b", "a\x01b"])
def test_names_with_characters_windows_refuses_raise(name: str) -> None:
    with pytest.raises(InvalidNameError):
        _safe_name(name)


@pytest.mark.parametrize("name", ["NUL", "CON", "con", "Prn", "AUX", "COM1", "lpt9", "NUL.json", "com¹"])
def test_reserved_device_names_raise(name: str) -> None:
    with pytest.raises(InvalidNameError):
        _safe_name(name)


def test_a_trailing_dot_raises_instead_of_colliding_with_the_name_without_it() -> None:
    with pytest.raises(InvalidNameError):
        _safe_name("naam.")


def test_path_separators_are_still_stripped() -> None:
    assert _safe_name("../evil/name") == "evilname"


def test_invalid_name_error_is_a_value_error() -> None:
    assert issubclass(InvalidNameError, ValueError)
