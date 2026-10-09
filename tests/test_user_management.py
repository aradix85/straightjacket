import pytest

from straightjacket.engine.user_management import InvalidNameError, _safe_name


@pytest.mark.parametrize(
    "name", ["Elvira", "ws_succ", "Anouk van Dijk", "Kira-2", "Console", "Nullah", "con man", "Dr. Vos", "a..b"]
)
def test_ordinary_names_pass(name: str) -> None:
    assert _safe_name(name) == name


def test_surrounding_and_repeated_spaces_are_normalised() -> None:
    assert _safe_name("  Anouk   van Dijk ") == "Anouk van Dijk"


@pytest.mark.parametrize(
    "name", ["D:", "D:elders", "Elvira:stream", "a?b", 'x"y', "a<b", "a|b", "a*b", "a\x01b", "a\x1fb", "a\tb", "a\x00b"]
)
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


@pytest.mark.parametrize("name", ["../evil/name", "a/b", "a\\b", ".", "..", ".hidden", "   "])
def test_names_that_would_be_altered_into_another_name_raise(name: str) -> None:
    with pytest.raises(InvalidNameError):
        _safe_name(name)


def test_invalid_name_error_is_a_value_error() -> None:
    assert issubclass(InvalidNameError, ValueError)
