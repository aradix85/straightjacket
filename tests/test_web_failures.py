import asyncio
from typing import Any

import pytest

from straightjacket.web.session import Session
from tests._helpers import make_act, make_blueprint, make_game_state
from tests._mocks import MockProvider


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


def test_a_failed_chapter_opening_leaves_the_game_as_it_was(
    load_engine: None, stub_emotions: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game import chapters
    from straightjacket.web import handlers

    def narrator_down(*_args: Any, **_kwargs: Any) -> str:
        raise AIUnavailableError("narrator: down")

    monkeypatch.setattr(chapters, "call_narrator", narrator_down)
    monkeypatch.setattr(handlers, "get_provider", lambda: MockProvider("{}"))
    session = Session()
    session.game = make_game_state(player_name="Aria", setting_id="starforged")
    before = session.game.to_dict()
    ws = _FakeWS()

    asyncio.run(handlers.handle_new_chapter(session, ws, {}))

    assert session.game.to_dict() == before
    assert ws.sent[-1]["type"] == "error"
    assert session.processing is False


def test_a_fault_outside_the_ai_calls_is_not_swallowed_by_the_handler(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.web import handlers

    def broken(*_args: Any) -> None:
        raise KeyError("broken succession")

    monkeypatch.setattr(handlers, "prepare_succession", broken)
    session = Session()
    session.game = make_game_state(player_name="Aria", setting_id="starforged")

    with pytest.raises(KeyError, match="broken succession"):
        asyncio.run(handlers.handle_retire(session, _FakeWS(), {}))
    assert session.processing is False


def test_the_status_after_the_epilogue_names_the_aftermath(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.i18n import t
    from straightjacket.web.serializers import build_narrative_status

    game = make_game_state(player_name="Aria", setting_id="starforged")
    game.world.time_of_day = "evening"
    game.narrative.story_blueprint = make_blueprint(acts=[make_act(scene_range=[1, 20])], story_complete=True)
    game.campaign.epilogue_dismissed = True

    status = build_narrative_status(game)
    assert t("story.aftermath") in status
    assert eng().status_descriptions.act_progress["late"] in status
