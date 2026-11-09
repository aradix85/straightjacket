from __future__ import annotations

import asyncio
import logging
import socket
from pathlib import Path
from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster import questions
from straightjacket.engine.ruleset import answers, threats
from straightjacket.web import handlers
from tests._creation import TurnProvider, brain_answer
from tests._helpers import emit_engine_log, use_users_dir
from tests.elvira.elvira_bot import ai_helpers, runner, ws_runner
from tests.elvira.elvira_bot.models import SessionLog, TurnRecord
from tests.elvira.elvira_bot.report import _event_lines, collect_problems
from tests.elvira.elvira_bot.runner import _EventCapture

if TYPE_CHECKING:
    import pytest

ELVIRA_CONFIG = Path(__file__).resolve().parent / "elvira" / "elvira_config.yaml"


def _provider() -> TurnProvider:
    return TurnProvider(brain_answer(player_intent="I search the room for clues", location_change=None))


def _mock_direct_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    users = tmp_path / "users"
    users.mkdir()
    use_users_dir(monkeypatch, users)
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runner, "check_configured_models", lambda: None)
    monkeypatch.setattr(runner, "get_provider", _provider)
    monkeypatch.setattr(ai_helpers, "provider_named", lambda _name: _provider())
    monkeypatch.setattr(runner, "selectable_settings", lambda: ["starforged"])
    monkeypatch.setattr(runner, "available_styles", lambda: ["explorer"])


def _scenario_run(name: str, turns: int) -> SessionLog:
    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"] |= {"scenario": name, "max_turns": turns, "inject_ai_failure_turn": 0}
    bot_cfg["logging"]["print_full_narration"] = False
    session: SessionLog = runner.run_session(bot_cfg, auto_override=True, turns_override=None)
    return session


def test_a_scenario_with_fixed_results_plays_to_its_aim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    session = _scenario_run("miss", 3)
    assert session.scenario["missed"] == []
    rolled = [t.roll.result for t in session.turns if t.roll and not t.is_correction]
    assert rolled
    assert set(rolled) == {"MISS"}


def test_a_scenario_that_starts_at_a_game_over_plays_the_successor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    session = _scenario_run("succession", 1)
    assert session.scenario["missed"] == []
    assert "new_character" in session.succession
    assert not session.turns[0].error


def test_a_threat_on_the_vow_advances_on_a_miss(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    emit_engine_log(monkeypatch, threats)
    session = _scenario_run("threat_advance", 2)
    assert session.scenario["missed"] == []


def test_a_scenario_plays_the_setting_it_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    session = _scenario_run("bond", 1)
    assert session.config["game"]["setting_id"] == "classic"


def test_elvira_plays_a_short_session_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "CORRECTION_TEST_INTERVAL", 2)

    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"]["max_turns"] = 3
    bot_cfg["logging"]["print_full_narration"] = False
    bot_cfg["session"]["inject_ai_failure_turn"] = 3

    session = runner.run_session(bot_cfg, auto_override=True, turns_override=None)

    assert session.chapters
    assert session.chapters[0].turns_played == 3
    assert session.ended_reason != "engine_error"
    assert list((tmp_path / "runs").glob("*.json"))
    report = next((tmp_path / "runs").glob("*.md")).read_text(encoding="utf-8")
    assert "## Coverage" in report
    assert "## Revelations" in report
    assert report.startswith("# Elvira report: starforged, explorer")
    assert session.coverage["counts"]["save_roundtrip"] >= 1
    assert not session.save_roundtrip_issues
    compact = session.turns[0].to_compact_dict()
    assert compact["narration"]
    assert all(t.stream_complete for t in session.turns if not t.is_correction and not t.error and not t.rolled_back)
    assert session.coverage["counts"]["ai_failure_rollback"] == 1
    assert not session.rollback_issues
    assert {"narrator", "opening_setup", "brain"} <= {str(e["role"]) for e in session.turns[0].token_usage}


def _ws_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionLog:
    users = tmp_path / "users"
    users.mkdir()
    use_users_dir(monkeypatch, users)
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(ws_runner, "check_configured_models", lambda: None)
    monkeypatch.setattr(ws_runner, "get_provider", _provider)
    monkeypatch.setattr(ai_helpers, "provider_named", lambda _name: _provider())
    monkeypatch.setattr(handlers, "get_provider", _provider)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"]["max_turns"] = 2
    bot_cfg["game"]["setting_id"] = "starforged"
    bot_cfg["bot_behavior"]["style"] = "explorer"
    bot_cfg["logging"]["print_full_narration"] = False
    bot_cfg["ws_port"] = port

    session: SessionLog = asyncio.run(ws_runner.run_ws_session(bot_cfg, auto_override=True, turns_override=None))
    return session


def test_elvira_websocket_mode_plays_through_the_real_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = _ws_session(monkeypatch, tmp_path)

    played = [t for t in session.turns if not t.error]
    assert len(played) == 2
    assert all(t.stream_sentences > 0 and t.stream_complete and t.stream_matches for t in played)
    assert session.query_issues == []
    assert session.stream_issues == []
    assert all(t.token_usage for t in played)
    assert session.token_summary["by_role"]["narrator"]["calls"] >= 2
    assert list((tmp_path / "runs").glob("*.md"))


def test_a_websocket_chapter_that_ends_on_an_error_says_so(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def no_decision(_persona: str, _context: str, *, max_tokens: int) -> str:
        msg = f"bot unreachable after {max_tokens} tokens"
        raise RuntimeError(msg)

    monkeypatch.setattr(ws_runner, "ask_bot", no_decision)
    session = _ws_session(monkeypatch, tmp_path)
    assert [ch.ended_reason for ch in session.chapters] == ["engine_error"]
    assert session.ended_reason == "engine_error"
    assert session.turns[0].error


def test_event_capture_keeps_only_the_configured_prefixes() -> None:
    capture = _EventCapture(["[Bonus]", "[Chain]"])
    logger = logging.getLogger("elvira-capture-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(capture)
    for message in ("[Bonus] Ace: +1", "[Roll] not kept", "[Chain] Develop Your Relationship"):
        logger.info(message)
    logger.removeHandler(capture)
    assert capture.lines == ["[Bonus] Ace: +1", "[Chain] Develop Your Relationship"]


def test_a_failed_load_back_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)

    def broken_load(_username: str, _name: str) -> tuple[object, list[object]]:
        msg = "UNIQUE constraint failed: threads.id"
        raise RuntimeError(msg)

    monkeypatch.setattr(runner, "load_game", broken_load)
    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"] |= {"max_turns": 1, "inject_ai_failure_turn": 0}
    bot_cfg["logging"]["print_full_narration"] = False
    session = runner.run_session(bot_cfg, auto_override=True, turns_override=None)
    assert session.save_roundtrip_issues
    assert all("UNIQUE constraint failed" in issue for issue in session.save_roundtrip_issues)


def test_event_capture_keeps_every_warning_and_error() -> None:
    capture = _EventCapture(["[Bonus]"])
    logger = logging.getLogger("elvira-warning-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(capture)
    logger.info("[Roll] fine")
    logger.warning("[Metadata] Extraction failed: no route")
    logger.error("[DB] sync failed")
    logger.removeHandler(capture)
    assert capture.warnings == ["WARNING: [Metadata] Extraction failed: no route", "ERROR: [DB] sync failed"]


def test_the_report_counts_the_directors_tool_calls() -> None:
    slog = SessionLog(config={"game": {"setting_id": "starforged"}})
    slog.turns = [
        TurnRecord(turn=1, engine_events=["[Director] Phase 1: 1 tool calls"]),
        TurnRecord(
            turn=2, engine_events=["[Director] Phase 1: no tools called", "[Tools] Registered query_game_state"]
        ),
        TurnRecord(turn=3, engine_events=["[Director] Phase 1: 2 tool calls"]),
    ]
    assert "Director tool calls: 3." in _event_lines(slog)


def test_repeated_engine_warnings_become_one_counted_problem() -> None:
    slog = SessionLog(config={"game": {"setting_id": "starforged"}})
    slog.engine_warnings = ["WARNING: [Metadata] Extraction failed"] * 3 + ["ERROR: [DB] sync failed"]
    problems = collect_problems(slog)
    assert "Engine WARNING: [Metadata] Extraction failed (3 times)" in problems
    assert "Engine ERROR: [DB] sync failed" in problems


def test_elvira_installs_the_ruleset_answers_when_she_starts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _mock_direct_runner(monkeypatch, tmp_path)
    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"]["max_turns"] = 1
    bot_cfg["logging"]["print_full_narration"] = False
    monkeypatch.setattr(questions, "_installed", [])

    runner.run_session(bot_cfg, auto_override=True, turns_override=None)

    assert questions.answers() is answers
