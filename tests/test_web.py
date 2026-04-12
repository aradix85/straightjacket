#!/usr/bin/env python3
"""Tests for the web module: session state, serializers, WebSocket handlers.

Unit tests for Session and serializers need no server.
Integration tests use Starlette's TestClient with websocket_connect().

The web module imports the real engine (not the conftest stub), so we
use a local load_engine fixture that loads real engine.yaml.

Run: python -m pytest tests/test_web.py -v
"""

from typing import Any

import pytest

from straightjacket.engine import engine_loader  # type: ignore[import-not-found]
from straightjacket.engine.models import (  # type: ignore[import-not-found]
    BrainResult,
    ClockData,
    GameState,
    NpcData,
    RollResult,
    TurnSnapshot,
)
from straightjacket.web.session import BurnOffer, Session  # type: ignore[import-not-found]
from straightjacket.web.serializers import (  # type: ignore[import-not-found]
    build_creation_options,
    build_narrative_status,
    highlight_dialog,
)


@pytest.fixture()
def load_engine() -> None:
    """Load real engine.yaml."""
    engine_loader._eng = None
    engine_loader.eng()


# ── Session dataclass ─────────────────────────────────────────


class TestSession:
    def test_initial_state(self) -> None:
        s = Session()
        assert s.player == ""
        assert s.game is None
        assert s.has_game is False
        assert s.processing is False
        assert s.chat_messages == []
        assert s.pending_burn is None

    def test_append_chat(self) -> None:
        s = Session()
        s.append_chat("user", "hello")
        s.append_chat("assistant", "world")
        assert len(s.chat_messages) == 2
        assert s.chat_messages[0] == {"role": "user", "content": "hello"}
        assert s.chat_messages[1] == {"role": "assistant", "content": "world"}

    def test_append_chat_extra_fields(self) -> None:
        s = Session()
        s.append_chat("assistant", "epilogue text", epilogue=True)
        assert s.chat_messages[0]["epilogue"] is True

    def test_orphan_input_none_when_assistant_last(self) -> None:
        s = Session()
        s.append_chat("user", "action")
        s.append_chat("assistant", "narration")
        assert s.orphan_input() is None

    def test_orphan_input_returns_text_when_user_last(self) -> None:
        s = Session()
        s.append_chat("user", "orphaned action")
        assert s.orphan_input() == "orphaned action"

    def test_orphan_input_none_when_empty(self) -> None:
        s = Session()
        assert s.orphan_input() is None

    def test_pop_last_user_message(self) -> None:
        s = Session()
        s.append_chat("user", "first")
        s.append_chat("assistant", "response")
        s.append_chat("user", "second")
        s.pop_last_user_message()
        assert len(s.chat_messages) == 2
        assert s.chat_messages[-1]["role"] == "assistant"

    def test_pop_last_user_message_noop_when_assistant_last(self) -> None:
        s = Session()
        s.append_chat("user", "x")
        s.append_chat("assistant", "y")
        s.pop_last_user_message()
        assert len(s.chat_messages) == 2

    def test_replace_last_assistant(self) -> None:
        s = Session()
        s.append_chat("user", "input")
        s.append_chat("assistant", "original")
        s.replace_last_assistant("replaced")
        assert s.chat_messages[-1]["content"] == "replaced"

    def test_replace_last_assistant_skips_user(self) -> None:
        s = Session()
        s.append_chat("assistant", "first")
        s.append_chat("user", "second")
        s.replace_last_assistant("replaced")
        assert s.chat_messages[0]["content"] == "replaced"

    def test_clear_game(self) -> None:
        s = Session()
        s.game = GameState(player_name="Test")
        s.chat_messages = [{"role": "assistant", "content": "x"}]
        s.save_name = "custom"
        s.pending_burn = BurnOffer(
            roll=RollResult(1, 1, 1, 1, "wits", 2, 4, "MISS", "adventure/face_danger"),
            new_result="WEAK_HIT",
            cost=5,
            brain=BrainResult(),
            player_words="x",
            pre_snapshot=TurnSnapshot(),
        )
        s.clear_game()
        assert s.game is None
        assert s.chat_messages == []
        assert s.save_name == "autosave"
        assert s.pending_burn is None

    def test_has_game_property(self) -> None:
        s = Session()
        assert s.has_game is False
        s.game = GameState()
        assert s.has_game is True

    def test_filtered_messages_strips_recaps(self) -> None:
        s = Session()
        s.chat_messages = [
            {"role": "assistant", "content": "narration"},
            {"role": "user", "content": "action"},
            {"role": "assistant", "content": "recap", "recap": True},
        ]
        filtered = s.filtered_messages()
        assert len(filtered) == 2
        assert all(not m.get("recap") for m in filtered)


# ── BurnOffer dataclass ───────────────────────────────────────


class TestBurnOffer:
    def test_fields(self) -> None:
        from straightjacket.engine.mechanics.scene import SceneSetup

        bo = BurnOffer(
            roll=RollResult(1, 2, 3, 4, "iron", 3, 6, "MISS", "combat/strike"),
            new_result="STRONG_HIT",
            cost=7,
            brain=BrainResult(move="combat/strike", stat="iron"),
            player_words="I attack",
            pre_snapshot=TurnSnapshot(),
            scene_setup=SceneSetup(scene_type="altered", adjustments=["add_character"]),
        )
        assert bo.new_result == "STRONG_HIT"
        assert bo.cost == 7
        assert bo.scene_setup is not None
        assert bo.scene_setup.scene_type == "altered"

    def test_scene_setup_defaults_none(self) -> None:
        bo = BurnOffer(
            roll=RollResult(1, 1, 1, 1, "wits", 1, 3, "MISS", "adventure/face_danger"),
            new_result="WEAK_HIT",
            cost=3,
            brain=BrainResult(),
            player_words="x",
            pre_snapshot=TurnSnapshot(),
        )
        assert bo.scene_setup is None


# ── Serializers ───────────────────────────────────────────────


class TestHighlightDialog:
    def test_curly_quotes(self) -> None:
        text = "\u201cHello,\u201d she said."
        result = highlight_dialog(text)
        assert '<span class="dialog">' in result
        assert "Hello," in result

    def test_straight_quotes(self) -> None:
        result = highlight_dialog('"Hello," she said.')
        assert '<span class="dialog">' in result

    def test_german_quotes(self) -> None:
        result = highlight_dialog("\u201eHallo,\u201c sagte sie.")
        assert '<span class="dialog">' in result

    def test_no_quotes_unchanged(self) -> None:
        text = "The wind howled through the broken windows."
        assert highlight_dialog(text) == text

    def test_guillemets(self) -> None:
        result = highlight_dialog("\u00abBonjour\u00bb dit-elle.")
        assert '<span class="dialog">' in result


class TestBuildNarrativeStatus:
    def _game(self) -> GameState:
        game = GameState(
            player_name="Kael",
            character_concept="Scholar",
            edge=1,
            heart=2,
            iron=1,
            shadow=1,
            wits=2,
            setting_genre="dark_fantasy",
        )
        game.resources.health = 4
        game.resources.spirit = 3
        game.resources.supply = 5
        game.resources.momentum = 5
        game.world.current_location = "Library"
        game.world.time_of_day = "evening"
        game.world.chaos_factor = 6
        game.narrative.scene_count = 5
        game.npcs = [
            NpcData(id="npc_1", name="Mira", status="active", disposition="friendly"),
            NpcData(id="npc_2", name="Ghost", status="deceased", disposition="neutral"),
            NpcData(id="npc_3", name="Lore Figure", status="lore", disposition="neutral"),
        ]
        game.world.clocks = [
            ClockData(name="Doom", clock_type="threat", segments=6, filled=3),
        ]
        return game

    def test_returns_string(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert isinstance(text, str)
        assert "Kael" in text

    def test_contains_resources(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "4" in text  # health
        assert "3" in text  # spirit
        assert "5" in text  # supply/momentum

    def test_contains_location(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "Library" in text

    def test_npcs_filtered(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "Mira" in text
        assert "Ghost" in text
        assert "Lore Figure" not in text

    def test_clocks_present(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "Doom" in text

    def test_story_arc_absent_without_blueprint(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "act" not in text.lower() or "Story:" not in text

    def test_story_arc_present_with_blueprint(self, load_engine: None) -> None:
        from straightjacket.engine.models import StoryAct, StoryBlueprint

        game = self._game()
        game.narrative.story_blueprint = StoryBlueprint(
            central_conflict="test",
            antagonist_force="villain",
            thematic_thread="theme",
            structure_type="3act",
            acts=[StoryAct(phase="setup", title="Begin", scene_range=[1, 10], mood="dark")],
        )
        text = build_narrative_status(game)
        assert "Begin" in text


class TestBuildCreationOptions:
    def test_returns_settings(self, load_engine: None) -> None:
        opts = build_creation_options()
        assert "settings" in opts
        from straightjacket.engine.datasworn.loader import list_available  # type: ignore[import-not-found]

        if not list_available():
            pytest.skip("No Datasworn JSON files in data/ — run download_datasworn.py")
        assert len(opts["settings"]) >= 1

    def test_settings_have_paths(self, load_engine: None) -> None:
        opts = build_creation_options()
        for s in opts["settings"]:
            assert "id" in s
            assert "title" in s
            assert "paths" in s
            assert len(s["paths"]) > 0

    def test_delve_excluded(self, load_engine: None) -> None:
        opts = build_creation_options()
        ids = [s["id"] for s in opts["settings"]]
        assert "delve" not in ids

    def test_paths_have_id_and_title(self, load_engine: None) -> None:
        opts = build_creation_options()
        for s in opts["settings"]:
            for p in s["paths"]:
                assert "id" in p
                assert "title" in p


# ── WebSocket integration (via Starlette TestClient) ──────────


class TestWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self, load_engine: None) -> None:
        """Reset session state before each test."""
        from straightjacket.web.server import _session

        _session.player = ""
        _session.game = None
        _session.chat_messages = []
        _session.processing = False
        _session.active_ws = None
        _session.pending_burn = None
        self.session = _session

    @pytest.fixture()
    def client(self) -> Any:
        from starlette.testclient import TestClient
        from straightjacket.web.server import app  # type: ignore[import-not-found]

        return TestClient(app)

    def test_full_connection_flow(self, client: Any) -> None:
        """Full WebSocket flow: connect, create player, error handling, saves, cleanup."""
        with client.websocket_connect("/ws") as ws:
            # 1. Connect: receive ui_strings then players_list
            msg = ws.receive_json()
            assert msg["type"] == "ui_strings"
            assert "ui.title" in msg["strings"]

            msg = ws.receive_json()
            assert msg["type"] == "players_list"

            # 2. Create player → player_selected with creation options
            ws.send_json({"type": "create_player", "name": "ws_flow"})
            msg = ws.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["name"] == "ws_flow"
            assert msg["has_game"] is False
            assert "creation_options" in msg

            # 3. Empty name → error
            ws.send_json({"type": "create_player", "name": ""})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            # 4. Unknown message type → error
            ws.send_json({"type": "nonexistent_type"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "nonexistent_type" in msg["text"]

            # 5. Player input without game → error
            ws.send_json({"type": "player_input", "text": "I search"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            # 6. Empty saves list
            ws.send_json({"type": "list_saves"})
            msg = ws.receive_json()
            assert msg["type"] == "saves_list"
            assert msg["saves"] == []

            # 7. Delete player and verify gone
            ws.send_json({"type": "delete_player", "name": "ws_flow"})
            msg = ws.receive_json()
            assert msg["type"] == "players_list"
            assert "ws_flow" not in msg["players"]

    def test_reconnect_resends_player_state(self, client: Any) -> None:
        """Reconnect after player selection resends full state."""
        with client.websocket_connect("/ws") as ws1:
            ws1.receive_json()  # ui_strings
            ws1.receive_json()  # players_list
            ws1.send_json({"type": "create_player", "name": "ws_recon"})
            ws1.receive_json()  # player_selected

        with client.websocket_connect("/ws") as ws2:
            ws2.receive_json()  # ui_strings
            msg = ws2.receive_json()
            assert msg["type"] == "players_list"
            msg = ws2.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["name"] == "ws_recon"
            ws2.send_json({"type": "delete_player", "name": "ws_recon"})
            ws2.receive_json()
