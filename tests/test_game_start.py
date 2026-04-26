import json

import pytest

from straightjacket.engine.models import GameState
from tests._helpers import make_game_state
from tests._mocks import MockResponse


class _SmartMockProvider:
    def __init__(self, narration: str = "Opening text.") -> None:
        self.narration = narration
        self.calls: list[dict] = []

    def create_message(
        self,
        model: str = "",
        system: str = "",
        messages: list | None = None,
        max_tokens: int = 1000,
        json_schema: dict | None = None,
        tools: list | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        extra_body: dict | None = None,
    ) -> MockResponse:
        self.calls.append(
            {"system": system[:80], "json_schema_keys": list((json_schema or {}).get("properties", {}).keys())}
        )
        if not json_schema:
            return MockResponse(self.narration)

        props = set(json_schema.get("properties", {}).keys())

        if "central_conflict" in props:
            return MockResponse(
                json.dumps(
                    {
                        "central_conflict": "Find the relic",
                        "antagonist_force": "The cult",
                        "thematic_thread": "trust",
                        "acts": [
                            {
                                "phase": "setup",
                                "title": "Beginning",
                                "goal": "g",
                                "mood": "tense",
                                "scene_range": [1, 5],
                            },
                        ],
                        "revelations": [],
                        "possible_endings": [],
                    }
                )
            )
        if "fixed_conflict" in props:
            return MockResponse(
                json.dumps(
                    {
                        "pass": True,
                        "violations": [],
                        "fixed_conflict": "",
                        "fixed_antagonist": "",
                    }
                )
            )
        if "pass" in props and "violations" in props:
            return MockResponse(json.dumps({"pass": True, "violations": [], "correction": ""}))
        if "npcs" in props and "clocks" in props:
            return MockResponse(
                json.dumps(
                    {
                        "npcs": [],
                        "clocks": [],
                        "location": "Drift Station",
                        "scene_context": "Quiet morning",
                        "time_of_day": "morning",
                        "memory_updates": [],
                        "deceased_npcs": [],
                    }
                )
            )
        if "new_npcs" in props:
            return MockResponse(
                json.dumps(
                    {
                        "new_npcs": [],
                        "npc_renames": [],
                        "npc_details": [],
                        "deceased_npcs": [],
                        "lore_npcs": [],
                    }
                )
            )

        return MockResponse(json.dumps({}))


def _valid_creation_data() -> dict:
    return {
        "setting_id": "starforged",
        "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
        "player_name": "Aria",
        "pronouns": "she/her",
        "background_vow": "Find the lost archive",
        "paths": ["ace"],
        "backstory": "She fled the temple.",
        "assets": [],
        "truths": {},
        "wishes": "",
        "content_lines": "",
        "vow_subject": "",
        "background_vow_rank": "epic",
    }


def test_start_new_game_happy_path(load_engine: None, tmp_path) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.game.game_start import start_new_game

    reset_db()
    provider = _SmartMockProvider("The station hums with cold air.")
    creation = _valid_creation_data()
    try:
        game, narration = start_new_game(provider, creation)
    finally:
        close_db()
    assert isinstance(game, GameState)
    assert game.player_name == "Aria"
    assert game.pronouns == "she/her"
    assert game.background_vow == "Find the lost archive"
    assert game.setting_id == "starforged"
    assert "station" in narration.lower()


def test_start_new_game_empty_background_vow_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _SmartMockProvider()
    creation = _valid_creation_data()
    creation["background_vow"] = ""
    with pytest.raises(ValueError, match="background_vow"):
        start_new_game(provider, creation)


def test_start_new_game_empty_player_name_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _SmartMockProvider()
    creation = _valid_creation_data()
    creation["player_name"] = ""
    with pytest.raises(ValueError, match="player_name"):
        start_new_game(provider, creation)


def test_start_new_game_invalid_stats_raises(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import start_new_game

    provider = _SmartMockProvider()
    creation = _valid_creation_data()
    creation["stats"] = {"edge": 1, "heart": 1, "iron": 1, "shadow": 1, "wits": 1}
    with pytest.raises(ValueError, match="must total"):
        start_new_game(provider, creation)


def test_start_new_game_seeds_background_vow_track(load_engine: None) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.game.game_start import start_new_game

    reset_db()
    provider = _SmartMockProvider()
    try:
        game, _ = start_new_game(provider, _valid_creation_data())
    finally:
        close_db()
    vow_tracks = [t for t in game.progress_tracks if t.id == "vow_background"]
    assert len(vow_tracks) == 1
    assert vow_tracks[0].rank == "epic"


def test_start_new_game_creates_opening_clock(load_engine: None) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.game.game_start import start_new_game

    reset_db()
    provider = _SmartMockProvider()
    try:
        game, _ = start_new_game(provider, _valid_creation_data())
    finally:
        close_db()
    assert len(game.world.clocks) >= 1
    assert any(c.name == "Find the lost archive" for c in game.world.clocks)


def test_start_new_game_seeds_thread_for_vow(load_engine: None) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.game.game_start import start_new_game

    reset_db()
    provider = _SmartMockProvider()
    try:
        game, _ = start_new_game(provider, _valid_creation_data())
    finally:
        close_db()
    vow_threads = [t for t in game.narrative.threads if t.id == "thread_background_vow"]
    assert len(vow_threads) == 1


def test_start_new_game_with_user_persists_content_lines(load_engine: None, tmp_path, monkeypatch) -> None:
    from straightjacket.engine.db.connection import close_db, reset_db
    from straightjacket.engine.game.game_start import start_new_game

    monkeypatch.setattr("straightjacket.engine.user_management.USERS_DIR", tmp_path)

    reset_db()
    provider = _SmartMockProvider()
    creation = _valid_creation_data()
    creation["content_lines"] = "no spiders, no body horror"
    try:
        game, _ = start_new_game(provider, creation, username="testuser")
    finally:
        close_db()
    assert game.preferences.content_lines == "no spiders, no body horror"


def test_apply_opening_setup_routes_to_apply(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.game_start import _apply_opening_setup

    g = make_game_state(player_name="X", setting_id="starforged")
    g.world.current_location = "Tavern"
    data = {
        "clocks": [],
        "location": "Tavern",
        "scene_context": "Quiet",
        "time_of_day": "morning",
    }
    _apply_opening_setup(g, data)
    assert g.world.current_scene_context == "Quiet"


def test_valid_ranks_returns_set(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import _valid_ranks

    ranks = _valid_ranks()
    assert isinstance(ranks, set)
    assert "epic" in ranks
    assert "troublesome" in ranks
