import asyncio
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse
from tests._creation import TurnProvider, brain_answer, force_result, library_game
from tests._helpers import make_game_state
from tests._mocks import MockProvider


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


def test_an_empty_narration_raises(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.finalization import narrate_scene

    with pytest.raises(AIUnavailableError, match="empty narration"):
        narrate_scene(MockProvider(response_content=""), make_game_state(setting_id="starforged"), "<scene/>")


class _NarratorDown(TurnProvider):
    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema is None:
            raise ConnectionError("narrator unreachable")
        return super().create_message(spec)


def test_a_failed_turn_is_rolled_back_and_reported(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.i18n import t
    from straightjacket.web import handlers
    from straightjacket.web.session import new_session

    game = library_game()
    before = game.to_dict()
    session = new_session()
    session.game = game
    ws = _FakeWS()

    force_result(monkeypatch, "MISS")
    monkeypatch.setattr(handlers, "get_provider", lambda: _NarratorDown(brain_answer()))

    asyncio.run(handlers.handle_player_input(session, ws, {"text": "I leap the gorge"}))

    assert game.to_dict() == before
    assert {"type": "error", "text": f"{t('error.ai_unavailable')} {t('error.nothing_changed')}"} in ws.sent
    assert session.chat_messages == []
    assert session.processing is False
