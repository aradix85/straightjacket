#!/usr/bin/env python3
"""Tests for the web module: session state, serializers, WebSocket handlers.

Unit tests for Session and serializers need no server.
Integration tests use Starlette's TestClient with websocket_connect().

The web module imports the real engine (not the conftest stub), so we
use a local load_engine fixture that loads real engine.yaml.

Run: python -m pytest tests/test_web.py -v
"""


import pytest

from straightjacket.engine import engine_loader
from straightjacket.engine.models import (
    BrainResult, ClockData, GameState, NpcData, RollResult, TurnSnapshot,
)
from straightjacket.web.session import BurnOffer, Session
from straightjacket.web.serializers import (
    build_creation_options,
    build_roll_data,
    build_state,
    highlight_dialog,
)


@pytest.fixture()
def load_engine():
    """Load real engine.yaml."""
    engine_loader._eng = None
    engine_loader.eng()


# ── Session dataclass ─────────────────────────────────────────

class TestSession:
    def test_initial_state(self):
        s = Session()
        assert s.player == ""
        assert s.game is None
        assert s.has_game is False
        assert s.processing is False
        assert s.chat_messages == []
        assert s.pending_burn is None

    def test_append_chat(self):
        s = Session()
        s.append_chat("user", "hello")
        s.append_chat("assistant", "world")
        assert len(s.chat_messages) == 2
        assert s.chat_messages[0] == {"role": "user", "content": "hello"}
        assert s.chat_messages[1] == {"role": "assistant", "content": "world"}

    def test_append_chat_extra_fields(self):
        s = Session()
        s.append_chat("assistant", "epilogue text", epilogue=True)
        assert s.chat_messages[0]["epilogue"] is True

    def test_orphan_input_none_when_assistant_last(self):
        s = Session()
        s.append_chat("user", "action")
        s.append_chat("assistant", "narration")
        assert s.orphan_input() is None

    def test_orphan_input_returns_text_when_user_last(self):
        s = Session()
        s.append_chat("user", "orphaned action")
        assert s.orphan_input() == "orphaned action"

    def test_orphan_input_none_when_empty(self):
        s = Session()
        assert s.orphan_input() is None

    def test_pop_last_user_message(self):
        s = Session()
        s.append_chat("user", "first")
        s.append_chat("assistant", "response")
        s.append_chat("user", "second")
        s.pop_last_user_message()
        assert len(s.chat_messages) == 2
        assert s.chat_messages[-1]["role"] == "assistant"

    def test_pop_last_user_message_noop_when_assistant_last(self):
        s = Session()
        s.append_chat("user", "x")
        s.append_chat("assistant", "y")
        s.pop_last_user_message()
        assert len(s.chat_messages) == 2

    def test_replace_last_assistant(self):
        s = Session()
        s.append_chat("user", "input")
        s.append_chat("assistant", "original")
        s.replace_last_assistant("replaced")
        assert s.chat_messages[-1]["content"] == "replaced"

    def test_replace_last_assistant_skips_user(self):
        s = Session()
        s.append_chat("assistant", "first")
        s.append_chat("user", "second")
        s.replace_last_assistant("replaced")
        assert s.chat_messages[0]["content"] == "replaced"

    def test_clear_game(self):
        s = Session()
        s.game = GameState(player_name="Test")
        s.chat_messages = [{"role": "assistant", "content": "x"}]
        s.save_name = "custom"
        s.pending_burn = BurnOffer(
            roll=RollResult(1, 1, 1, 1, "wits", 2, 4, "MISS", "face_danger"),
            new_result="WEAK_HIT", cost=5,
            brain=BrainResult(), player_words="x",
            pre_snapshot=TurnSnapshot(),
        )
        s.clear_game()
        assert s.game is None
        assert s.chat_messages == []
        assert s.save_name == "autosave"
        assert s.pending_burn is None

    def test_has_game_property(self):
        s = Session()
        assert s.has_game is False
        s.game = GameState()
        assert s.has_game is True

    def test_filtered_messages_strips_audio_and_recaps(self):
        s = Session()
        s.chat_messages = [
            {"role": "assistant", "content": "narration", "audio_bytes": b"\x00"},
            {"role": "user", "content": "action"},
            {"role": "assistant", "content": "recap", "recap": True},
        ]
        filtered = s.filtered_messages()
        assert len(filtered) == 2
        assert "audio_bytes" not in filtered[0]
        assert all(not m.get("recap") for m in filtered)


# ── BurnOffer dataclass ───────────────────────────────────────

class TestBurnOffer:
    def test_fields(self):
        bo = BurnOffer(
            roll=RollResult(1, 2, 3, 4, "iron", 3, 6, "MISS", "strike"),
            new_result="STRONG_HIT", cost=7,
            brain=BrainResult(move="strike", stat="iron"),
            player_words="I attack",
            pre_snapshot=TurnSnapshot(),
            chaos_interrupt="twist",
        )
        assert bo.new_result == "STRONG_HIT"
        assert bo.cost == 7
        assert bo.chaos_interrupt == "twist"

    def test_chaos_interrupt_defaults_none(self):
        bo = BurnOffer(
            roll=RollResult(1, 1, 1, 1, "wits", 1, 3, "MISS", "face_danger"),
            new_result="WEAK_HIT", cost=3,
            brain=BrainResult(), player_words="x",
            pre_snapshot=TurnSnapshot(),
        )
        assert bo.chaos_interrupt is None


# ── Serializers ───────────────────────────────────────────────

class TestHighlightDialog:
    def test_curly_quotes(self):
        text = '\u201cHello,\u201d she said.'
        result = highlight_dialog(text)
        assert '<span class="dialog">' in result
        assert "Hello," in result

    def test_straight_quotes(self):
        result = highlight_dialog('"Hello," she said.')
        assert '<span class="dialog">' in result

    def test_german_quotes(self):
        result = highlight_dialog('\u201eHallo,\u201c sagte sie.')
        assert '<span class="dialog">' in result

    def test_no_quotes_unchanged(self):
        text = "The wind howled through the broken windows."
        assert highlight_dialog(text) == text

    def test_guillemets(self):
        result = highlight_dialog('\u00abBonjour\u00bb dit-elle.')
        assert '<span class="dialog">' in result


class TestBuildRollData:
    def _roll(self, result="STRONG_HIT", move="face_danger"):
        return RollResult(d1=4, d2=3, c1=5, c2=8, stat_name="wits",
                          stat_value=2, action_score=9, result=result,
                          move=move, match=False)

    def test_basic_fields(self, load_engine):
        rd = build_roll_data(self._roll())
        assert rd["result"] == "STRONG_HIT"
        assert rd["move"] == "face_danger"
        assert rd["d1"] == 4
        assert rd["action_score"] == 9

    def test_labels_resolved(self, load_engine):
        rd = build_roll_data(self._roll())
        assert rd["result_label"] != ""
        assert rd["move_label"] != "face_danger"
        assert rd["stat_label"] != "wits"

    def test_consequences_translated(self, load_engine):
        rd = build_roll_data(self._roll("MISS"), consequences=["health -2", "momentum -2"])
        assert len(rd["consequences"]) == 2

    def test_clock_events_from_objects(self, load_engine):
        from straightjacket.engine.models import ClockEvent
        ce = ClockEvent(clock="Doom", trigger="Darkness falls")
        rd = build_roll_data(self._roll(), clock_events=[ce])
        assert rd["clock_events"][0]["clock"] == "Doom"

    def test_clock_events_from_dicts(self, load_engine):
        rd = build_roll_data(self._roll(), clock_events=[{"clock": "X", "trigger": "Y"}])
        assert rd["clock_events"][0]["clock"] == "X"

    def test_brain_position_from_dataclass(self, load_engine):
        brain = BrainResult(position="desperate", effect="great")
        rd = build_roll_data(self._roll(), brain=brain)
        assert rd["position"] == "desperate"
        assert rd["effect"] == "great"

    def test_brain_position_from_dict(self, load_engine):
        rd = build_roll_data(self._roll(), brain={"position": "controlled", "effect": "limited"})
        assert rd["position"] == "controlled"

    def test_match_flag(self, load_engine):
        roll = RollResult(d1=4, d2=3, c1=5, c2=5, stat_name="wits",
                          stat_value=2, action_score=9, result="MISS",
                          move="face_danger", match=True)
        rd = build_roll_data(roll)
        assert rd["match"] is True


class TestBuildState:
    def _game(self):
        game = GameState(player_name="Kael", character_concept="Scholar",
                         edge=1, heart=2, iron=1, shadow=1, wits=2,
                         setting_genre="dark_fantasy")
        game.resources.health = 4
        game.resources.spirit = 3
        game.resources.supply = 5
        game.resources.momentum = 5
        game.world.current_location = "Library"
        game.world.time_of_day = "evening"
        game.world.chaos_factor = 6
        game.narrative.scene_count = 5
        game.npcs = [
            NpcData(id="npc_1", name="Mira", status="active",
                    disposition="friendly", bond=2, bond_max=4),
            NpcData(id="npc_2", name="Ghost", status="deceased",
                    disposition="neutral", bond=0, bond_max=4),
            NpcData(id="npc_3", name="Lore Figure", status="lore",
                    disposition="neutral", bond=0, bond_max=4),
        ]
        game.world.clocks = [
            ClockData(name="Doom", clock_type="threat", segments=6, filled=3),
        ]
        return game

    def test_basic_fields(self, load_engine):
        state = build_state(self._game())
        assert state["player_name"] == "Kael"
        assert state["health"] == 4
        assert state["chaos"] == 6
        assert state["scene"] == 5
        assert state["location"] == "Library"

    def test_stats_have_labels(self, load_engine):
        state = build_state(self._game())
        assert "label" in state["stats"]["edge"]
        assert "value" in state["stats"]["edge"]
        assert state["stats"]["edge"]["value"] == 1

    def test_npcs_filtered(self, load_engine):
        state = build_state(self._game())
        names = [n["name"] for n in state["npcs"]]
        assert "Mira" in names
        assert "Ghost" in names
        assert "Lore Figure" not in names

    def test_npc_disposition_labeled(self, load_engine):
        state = build_state(self._game())
        mira = next(n for n in state["npcs"] if n["name"] == "Mira")
        assert mira["disposition_label"] != ""

    def test_clocks_present(self, load_engine):
        state = build_state(self._game())
        assert len(state["clocks"]) == 1
        assert state["clocks"][0]["name"] == "Doom"
        assert state["clocks"][0]["filled"] == 3

    def test_time_label_resolved(self, load_engine):
        state = build_state(self._game())
        assert state["time_label"] != ""

    def test_story_arc_none_without_blueprint(self, load_engine):
        state = build_state(self._game())
        assert state["story_arc"] is None

    def test_story_arc_present_with_blueprint(self, load_engine):
        from straightjacket.engine.models import StoryAct, StoryBlueprint
        game = self._game()
        game.narrative.story_blueprint = StoryBlueprint(
            central_conflict="test", antagonist_force="villain",
            thematic_thread="theme", structure_type="3act",
            acts=[StoryAct(phase="setup", title="Begin", scene_range=[1, 10], mood="dark")],
        )
        state = build_state(game)
        assert state["story_arc"] is not None
        assert state["story_arc"]["phase"] == "setup"
        assert state["story_arc"]["phase_label"] != ""


class TestBuildCreationOptions:
    def test_returns_settings(self, load_engine):
        opts = build_creation_options()
        assert "settings" in opts
        from straightjacket.engine.datasworn.loader import list_available
        if not list_available():
            pytest.skip("No Datasworn JSON files in data/ — run download_datasworn.py")
        assert len(opts["settings"]) >= 1

    def test_settings_have_paths(self, load_engine):
        opts = build_creation_options()
        for s in opts["settings"]:
            assert "id" in s
            assert "title" in s
            assert "paths" in s
            assert len(s["paths"]) > 0

    def test_delve_excluded(self, load_engine):
        opts = build_creation_options()
        ids = [s["id"] for s in opts["settings"]]
        assert "delve" not in ids

    def test_paths_have_id_and_title(self, load_engine):
        opts = build_creation_options()
        for s in opts["settings"]:
            for p in s["paths"]:
                assert "id" in p
                assert "title" in p


# ── WebSocket integration (via Starlette TestClient) ──────────

class TestWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self, load_engine):
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
    def client(self):
        from starlette.testclient import TestClient
        from straightjacket.web.server import app
        return TestClient(app)

    def test_connect_receives_players_list(self, client):
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "players_list"

    def test_create_and_select_player(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # players_list
            ws.send_json({"type": "create_player", "name": "ws_test"})
            msg = ws.receive_json()
            assert msg["type"] == "player_selected"
            assert msg["name"] == "ws_test"
            assert msg["has_game"] is False
            assert "creation_options" in msg
            # Cleanup
            ws.send_json({"type": "delete_player", "name": "ws_test"})
            ws.receive_json()  # players_list

    def test_create_player_empty_name_errors(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "create_player", "name": ""})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_list_saves_empty_for_new_player(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "create_player", "name": "ws_saves"})
            ws.receive_json()  # player_selected
            ws.send_json({"type": "list_saves"})
            msg = ws.receive_json()
            assert msg["type"] == "saves_list"
            assert msg["saves"] == []
            ws.send_json({"type": "delete_player", "name": "ws_saves"})
            ws.receive_json()

    def test_unknown_message_returns_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "nonexistent_type"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "nonexistent_type" in msg["text"]

    def test_player_input_without_game_errors(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "player_input", "text": "I search"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_delete_player_and_relist(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.send_json({"type": "create_player", "name": "ws_del"})
            ws.receive_json()  # player_selected
            ws.send_json({"type": "delete_player", "name": "ws_del"})
            msg = ws.receive_json()
            assert msg["type"] == "players_list"
            assert "ws_del" not in msg["players"]

    def test_reconnect_resends_player_state(self, client):
        """Simulate reconnect by opening a second WebSocket while player is selected."""
        # First connection: create and select player
        with client.websocket_connect("/ws") as ws1:
            ws1.receive_json()  # players_list
            ws1.send_json({"type": "create_player", "name": "ws_recon"})
            ws1.receive_json()  # player_selected

        # Second connection: should get players_list + player_selected
        with client.websocket_connect("/ws") as ws2:
            msg1 = ws2.receive_json()
            assert msg1["type"] == "players_list"
            msg2 = ws2.receive_json()
            assert msg2["type"] == "player_selected"
            assert msg2["name"] == "ws_recon"
            # Cleanup
            ws2.send_json({"type": "delete_player", "name": "ws_recon"})
            ws2.receive_json()
