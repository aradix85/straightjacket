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
