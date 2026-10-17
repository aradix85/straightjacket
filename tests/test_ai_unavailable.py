import asyncio
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests._creation import force_miss
from tests._helpers import make_game_state, make_revelation
from tests._mocks import MockProvider
from tests.test_momentum_burn import _brain, _game, _Provider


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


def test_a_brain_failure_raises_instead_of_becoming_dialog(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from straightjacket.engine.ai.provider_base import AIUnavailableError

    with pytest.raises(AIUnavailableError, match="brain"):
        call_brain(MockProvider(fail=True), make_game_state(setting_id="starforged"), "I look around")


def test_a_failed_revelation_check_counts_as_not_yet_confirmed(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_revelation_check

    assert call_revelation_check(MockProvider(fail=True), "The ledger burns.", make_revelation()) is False


def test_an_empty_narration_raises(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.finalization import narrate_scene

    with pytest.raises(AIUnavailableError, match="empty narration"):
        narrate_scene(MockProvider(response_content=""), make_game_state(setting_id="starforged"), "<scene/>")


class _NarratorDown(_Provider):
    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema is None:
            raise ConnectionError("narrator unreachable")
        return super().create_message(spec)


def test_a_failed_turn_is_rolled_back_and_reported(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web import handlers
    from straightjacket.web.session import Session

    game = _game()
    before = game.to_dict()
    session = Session()
    session.game = game
    ws = _FakeWS()

    force_miss(monkeypatch)
    monkeypatch.setattr(handlers, "get_provider", lambda: _NarratorDown(_brain()))
    monkeypatch.setattr(handlers, "_narration_stream", lambda _ws, _game: (None, []))

    asyncio.run(handlers.handle_player_input(session, ws, {"text": "I leap the gorge"}))

    assert game.to_dict() == before
    assert {"type": "error", "text": f"{t('error.ai_unavailable')} {t('error.nothing_changed')}"} in ws.sent
    assert session.chat_messages == []
    assert session.processing is False


def test_an_unexpected_handler_error_is_reported_and_the_connection_stays(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.i18n import t
    from straightjacket.web import server

    async def broken(_session: Any, _ws: Any, _msg: dict[str, Any]) -> None:
        raise KeyError("boom")

    monkeypatch.setitem(server._HANDLERS, "broken", broken)
    ws = _FakeWS()
    asyncio.run(server._dispatch_one_message(ws, {"type": "broken"}))
    assert ws.sent == [{"type": "error", "text": t("error.unexpected")}]
