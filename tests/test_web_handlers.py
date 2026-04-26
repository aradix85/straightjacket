import asyncio

import pytest

from straightjacket.web.session import Session
from tests._helpers import make_game_state


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def fake_ws() -> _FakeWS:
    return _FakeWS()


@pytest.fixture()
def session(load_engine: None) -> Session:
    return Session()


def test_require_str_returns_trimmed_value(load_engine: None, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import _require_str

    result = _run(_require_str(fake_ws, {"name": "  Alice  "}, "name", "error.empty_player_name"))
    assert result == "Alice"
    assert fake_ws.sent == []


def test_require_str_rejects_missing_key(load_engine: None, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import _require_str

    result = _run(_require_str(fake_ws, {}, "name", "error.empty_player_name"))
    assert result is None
    assert len(fake_ws.sent) == 1
    assert fake_ws.sent[0]["type"] == "error"


def test_require_str_rejects_non_string(load_engine: None, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import _require_str

    result = _run(_require_str(fake_ws, {"name": 42}, "name", "error.empty_player_name"))
    assert result is None
    assert fake_ws.sent[0]["type"] == "error"


def test_require_str_rejects_blank(load_engine: None, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import _require_str

    result = _run(_require_str(fake_ws, {"name": "   "}, "name", "error.empty_player_name"))
    assert result is None


def test_send_swallows_disconnect(load_engine: None) -> None:
    from straightjacket.web.handlers import _send
    from starlette.websockets import WebSocketDisconnect

    class _DeadWS:
        async def send_json(self, msg: dict) -> None:
            raise WebSocketDisconnect()

    _run(_send(_DeadWS(), {"type": "x"}))


def test_handle_list_players_returns_list(
    load_engine: None, session: Session, fake_ws: _FakeWS, monkeypatch, tmp_path
) -> None:
    from straightjacket.web.handlers import handle_list_players

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)
    _run(handle_list_players(session, fake_ws, {}))
    assert len(fake_ws.sent) == 1
    assert fake_ws.sent[0]["type"] == "players_list"
    assert isinstance(fake_ws.sent[0]["players"], list)


def test_handle_create_player_empty_name_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_create_player

    _run(handle_create_player(session, fake_ws, {"name": ""}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


def test_handle_select_player_missing_name_errors(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_select_player

    _run(handle_select_player(session, fake_ws, {}))
    assert any(m["type"] == "error" for m in fake_ws.sent)


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
    _run(handle_save(session, fake_ws, {"save_name": "test"}))
    assert fake_ws.sent == []


def test_handle_save_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_save

    session.game = make_game_state(player_name="X", setting_id="starforged")
    session.player = ""
    _run(handle_save(session, fake_ws, {"save_name": "test"}))
    assert fake_ws.sent == []


def test_handle_load_no_player_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_load

    session.player = ""
    _run(handle_load(session, fake_ws, {"save_name": "test"}))
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
    _run(handle_delete_save(session, fake_ws, {"save_name": "x"}))
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


def test_handle_generate_epilogue_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_generate_epilogue

    session.game = None
    _run(handle_generate_epilogue(session, fake_ws, {}))
    assert fake_ws.sent == []


def test_handle_dismiss_epilogue_no_game_silent(load_engine: None, session: Session, fake_ws: _FakeWS) -> None:
    from straightjacket.web.handlers import handle_dismiss_epilogue

    session.game = None
    _run(handle_dismiss_epilogue(session, fake_ws, {}))


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
