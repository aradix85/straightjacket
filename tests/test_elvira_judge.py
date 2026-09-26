from typing import Any

import pytest

VERDICT = '{"result_integrity": 5, "prompt_elements": 5, "npc_voice": 5, "player_agency": 5, "restraint": 5, "prose": 5, "overall": 9, "weakness": "none"}'


def _judge_with_capture(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, list[Any]]:
    from straightjacket.engine.ai.provider_base import AIResponse
    from tests.elvira.elvira_bot import judge

    seen: list[Any] = []

    class Capture:
        def create_message(self, spec: Any) -> AIResponse:
            seen.append(spec)
            return AIResponse(content=VERDICT)

    monkeypatch.setattr(judge, "bot_provider", lambda: Capture())
    monkeypatch.setattr(judge, "bot_model", lambda: "judge-model")
    return judge, seen


def _game() -> Any:
    from tests._helpers import make_game_state, make_npc

    game = make_game_state()
    game.setting_id = "classic"
    game.backstory = "Raised by smugglers on the northern coast."
    game.npcs = [make_npc(id="npc_1", name="Mira", status="active", description="A tired smith with burned hands.")]
    return game


def test_the_judge_sees_the_move_text_the_previous_narration_and_what_is_established(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge, seen = _judge_with_capture(monkeypatch)
    verdict = judge.judge_turn(
        {"max_tokens": 200, "extra_body": {}},
        _game(),
        "I search the ruined chapel for tracks.",
        "The mud gives you nothing.",
        "MISS",
        False,
        "Rain drums on the chapel roof.",
        "adventure/gather_information",
    )
    assert verdict["overall"] == 9
    user = seen[0].messages[0]["content"]
    assert "unwelcome truth that undermines your quest" in user
    assert "(id:" not in user
    assert "__" not in user
    assert "Rain drums on the chapel roof." in user
    assert "Raised by smugglers on the northern coast." in user
    assert "A tired smith with burned hands." in user


def test_the_judge_marks_a_dialog_turn_as_having_no_move(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.elvira.elvira_bot.ai_helpers import _p

    judge, seen = _judge_with_capture(monkeypatch)
    judge.judge_turn(
        {"max_tokens": 200, "extra_body": {}}, _game(), "I ask Mira about the fire.", "She shrugs.", None, False, "", ""
    )
    user = seen[0].messages[0]["content"]
    assert _p("judge_none_move") in user
    assert _p("judge_none_previous") in user
