from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from starlette.websockets import WebSocket, WebSocketState
from typing_extensions import override

from straightjacket.engine.ai.provider_base import AIResponse
from tests._helpers import make_game_state, make_npc

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import Message

    from straightjacket.engine.ai.provider_base import AICallSpec
    from straightjacket.engine.models import GameState


class RecordingWebSocket(WebSocket):
    def __init__(self) -> None:
        super().__init__({"type": "websocket"}, self._client_leaves, self._record)
        self.sent: list[dict[str, Any]] = []
        self.client_state = WebSocketState.CONNECTED
        self.application_state = WebSocketState.CONNECTED

    async def _client_leaves(self) -> Message:
        return {"type": "websocket.disconnect", "code": 1000}

    async def _record(self, message: Message) -> None:
        self.sent.append(json.loads(message["text"]))


class DroppedWebSocket(RecordingWebSocket):
    @override
    async def _record(self, message: Message) -> None:
        raise OSError


class ScriptedProvider(ABC):
    @abstractmethod
    def create_message(self, spec: AICallSpec) -> AIResponse: ...

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        response = self.create_message(spec)
        on_text(response.content)
        return response


class MockProvider(ScriptedProvider):
    def __init__(self, response_content: str = "", fail: bool = False) -> None:
        self._content = response_content
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    @override
    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.calls.append({"system": spec.system, "json_schema": spec.json_schema, "messages": spec.messages})
        if self._fail:
            raise ConnectionError("mock fail")
        return AIResponse(content=self._content, usage={"input_tokens": 10, "output_tokens": 10})


def make_test_game() -> GameState:
    g = make_game_state(
        player_name="Hero",
        setting_id="classic",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A dark world.",
        stats={"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2},
        backstory="Was a farmer.",
    )
    g.narrative.scene_count = 5
    g.world.current_location = "Tavern"
    g.world.time_of_day = "evening"
    g.world.chaos_factor = 5
    g.resources.meters["health"] = 3
    g.resources.meters["spirit"] = 4
    g.preferences.content_lines = "no spiders"
    g.preferences.player_wishes = "a loyal dog"
    g.npcs = [make_npc(id="npc_1", name="Kira", disposition="friendly")]
    return g
