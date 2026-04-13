#!/usr/bin/env python3
"""Tests for persistence.py: save, load, list, delete."""

import json
from typing import Any

import pytest

from straightjacket.engine.models import GameState, MemoryEntry, NpcData, ClockData


def _game() -> GameState:
    game = GameState(player_name="TestHero", edge=2, heart=2, iron=1, shadow=1, wits=1)
    game.resources.health = 4
    game.resources.momentum = 3
    game.world.current_location = "TestTavern"
    game.narrative.scene_count = 3
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Ally",
            disposition="friendly",
            memory=[MemoryEntry(scene=1, event="Met player", importance=3)],
        ),
    ]
    game.world.clocks = [ClockData(name="Doom", segments=6, filled=2)]
    return game


@pytest.fixture()
def save_dir(tmp_path: Any, monkeypatch: Any, stub_all: None) -> object:  # type: ignore[override]
    """Redirect save directory to a temp path."""
    from straightjacket.engine import persistence

    monkeypatch.setattr(persistence, "get_save_dir", lambda username: tmp_path / username / "saves")
    (tmp_path / "tester" / "saves").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_save_and_load_roundtrip(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game, load_game

    game = _game()
    msgs = [{"role": "assistant", "content": "Hello world."}]
    save_game(game, "tester", msgs, "test_save")

    loaded, loaded_msgs = load_game("tester", "test_save")
    assert loaded is not None
    assert loaded.player_name == "TestHero"
    assert loaded.resources.health == 4
    assert loaded.narrative.scene_count == 3
    assert len(loaded.npcs) == 1
    assert loaded.npcs[0].name == "Ally"
    assert len(loaded_msgs) == 1


def test_save_excludes_recaps(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game, load_game

    game = _game()
    msgs = [
        {"role": "assistant", "content": "Narration."},
        {"role": "assistant", "content": "Recap text.", "recap": True},
    ]
    save_game(game, "tester", msgs, "test_save")
    _, loaded_msgs = load_game("tester", "test_save")
    assert len(loaded_msgs) == 1
    assert not any(m.get("recap") for m in loaded_msgs)


def test_load_nonexistent_returns_none(save_dir: Any) -> None:
    from straightjacket.engine.persistence import load_game

    game, msgs = load_game("tester", "nonexistent")
    assert game is None
    assert msgs == []


def test_list_saves_empty(save_dir: Any) -> None:
    from straightjacket.engine.persistence import list_saves_with_info

    result = list_saves_with_info("empty_user")
    assert result == []


def test_list_saves_with_saves(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game, list_saves_with_info

    save_game(_game(), "lister", [], "save_a")
    save_game(_game(), "lister", [], "save_b")
    result = list_saves_with_info("lister")
    assert len(result) == 2
    names = {s["name"] for s in result}
    assert "save_a" in names
    assert "save_b" in names


def test_delete_save(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game, delete_save, list_saves_with_info

    save_game(_game(), "deleter", [], "to_delete")
    assert delete_save("deleter", "to_delete") is True
    assert list_saves_with_info("deleter") == []


def test_delete_nonexistent_returns_false(save_dir: Any) -> None:
    from straightjacket.engine.persistence import delete_save

    assert delete_save("nobody", "nope") is False


def test_save_carries_version(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game
    from straightjacket.engine.config_loader import VERSION

    game = _game()
    path = save_game(game, "tester", [], "versioned")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["engine_version"] == VERSION


def test_load_normalizes_npc_dispositions(save_dir: Any) -> None:
    from straightjacket.engine.persistence import save_game, load_game

    game = _game()
    game.npcs[0].disposition = "wary"  # non-canonical, should normalize
    save_game(game, "tester", [], "disp_test")
    loaded, _ = load_game("tester", "disp_test")
    assert loaded is not None
    assert loaded.npcs[0].disposition == "distrustful"
