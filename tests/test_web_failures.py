import asyncio
from typing import Any

import pytest

from straightjacket.engine.ai.provider_base import AIUnavailableError
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game import setup_common
from straightjacket.i18n import t
from straightjacket.web import handlers
from straightjacket.web.serializers import build_narrative_status
from straightjacket.web.session import new_session
from tests._helpers import make_act, make_blueprint, make_game_state
from tests._mocks import MockProvider, RecordingWebSocket


def test_a_failed_chapter_opening_leaves_the_game_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    def narrator_down(*_args: Any, **_kwargs: Any) -> str:
        msg = "narrator: down"
        raise AIUnavailableError(msg)

    monkeypatch.setattr(setup_common, "call_narrator", narrator_down)
    monkeypatch.setattr(handlers, "get_provider", lambda: MockProvider("{}"))
    session = new_session()
    session.game = make_game_state(player_name="Aria", setting_id="starforged")
    before = session.game.to_dict()
    ws = RecordingWebSocket()

    asyncio.run(handlers.handle_new_chapter(session, ws, {}))

    assert session.game.to_dict() == before
    assert ws.sent[-1]["type"] == "error"
    assert session.processing is False


def test_a_fault_outside_the_ai_calls_is_not_swallowed_by_the_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: Any) -> None:
        msg = "broken succession"
        raise KeyError(msg)

    monkeypatch.setattr(handlers, "prepare_succession", broken)
    session = new_session()
    session.game = make_game_state(player_name="Aria", setting_id="starforged")

    with pytest.raises(KeyError, match="broken succession"):
        asyncio.run(handlers.handle_retire(session, RecordingWebSocket(), {}))
    assert session.processing is False


def test_the_status_after_the_epilogue_names_the_aftermath() -> None:
    game = make_game_state(player_name="Aria", setting_id="starforged")
    game.world.time_of_day = "evening"
    game.narrative.story_blueprint = make_blueprint(acts=[make_act(scene_range=[1, 20])], story_complete=True)
    game.campaign.epilogue_dismissed = True

    status = build_narrative_status(game)
    assert t("story.aftermath") in status
    assert eng().status_descriptions.act_progress["late"] in status
