import asyncio

import pytest
from typing_extensions import override

from straightjacket.engine.ai.brain import call_brain
from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, AIUnavailableError
from straightjacket.engine.game import process_turn
from straightjacket.engine.game.finalization import narrate_scene
from straightjacket.i18n import t
from straightjacket.web import handlers
from straightjacket.web.session import new_session
from tests._creation import TurnProvider, brain_answer, correction_answer, force_result, library_game
from tests._helpers import make_game_state, make_state_op
from tests._mocks import MockProvider, RecordingWebSocket


def test_a_brain_failure_raises_instead_of_becoming_dialog() -> None:
    with pytest.raises(AIUnavailableError, match="brain"):
        call_brain(MockProvider(fail=True), make_game_state(setting_id="starforged"), "I look around")


def test_an_empty_narration_raises() -> None:
    with pytest.raises(AIUnavailableError, match="empty narration"):
        narrate_scene(MockProvider(response_content=""), make_game_state(setting_id="starforged"), "<scene/>")


class _NarratorDown(TurnProvider):
    @override
    def create_message(self, spec: AICallSpec) -> AIResponse:
        if spec.json_schema is None:
            msg = "narrator unreachable"
            raise ConnectionError(msg)
        return super().create_message(spec)


def test_a_failed_turn_is_rolled_back_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    game = library_game()
    before = game.to_dict()
    session = new_session()
    session.game = game
    ws = RecordingWebSocket()

    force_result(monkeypatch, "MISS")
    monkeypatch.setattr(handlers, "get_provider", lambda: _NarratorDown(brain_answer()))

    asyncio.run(handlers.handle_player_input(session, ws, {"text": "I leap the gorge"}))

    assert game.to_dict() == before
    assert {"type": "error", "text": f"{t('error.ai_unavailable')} {t('error.nothing_changed')}"} in ws.sent
    assert not session.chat_messages
    assert session.processing is False


def test_a_failed_state_correction_is_rolled_back_with_its_backstory(monkeypatch: pytest.MonkeyPatch) -> None:
    game = library_game()
    force_result(monkeypatch, "MISS")
    process_turn(TurnProvider(brain_answer()), game, "I leap the gorge", None)
    before = game.to_dict()
    session = new_session()
    session.game = game
    provider = _NarratorDown(brain_answer())
    provider.correction = correction_answer(
        correction_source="state_error",
        corrected_input="",
        state_ops=[make_state_op(op="backstory_append", value="Raised by wolves.")],
    )
    monkeypatch.setattr(handlers, "get_provider", lambda: provider)

    asyncio.run(handlers.handle_correction(session, RecordingWebSocket(), {"text": "## I was raised by wolves"}))

    assert game.to_dict() == before
