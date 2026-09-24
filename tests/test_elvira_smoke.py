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
