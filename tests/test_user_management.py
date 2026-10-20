from pathlib import Path

import pytest

from straightjacket.engine import user_management
from straightjacket.engine.user_management import InvalidNameError, create_user, list_users


@pytest.fixture(autouse=True)
def users(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(user_management, "USERS_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("name", "folder"),
    [
        *((name, name) for name in ("Elvira", "ws_succ", "Kira-2", "Console", "Nullah", "con man", "Dr. Vos", "a..b")),
        ("  Anouk   van Dijk ", "Anouk van Dijk"),
    ],
)
def test_a_player_gets_a_folder_of_their_name_with_its_spaces_tidied(name: str, folder: str) -> None:
    create_user(name)
    assert list_users() == [{"name": folder}]


@pytest.mark.parametrize(
    "name",
    [
        *("D:", "D:elders", "Elvira:stream", "a?b", 'x"y', "a<b", "a|b", "a*b", "a\x01b", "a\x1fb", "a\tb", "a\x00b"),
        *("NUL", "CON", "con", "Prn", "AUX", "COM1", "lpt9", "NUL.json", "com¹"),
        *("naam.", "../evil/name", "a/b", "a\\b", ".", "..", ".hidden", "   "),
    ],
)
def test_a_name_the_file_system_would_refuse_or_alter_is_refused(name: str) -> None:
    with pytest.raises(InvalidNameError):
        create_user(name)
    assert list_users() == []
