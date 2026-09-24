from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_integration import MockProvider

ELVIRA_CONFIG = Path(__file__).resolve().parent / "elvira" / "elvira_config.yaml"


def test_elvira_plays_a_short_session_end_to_end(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.elvira.elvira_bot import runner

    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path / "users")
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runner, "check_configured_models", lambda: None)
    monkeypatch.setattr(runner, "get_provider", MockProvider)
    monkeypatch.setattr(runner, "CORRECTION_TEST_INTERVAL", 2)

    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"]["max_turns"] = 3
    bot_cfg["logging"]["print_full_narration"] = False

    session = runner.run_session(bot_cfg, auto_override=True)

    assert session.chapters
    assert session.chapters[0].turns_played == 3
    assert session.ended_reason != "engine_error"
    assert list((tmp_path / "runs").glob("*.json"))
    report = next((tmp_path / "runs").glob("*.md")).read_text(encoding="utf-8")
    assert "## Coverage" in report
    assert session.coverage["counts"]["save_roundtrip"] >= 1
    assert session.save_roundtrip_issues == []
    compact = session.turns[0].to_compact_dict()
    assert compact["narration"]
    assert all(t.stream_complete for t in session.turns if not t.is_correction and not t.error)


def test_elvira_websocket_mode_plays_through_the_real_server(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import asyncio
    import socket

    from straightjacket.engine.ai import api_client
    from straightjacket.web import handlers
    from tests.elvira.elvira_bot import runner, ws_runner

    for target in (
        "straightjacket.engine.config_loader.USERS_DIR",
        "straightjacket.engine.user_management.USERS_DIR",
    ):
        monkeypatch.setattr(target, tmp_path / "users")
    monkeypatch.setattr(ws_runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api_client, "check_configured_models", lambda: None)
    monkeypatch.setattr(api_client, "get_provider", MockProvider)
    monkeypatch.setattr(handlers, "get_provider", MockProvider)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    bot_cfg = runner.load_config(ELVIRA_CONFIG)
    bot_cfg["session"]["max_turns"] = 2
    bot_cfg["logging"]["print_full_narration"] = False
    bot_cfg["ws_port"] = port

    session = asyncio.run(ws_runner.run_ws_session(bot_cfg, auto_override=True))

    played = [t for t in session.turns if not t.error]
    assert len(played) == 2
    assert all(t.stream_sentences > 0 and t.stream_complete and t.stream_matches for t in played)
    assert session.query_issues == []
    assert session.stream_issues == []
    assert list((tmp_path / "runs").glob("*.md"))


def test_event_capture_keeps_only_the_configured_prefixes() -> None:
    import logging

    from tests.elvira.elvira_bot.runner import _EventCapture

    capture = _EventCapture(["[Bonus]", "[Chain]"])
    logger = logging.getLogger("elvira-capture-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(capture)
    for message in ("[Bonus] Ace: +1", "[Roll] not kept", "[Chain] Develop Your Relationship"):
        logger.info(message)
    logger.removeHandler(capture)
    assert capture.lines == ["[Bonus] Ace: +1", "[Chain] Develop Your Relationship"]


def test_a_failed_load_back_is_reported_not_raised(
    load_engine: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.elvira.elvira_bot import runner
    from tests.elvira.elvira_bot.coverage import Coverage
    from tests.elvira.elvira_bot.models import SessionLog
    from tests._helpers import make_game_state

    def broken_load(username: str, name: str) -> tuple[object, list]:
        raise RuntimeError("UNIQUE constraint failed: threads.id")

    monkeypatch.setattr(runner, "_try_save", lambda *args: None)
    monkeypatch.setattr(runner, "load_game", broken_load)
    slog = SessionLog(config={"game": {"setting_id": "starforged"}})
    runner._save_and_verify(make_game_state(), "elvira", [], "slot", slog, Coverage())
    assert "UNIQUE constraint failed" in slog.save_roundtrip_issues[0]
