import asyncio
from pathlib import Path
from typing import Any

import pytest

from straightjacket.web.session import Session, new_session
from tests._helpers import make_game_state


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def fake_ws() -> _FakeWS:
    return _FakeWS()


@pytest.fixture
def session(load_engine: None) -> Session:
    return new_session()


@pytest.fixture
def users(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path)
    return tmp_path


def test_a_new_players_name_is_trimmed(session: Session, fake_ws: _FakeWS, users: Path) -> None:
    from straightjacket.web.handlers import handle_create_player

    _run(handle_create_player(session, fake_ws, {"name": "  Alice  "}))
    selected = next(m for m in fake_ws.sent if m["type"] == "player_selected")
    assert selected["name"] == "Alice"
    assert [p.name for p in users.iterdir()] == ["Alice"]


@pytest.mark.parametrize("msg", [{}, {"name": 42}, {"name": "   "}, {"name": ""}])
def test_a_new_player_without_a_name_is_refused(
    session: Session, fake_ws: _FakeWS, users: Path, msg: dict[str, Any]
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web.handlers import handle_create_player

    _run(handle_create_player(session, fake_ws, msg))
    assert fake_ws.sent == [{"type": "error", "text": t("error.empty_player_name")}]
    assert list(users.iterdir()) == []


def test_a_closed_connection_ends_a_handler_quietly(session: Session, users: Path) -> None:
    from starlette.websockets import WebSocketDisconnect

    from straightjacket.web.handlers import handle_list_players

    class _DeadWS:
        async def send_json(self, msg: dict[str, Any]) -> None:
            raise WebSocketDisconnect()

    _run(handle_list_players(session, _DeadWS(), {}))


def test_handle_list_players_returns_list(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.web.handlers import handle_list_players

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    _run(handle_list_players(session, fake_ws, {}))
    assert len(fake_ws.sent) == 1
    assert fake_ws.sent[0]["type"] == "players_list"
    assert isinstance(fake_ws.sent[0]["players"], list)


def test_handle_select_player_missing_name_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_select_player

    _run(handle_select_player(session, fake_ws, {}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_a_refused_player_name_leaves_the_session_as_it_was(session: Session, fake_ws: _FakeWS, users: Path) -> None:
    from straightjacket.engine.user_management import InvalidNameError
    from straightjacket.web.handlers import handle_select_player

    with pytest.raises(InvalidNameError):
        _run(handle_select_player(session, fake_ws, {"name": "../elsewhere"}))
    assert (session.player, fake_ws.sent) == (new_session().player, [])


def test_handle_select_player_no_game_returns_creation_options(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.web.handlers import handle_select_player

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    monkeypatch.setattr("straightjacket.engine.config_loader.USERS_DIR", tmp_path)

    _run(handle_select_player(session, fake_ws, {"name": "Alice"}))
    selected = next(m for m in fake_ws.sent if m["type"] == "player_selected")
    assert selected["has_game"] is False
    assert "creation_options" in selected


def test_handle_select_player_with_an_incompatible_save_offers_a_new_game(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    import json

    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.persistence import get_save_dir, save_game
    from straightjacket.i18n import t
    from straightjacket.web.handlers import handle_select_player

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    monkeypatch.setattr("straightjacket.engine.config_loader.USERS_DIR", tmp_path)
    name = eng().persistence.default_save_name
    save_game(make_game_state(setting_id="starforged"), "Alice", [], name)
    path = get_save_dir("Alice") / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["game_state"]["resources"].pop("next_move_bonus")
    path.write_text(json.dumps(data), encoding="utf-8")

    _run(handle_select_player(session, fake_ws, {"name": "Alice"}))
    assert {"type": "error", "text": t("actions.save_incompatible")} in fake_ws.sent
    selected = next(m for m in fake_ws.sent if m["type"] == "player_selected")
    assert selected["has_game"] is False
    assert "creation_options" in selected


def test_handle_start_game_when_processing_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_start_game

    session.processing = True
    _run(handle_start_game(session, fake_ws, {"creation_data": {}}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_start_game_malformed_creation_data_errors(
    load_engine: None, session: Session, fake_ws: _FakeWS
) -> None:
    from straightjacket.web.handlers import handle_start_game

    _run(handle_start_game(session, fake_ws, {"creation_data": "not a dict"}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_player_input_when_processing_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_player_input

    session.processing = True
    _run(handle_player_input(session, fake_ws, {"text": "go north"}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_player_input_no_game_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_player_input

    session.game = None
    _run(handle_player_input(session, fake_ws, {"text": "go north"}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_player_input_empty_text_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_player_input

    session.game = make_game_state(player_name="Test", setting_id="starforged")
    _run(handle_player_input(session, fake_ws, {"text": "   "}))
    assert fake_ws.sent == []


def test_handle_correction_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_correction

    session.game = None
    _run(handle_correction(session, fake_ws, {"text": "fix something"}))
    assert fake_ws.sent == []


def test_handle_correction_processing_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_correction

    session.processing = True
    _run(handle_correction(session, fake_ws, {"text": "x"}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_burn_momentum_no_pending_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_burn_momentum

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.pending_burn = None
    _run(handle_burn_momentum(session, fake_ws, {"accept": True}))
    assert fake_ws.sent == []


def test_handle_save_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_save

    session.game = None
    _run(handle_save(session, fake_ws, {"name": "test"}))
    assert fake_ws.sent == []


def test_handle_save_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_save

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.player = ""
    _run(handle_save(session, fake_ws, {"name": "test"}))
    assert fake_ws.sent == []


def test_handle_create_player_invalid_name_is_reported_and_creates_nothing(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web.handlers import handle_create_player

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    monkeypatch.setattr("straightjacket.engine.config_loader.USERS_DIR", tmp_path)
    _run(handle_create_player(session, fake_ws, {"name": "D:"}))
    assert fake_ws.sent == [{"type": "error", "text": t("error.invalid_name")}]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["NUL", "   ", ""])
def test_a_save_under_an_unusable_name_writes_nothing(
    session: Session, fake_ws: _FakeWS, users: Path, name: str
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web.handlers import handle_save

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.player = "Alice"
    _run(handle_save(session, fake_ws, {"name": name}))
    assert fake_ws.sent == [{"type": "error", "text": t("error.invalid_name")}]
    assert list(users.rglob("*.json")) == []


def test_handle_load_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_load

    session.player = ""
    _run(handle_load(session, fake_ws, {"name": "test"}))
    assert fake_ws.sent == []


def test_handle_load_nonexistent_save_errors(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.web.handlers import handle_load

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    monkeypatch.setattr("straightjacket.engine.config_loader.USERS_DIR", tmp_path)
    session.player = "Alice"
    _run(handle_load(session, fake_ws, {"name": "nonexistent"}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_delete_save_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_delete_save

    session.player = ""
    _run(handle_delete_save(session, fake_ws, {"name": "x"}))
    assert fake_ws.sent == []


def test_handle_recap_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_recap

    session.game = None
    _run(handle_recap(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_status_query_no_game_returns_no_game_status(
    load_engine: None, session: Session, fake_ws: _FakeWS
) -> None:
    from straightjacket.web.handlers import handle_status_query

    session.game = None
    _run(handle_status_query(session, fake_ws, {}))
    assert any(m["type"] == "status" for m in fake_ws.sent)


def test_handle_status_query_with_game_returns_status(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_status_query

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.game.world.time_of_day = "evening"
    _run(handle_status_query(session, fake_ws, {}))
    assert any(m["type"] == "status" for m in fake_ws.sent)


def test_handle_tracks_query_no_game_returns_status(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_tracks_query

    session.game = None
    _run(handle_tracks_query(session, fake_ws, {}))
    assert any(m["type"] == "status" for m in fake_ws.sent)


def test_handle_threats_query_no_game_returns_status(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_threats_query

    session.game = None
    _run(handle_threats_query(session, fake_ws, {}))
    assert any(m["type"] == "status" for m in fake_ws.sent)


def test_handle_advance_asset_no_game_returns_status(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_advance_asset

    session.game = None
    _run(handle_advance_asset(session, fake_ws, {"asset_id": "x"}))
    assert any(m["type"] == "status" for m in fake_ws.sent)


def test_a_refused_advance_tells_the_player_why(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.i18n import t
    from straightjacket.web.handlers import handle_advance_asset

    session.game = make_game_state(player_name="Hero", setting_id="starforged")
    session.game.campaign.xp = 10
    _run(handle_advance_asset(session, fake_ws, {"kind": "upgrade", "asset_id": "empath"}))
    assert fake_ws.sent == [{"type": "status", "text": t("advance.not_held", asset="empath")}]
    assert session.game.campaign.xp_spent == 0


def test_handle_generate_epilogue_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_generate_epilogue

    session.game = None
    _run(handle_generate_epilogue(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_dismiss_epilogue_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_dismiss_epilogue

    session.game = None
    _run(handle_dismiss_epilogue(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_new_chapter_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_new_chapter

    session.game = None
    _run(handle_new_chapter(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_retire_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_retire

    session.game = None
    _run(handle_retire(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_start_succession_no_pending_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_start_succession

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.game.campaign.pending_succession = False
    _run(handle_start_succession(session, fake_ws, {"creation_data": {}}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_request_succession_creation_no_game_errors(
    load_engine: None, session: Session, fake_ws: _FakeWS
) -> None:
    from straightjacket.web.handlers import handle_request_succession_creation

    session.game = None
    _run(handle_request_succession_creation(session, fake_ws, {}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_debug_state_no_game_returns_null_data(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_debug_state

    session.game = None
    _run(handle_debug_state(session, fake_ws, {}))
    assert any(m["type"] == "debug_state" for m in fake_ws.sent)


def test_handle_debug_state_with_game_returns_state(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_debug_state

    session.game = make_game_state(player_name="X", setting_id="starforged")
    _run(handle_debug_state(session, fake_ws, {}))
    assert any(m["type"] == "debug_state" for m in fake_ws.sent)


def test_handle_list_saves_returns_list(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.web.handlers import handle_list_saves

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    monkeypatch.setattr("straightjacket.engine.config_loader.USERS_DIR", tmp_path)
    session.player = "Alice"
    _run(handle_list_saves(session, fake_ws, {}))
    assert any(m["type"] == "saves_list" for m in fake_ws.sent)


def test_handle_list_saves_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_list_saves

    session.player = ""
    _run(handle_list_saves(session, fake_ws, {}))
    assert fake_ws.sent == []


def _play_a_turn(session: Session, ws: _FakeWS, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    from straightjacket.web import handlers
    from tests._creation import TurnProvider, brain_answer, force_result

    force_result(monkeypatch, "STRONG_HIT")
    monkeypatch.setattr(handlers, "get_provider", lambda: TurnProvider(brain_answer(location_change=None)))
    _run(handlers.handle_player_input(session, ws, {"text": text}))
    assert ws.sent[-1] == {"type": "turn_complete"}


def test_selecting_the_player_after_a_save_as_resumes_the_game_where_it_was_left(
    session: Session, fake_ws: _FakeWS, users: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.persistence import load_game
    from straightjacket.web.handlers import handle_save, handle_select_player
    from tests._creation import library_game

    session.player = "Kael"
    session.take_game(library_game(), [])
    _run(handle_save(session, fake_ws, {"name": "Before the vault"}))
    _play_a_turn(session, fake_ws, monkeypatch, "I slip into the vault")
    assert session.game is not None
    played = session.game.to_dict()

    _run(handle_select_player(session, fake_ws, {"name": "Kael"}))

    named, _messages = load_game("Kael", "Before the vault")
    assert named is not None
    assert (named.narrative.scene_count, played["narrative"]["scene_count"]) == (1, 2)
    assert session.game.to_dict() == played


def test_play_after_loading_a_save_goes_to_the_autosave_and_leaves_that_save_as_it_was(
    session: Session, fake_ws: _FakeWS, users: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.persistence import load_game
    from straightjacket.web.handlers import handle_load, handle_save
    from tests._creation import library_game

    session.player = "Kael"
    session.take_game(library_game(), [])
    _run(handle_save(session, fake_ws, {"name": "Checkpoint"}))
    _play_a_turn(session, fake_ws, monkeypatch, "I slip into the vault")
    _run(handle_load(session, fake_ws, {"name": "Checkpoint"}))
    _play_a_turn(session, fake_ws, monkeypatch, "I climb the shelves instead")

    named, _messages = load_game("Kael", "Checkpoint")
    resumed, messages = load_game("Kael", eng().persistence.default_save_name)
    assert named is not None
    assert resumed is not None
    assert named.narrative.scene_count == 1
    assert resumed.to_dict() == session.game.to_dict()
    assert [m["content"] for m in messages if m["role"] == "user"] == ["I climb the shelves instead"]


def test_a_correction_with_no_turn_to_correct_is_refused_outside_the_story(
    session: Session, fake_ws: _FakeWS, users: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web import handlers
    from tests._creation import TurnProvider, library_game

    provider = TurnProvider()
    monkeypatch.setattr(handlers, "get_provider", lambda: provider)
    session.player = "Kael"
    opening = [{"role": "assistant", "content": "The opening."}]
    session.take_game(library_game(), list(opening))
    assert session.game is not None
    before = session.game.to_dict()

    _run(handlers.handle_correction(session, fake_ws, {"text": "I meant the other door"}))

    assert fake_ws.sent == [{"type": "error", "text": t("correction.no_snapshot")}]
    assert (session.chat_messages, session.game.to_dict(), provider.calls) == (opening, before, [])
    assert list(users.rglob("*.json")) == []
