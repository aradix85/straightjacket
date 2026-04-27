from __future__ import annotations

from typing import Any


class MockResponse:
    def __init__(self, content: str, stop_reason: str = "complete") -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.tool_calls: list = []
        self.usage = {"input_tokens": 10, "output_tokens": 10}


class MockProvider:
    def __init__(self, response_content: str = "", fail: bool = False) -> None:
        self._content = response_content
        self._fail = fail
        self.calls: list = []

    def create_message(
        self,
        model: str,
        system: str,
        messages: list,
        max_tokens: int,
        json_schema: dict | None = None,
        tools: list | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        extra_body: dict | None = None,
    ) -> MockResponse:
        self.calls.append({"system": system, "json_schema": json_schema, "messages": messages})
        if self._fail:
            raise ConnectionError("mock fail")
        return MockResponse(self._content)


def make_test_game() -> Any:
    from straightjacket.engine.models import GameState

    from tests._helpers import make_npc

    g = GameState(
        player_name="Hero",
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
    g.resources.health = 3
    g.resources.spirit = 4
    g.preferences.content_lines = "no spiders"
    g.preferences.player_wishes = "a loyal dog"
    g.npcs = [make_npc(id="npc_1", name="Kira", disposition="friendly")]
    return g
