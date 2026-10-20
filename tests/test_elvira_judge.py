from typing import Any

import pytest

VERDICT = '{"result_integrity": 5, "prompt_elements": 5, "npc_voice": 5, "player_agency": 5, "restraint": 5, "prose": 5, "overall": 9, "weakness": "none", "revelation_conveyed": true}'


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
    from tests._helpers import make_game_state, make_memory, make_npc

    game = make_game_state()
    game.setting_id = "classic"
    game.backstory = "Raised by smugglers on the northern coast."
    game.narrative.scene_count = 4
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Mira",
            status="active",
            description="A tired smith with burned hands.",
            memory=[make_memory(scene=4, event="Watched the search", type="observation")],
        ),
        make_npc(
            id="npc_2",
            name="Saffi",
            status="active",
            description="A trader behind a shut door.",
            memory=[make_memory(scene=3, event="Went inside", type="observation")],
        ),
    ]
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
        "",
    )
    assert verdict["overall"] == 9
    assert "revelation_conveyed" not in verdict
    user = seen[0].messages[0]["content"]
    assert "unwelcome truth that undermines your quest" in user
    assert "(id:" not in user
    assert "__" not in user
    assert "Rain drums on the chapel roof." in user
    assert "Raised by smugglers on the northern coast." in user
    assert "A tired smith with burned hands." in user
    assert "A trader behind a shut door." not in user


def test_the_judge_marks_a_dialog_turn_as_having_no_move(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.elvira.elvira_bot.ai_helpers import _p

    judge, seen = _judge_with_capture(monkeypatch)
    judge.judge_turn(
        {"max_tokens": 200, "extra_body": {}},
        _game(),
        "I ask Mira about the fire.",
        "She shrugs.",
        None,
        False,
        "",
        "",
        "",
    )
    user = seen[0].messages[0]["content"]
    assert _p("judge_none_move") in user
    assert _p("judge_none_previous") in user


def test_the_judge_sees_the_revelation_the_narrator_was_given_and_says_whether_it_came_across(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    judge, seen = _judge_with_capture(monkeypatch)
    prompt = '<scene>\n<revelation weight="high">The harbourmaster sold the maps.</revelation>\n</scene>'
    revelation = judge.revelation_in(prompt)
    assert revelation == "The harbourmaster sold the maps."
    assert judge.revelation_in("<scene>\n</scene>") == ""

    verdict = judge.judge_turn(
        {"max_tokens": 200, "extra_body": {}}, _game(), "I ask Mira.", "She hesitates.", None, False, "", "", revelation
    )
    assert verdict["revelation_conveyed"] is True
    assert "The harbourmaster sold the maps." in seen[0].messages[0]["content"]
