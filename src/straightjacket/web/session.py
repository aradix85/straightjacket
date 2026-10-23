from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from starlette.websockets import WebSocket

from ..engine.game import BurnOffer
from ..engine.models import GameState


@dataclass(kw_only=True)
class Session:
    player: str
    game: GameState | None
    chat_messages: list[dict[str, Any]] = field(default_factory=list)
    processing: bool
    active_ws: WebSocket | None = field(repr=False)
    pending_burn: BurnOffer | None

    def take_game(self, game: GameState, chat_messages: list[dict[str, Any]]) -> None:
        self.game = game
        self.chat_messages = chat_messages
        self.pending_burn = None

    def clear_game(self) -> None:
        self.game = None
        self.chat_messages = []
        self.pending_burn = None

    def append_chat(self, role: str, content: str, **extra: Any) -> None:
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        self.chat_messages.append(msg)

    def pop_last_user_message(self) -> None:
        if self.chat_messages and self.chat_messages[-1]["role"] == "user":
            self.chat_messages.pop()

    def replace_last_assistant(self, content: str) -> None:
        for msg in reversed(self.chat_messages):
            if msg["role"] == "assistant":
                msg["content"] = content
                break

    def orphan_input(self) -> str | None:
        if self.chat_messages and self.chat_messages[-1]["role"] == "user":
            result: str = self.chat_messages[-1]["content"]
            return result
        return None


def new_session() -> Session:
    return Session(
        player="",
        game=None,
        processing=False,
        active_ws=None,
        pending_burn=None,
    )
