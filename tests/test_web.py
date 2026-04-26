from typing import Any

import pytest

from straightjacket.engine import engine_loader
from straightjacket.engine.models import (
    GameState,
    RollResult,
    TurnSnapshot,
)
from tests._helpers import make_brain_result, make_clock, make_game_state, make_npc
from straightjacket.web.session import BurnOffer, Session
from straightjacket.web.serializers import (
    build_creation_options,
    build_narrative_status,
    highlight_dialog,
)


@pytest.fixture()
def load_engine(_real_engine) -> None:
    engine_loader._eng = _real_engine


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
        s.game = make_game_state(player_name="Test")
        s.chat_messages = [{"role": "assistant", "content": "x"}]
        s.save_name = "custom"
        s.pending_burn = BurnOffer(
            roll=RollResult(1, 1, 1, 1, "wits", 2, 4, "MISS", "adventure/face_danger", match=True),
            new_result="WEAK_HIT",
            cost=5,
            brain=make_brain_result(),
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
        s.game = make_game_state()
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


class TestBurnOffer:
    def test_fields(self) -> None:
        from straightjacket.engine.mechanics.scene import SceneSetup

        bo = BurnOffer(
            roll=RollResult(1, 2, 3, 4, "iron", 3, 6, "MISS", "combat/strike", match=False),
            new_result="STRONG_HIT",
            cost=7,
            brain=make_brain_result(move="combat/strike", stat="iron"),
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
            roll=RollResult(1, 1, 1, 1, "wits", 1, 3, "MISS", "adventure/face_danger", match=True),
            new_result="WEAK_HIT",
            cost=3,
            brain=make_brain_result(),
            player_words="x",
            pre_snapshot=TurnSnapshot(),
        )
        assert bo.scene_setup is None


class TestHighlightDialog:
    def test_curly_quotes(self) -> None:
        text = "\u201cHello,\u201d she said."
        result = highlight_dialog(text)
        assert '<span class="dialog">' in result
        assert "Hello," in result

    def test_straight_quotes(self) -> None:
        result = highlight_dialog('"Hello," she said.')
        assert '<span class="dialog">' in result

    def test_no_quotes_unchanged(self) -> None:
        text = "The wind howled through the broken windows."
        assert highlight_dialog(text) == text


class TestBuildNarrativeStatus:
    def _game(self) -> GameState:
        game = GameState(
            player_name="Kael",
            character_concept="Scholar",
            stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
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
            make_npc(id="npc_1", name="Mira", status="active", disposition="friendly"),
            make_npc(id="npc_2", name="Ghost", status="deceased", disposition="neutral"),
            make_npc(id="npc_3", name="Lore Figure", status="lore", disposition="neutral"),
        ]
        game.world.clocks = [
            make_clock(name="Doom", clock_type="threat", segments=6, filled=3),
        ]
        return game

    def test_returns_string(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert isinstance(text, str)
        assert "Kael" in text

    def test_contains_resources(self, load_engine: None) -> None:
        text = build_narrative_status(self._game())
        assert "bruised" in text
        assert "shaken" in text
        assert "well-equipped" in text

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
        from straightjacket.engine.datasworn.loader import list_available

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


class TestWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self, load_engine: None) -> None:
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
        from straightjacket.web.server import app

        return TestClient(app)

    def test_full_connection_flow(self, client: Any) -> None:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "ui_strings"
            assert "ui.title" in msg["strings"]

            msg = ws.receive_json()
            assert msg["type"] == "players_list"

            ws.send_json({"type": "create_player", "name": "ws_flow"})
            msg = ws.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["name"] == "ws_flow"
            assert msg["has_game"] is False
            assert "creation_options" in msg

            ws.send_json({"type": "create_player", "name": ""})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            ws.send_json({"type": "nonexistent_type"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "nonexistent_type" in msg["text"]

            ws.send_json({"type": "player_input", "text": "I search"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            ws.send_json({"type": "list_saves"})
            msg = ws.receive_json()
            assert msg["type"] == "saves_list"
            assert msg["saves"] == []

            ws.send_json({"type": "delete_player", "name": "ws_flow"})
            msg = ws.receive_json()
            assert msg["type"] == "players_list"
            assert "ws_flow" not in msg["players"]

    def test_reconnect_resends_player_state(self, client: Any) -> None:
        with client.websocket_connect("/ws") as ws1:
            ws1.receive_json()
            ws1.receive_json()
            ws1.send_json({"type": "create_player", "name": "ws_recon"})
            ws1.receive_json()

        with client.websocket_connect("/ws") as ws2:
            ws2.receive_json()
            msg = ws2.receive_json()
            assert msg["type"] == "players_list"
            msg = ws2.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["name"] == "ws_recon"
            ws2.send_json({"type": "delete_player", "name": "ws_recon"})
            ws2.receive_json()


class TestSuccessionWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self, load_engine: None) -> None:
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
        from straightjacket.web.server import app

        return TestClient(app)

    def _seed_session(self, player: str = "ws_succ") -> None:
        from straightjacket.engine.persistence import save_game
        from straightjacket.engine.user_management import create_user

        create_user(player)
        game = make_game_state(
            player_name="Aria",
            pronouns="she/her",
            character_concept="outlander",
            background_vow="avenge sister",
            setting_id="classic",
        )
        game.campaign.legacy_quests.ticks = 24
        game.narrative.scene_count = 5
        save_game(game, player, [{"role": "assistant", "content": "..."}], "autosave")

    def _drain_initial(self, ws: Any) -> None:
        ws.receive_json()
        ws.receive_json()

    def test_retire_without_game_no_op(self, client: Any) -> None:
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "retire"})

            assert self.session.game is None
            assert self.session.processing is False

    def test_retire_with_game_prepares_succession(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            msg = ws.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["has_game"] is True

            ws.send_json({"type": "retire"})
            msg = ws.receive_json()
            assert msg["type"] == "game_over"
            succ = msg["succession"]
            assert succ["pending"] is True
            assert succ["predecessor"]["name"] == "Aria"
            assert succ["predecessor"]["end_reason"] == "retire"
            assert "Aria" in succ["headline"]
            assert len(succ["inheritance"]) == 3

            assert self.session.game is not None
            assert self.session.game.campaign.pending_succession is True
            assert self.session.game.game_over is True

    def test_retire_twice_rejected(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "retire"})
            ws.receive_json()

            ws.send_json({"type": "retire"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "already" in msg["text"].lower() or "pending" in msg["text"].lower()

    def test_request_succession_creation_without_game(self, client: Any) -> None:
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "request_succession_creation"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_request_succession_creation_without_pending(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "request_succession_creation"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_request_succession_creation_succeeds_after_retire(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "retire"})
            ws.receive_json()

            ws.send_json({"type": "request_succession_creation"})
            msg = ws.receive_json()
            assert msg["type"] == "succession_creation_options"
            assert "creation_options" in msg
            assert msg["current_setting_id"] == "classic"

    def test_start_succession_without_pending(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "start_succession", "creation_data": {}})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_start_succession_malformed_creation_data(self, client: Any) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "retire"})
            ws.receive_json()

            ws.send_json({"type": "start_succession"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

            ws.send_json({"type": "start_succession", "creation_data": "not_a_dict"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
