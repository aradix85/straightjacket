from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game import BurnOffer
from straightjacket.engine.models import (
    GameState,
    RollResult,
)
from straightjacket.engine.persistence import save_game
from straightjacket.engine.user_management import create_user
from straightjacket.i18n import t
from straightjacket.web import handlers, server
from straightjacket.web.serializers import (
    build_creation_options,
    build_narrative_status,
    highlight_dialog,
)
from straightjacket.web.server import app
from straightjacket.web.session import new_session
from tests._helpers import (
    make_act,
    make_blueprint,
    make_brain_result,
    make_clock,
    make_game_state,
    make_npc,
    make_scene_setup,
    use_users_dir,
)


class TestSession:
    @staticmethod
    def test_initial_state() -> None:
        s = new_session()
        assert not s.player
        assert s.game is None
        assert s.processing is False
        assert not s.chat_messages
        assert s.pending_burn is None

    @staticmethod
    def test_append_chat() -> None:
        s = new_session()
        s.append_chat("user", "hello")
        s.append_chat("assistant", "world")
        assert len(s.chat_messages) == 2
        assert s.chat_messages[0] == {"role": "user", "content": "hello"}
        assert s.chat_messages[1] == {"role": "assistant", "content": "world"}

    @staticmethod
    def test_append_chat_extra_fields() -> None:
        s = new_session()
        s.append_chat("assistant", "epilogue text", epilogue=True)
        assert s.chat_messages[0]["epilogue"] is True

    @staticmethod
    def test_an_input_without_its_narration_is_the_orphan() -> None:
        s = new_session()
        assert s.orphan_input() is None
        s.append_chat("user", "action")
        s.append_chat("assistant", "narration")
        assert s.orphan_input() is None
        s.append_chat("user", "orphaned action")
        assert s.orphan_input() == "orphaned action"

    @staticmethod
    def test_only_a_last_user_message_is_popped() -> None:
        s = new_session()
        s.append_chat("user", "first")
        s.append_chat("assistant", "response")
        s.pop_last_user_message()
        assert [m["content"] for m in s.chat_messages] == ["first", "response"]
        s.append_chat("user", "second")
        s.pop_last_user_message()
        assert [m["content"] for m in s.chat_messages] == ["first", "response"]

    @staticmethod
    def test_the_last_narration_is_replaced_past_a_later_input() -> None:
        s = new_session()
        s.append_chat("assistant", "first")
        s.append_chat("user", "second")
        s.replace_last_assistant("replaced")
        assert [m["content"] for m in s.chat_messages] == ["replaced", "second"]

    @staticmethod
    def test_clear_game() -> None:
        s = new_session()
        s.game = make_game_state(player_name="Test")
        s.chat_messages = [{"role": "assistant", "content": "x"}]
        s.pending_burn = BurnOffer(
            roll=RollResult(1, 1, 1, "wits", 2, 4, "MISS", "adventure/face_danger", match=True),
            new_result="WEAK_HIT",
            cost=5,
            brain=make_brain_result(),
            player_words="x",
            scene_setup=make_scene_setup(scene_type="expected"),
            ds_move=None,
            random_events=[],
            facts=[],
            resume_snapshot=make_game_state().snapshot(),
        )
        s.clear_game()
        game_after: GameState | None = s.game
        offer_after: BurnOffer | None = s.pending_burn
        assert game_after is None
        assert not s.chat_messages
        assert offer_after is None


class TestHighlightDialog:
    @staticmethod
    def test_no_quotes_unchanged() -> None:
        text = "The wind howled through the broken windows."
        assert highlight_dialog(text) == text


class TestBuildNarrativeStatus:
    @staticmethod
    def _game() -> GameState:
        game = make_game_state(
            player_name="Kael",
            character_concept="Scholar",
            stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
            setting_genre="dark_fantasy",
        )
        game.resources.meters["health"] = 4
        game.resources.meters["spirit"] = 3
        game.resources.meters["supply"] = 5
        game.resources.meters["momentum"] = 5
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

    def test_the_status_tells_the_character_place_people_and_dangers_in_words(self) -> None:
        text = build_narrative_status(self._game())
        for told in ("Kael", "bruised", "shaken", "well-equipped", "Library", "Mira", "Ghost", "Doom"):
            assert told in text
        assert "Lore Figure" not in text

    def test_the_status_names_the_act_of_the_story(self) -> None:
        game = self._game()
        game.narrative.story_blueprint = make_blueprint(
            central_conflict="test",
            antagonist_force="villain",
            thematic_thread="theme",
            acts=[make_act(title="Begin", scene_range=[1, 10], mood="dark")],
        )
        assert "Begin" in build_narrative_status(game)


class TestBuildCreationOptions:
    @staticmethod
    def test_every_playable_setting_offers_its_paths_by_id_and_title() -> None:
        settings = build_creation_options()["settings"]
        assert settings
        assert "delve" not in [s["id"] for s in settings]
        for s in settings:
            assert all(s[key] for key in ("id", "title", "paths"))
            assert all(p["id"] and p["title"] for p in s["paths"])


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def _fresh_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "active_session", new_session())


@pytest.fixture
def _players_in_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    users = tmp_path / "users"
    users.mkdir()
    use_users_dir(monkeypatch, users)


@pytest.mark.usefixtures("_fresh_session")
class TestWebSocket:
    @staticmethod
    def test_full_connection_flow(client: TestClient) -> None:
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
            assert msg["default_save"] == eng().persistence.default_save_name

            ws.send_json({"type": "delete_player", "name": "ws_flow"})
            msg = ws.receive_json()
            assert msg["type"] == "players_list"
            assert "ws_flow" not in msg["players"]

    @staticmethod
    def test_reconnect_resends_player_state(client: TestClient) -> None:
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

    @staticmethod
    def test_an_unexpected_handler_error_is_reported_and_the_connection_stays(
        client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken(_player: str) -> list[dict[str, Any]]:
            msg = "boom"
            raise KeyError(msg)

        monkeypatch.setattr(handlers, "list_saves_with_info", broken)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"type": "create_player", "name": "ws_broken"})
            ws.receive_json()
            ws.send_json({"type": "list_saves"})
            assert ws.receive_json() == {"type": "error", "text": t("error.unexpected")}
            ws.send_json({"type": "delete_player", "name": "ws_broken"})
            assert ws.receive_json()["type"] == "players_list"

    @staticmethod
    @pytest.mark.parametrize(
        ("origin", "host"),
        [
            (None, "localhost:8081"),
            ("http://localhost:8081", "localhost:8081"),
            ("http://127.0.0.1:8081", "localhost:8081"),
            ("http://[::1]:8081", "localhost:8081"),
            ("http://192.168.1.10:8081", "192.168.1.10:8081"),
            ("http://[fe80::1]:8081", "[fe80::1]:8081"),
        ],
    )
    def test_a_page_from_this_machine_or_from_the_address_it_reaches_connects(
        client: TestClient, origin: str | None, host: str
    ) -> None:
        headers = {"host": host, **({"origin": origin} if origin else {})}
        with client.websocket_connect("/ws", headers=headers) as ws:
            assert ws.receive_json()["type"] == "ui_strings"

    @staticmethod
    @pytest.mark.parametrize(
        ("origin", "host"),
        [
            ("https://evil.example", "localhost:8081"),
            ("http://192.168.1.66:8081", "192.168.1.10:8081"),
            ("http://192.168.1.10:9999", "192.168.1.10:8081"),
            ("http://rebind.example:8081", "rebind.example:8081"),
            ("http://[::1", "localhost:8081"),
        ],
    )
    def test_a_page_from_anywhere_else_is_refused(client: TestClient, origin: str, host: str) -> None:
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/ws", headers={"host": host, "origin": origin}) as ws,
        ):
            ws.receive_json()


@pytest.mark.usefixtures("_players_in_tmp", "_fresh_session")
class TestSuccessionWebSocket:
    @staticmethod
    def _seed_session(player: str = "ws_succ") -> None:
        create_user(player)
        game = make_game_state(
            player_name="Aria",
            pronouns="she/her",
            character_concept="outlander",
            background_vow="avenge sister",
            setting_id="starforged",
        )
        game.campaign.legacy["quests"].ticks = 24
        game.narrative.scene_count = 5
        save_game(game, player, [{"role": "assistant", "content": "..."}], "autosave")

    @staticmethod
    def _drain_initial(ws: Any) -> None:
        ws.receive_json()
        ws.receive_json()

    def test_retire_without_game_no_op(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "retire"})

            assert server.active_session.game is None
            assert server.active_session.processing is False

    def test_retire_with_game_prepares_succession(self, client: TestClient) -> None:
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
            assert succ["title"] == t("succession.title_retire")
            assert "Aria" in succ["headline"]
            assert len(succ["inheritance"]) == 3

            assert server.active_session.game is not None
            assert server.active_session.game.campaign.pending_succession is True
            assert server.active_session.game.game_over is True

    def test_retire_twice_rejected(self, client: TestClient) -> None:
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

    def test_request_succession_creation_without_game(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "request_succession_creation"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_request_succession_creation_without_pending(self, client: TestClient) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "request_succession_creation"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_request_succession_creation_succeeds_after_retire(self, client: TestClient) -> None:
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
            assert msg["current_setting_id"] == "starforged"

    def test_start_succession_without_pending(self, client: TestClient) -> None:
        self._seed_session()
        with client.websocket_connect("/ws") as ws:
            self._drain_initial(ws)
            ws.send_json({"type": "select_player", "name": "ws_succ"})
            ws.receive_json()
            ws.send_json({"type": "start_succession", "creation_data": {}})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_start_succession_malformed_creation_data(self, client: TestClient) -> None:
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


def test_highlight_dialog_never_touches_the_markup_it_inserts() -> None:
    text = '\u201cRun,\u201d she says. He answers, "Not yet." \u2018Fine.\u2019'
    assert highlight_dialog(text) == (
        '\u201c<span class="dialog">Run,</span>\u201d she says. '
        'He answers, "<span class="dialog">Not yet.</span>" '
        '\u2018<span class="dialog">Fine.</span>\u2019'
    )
