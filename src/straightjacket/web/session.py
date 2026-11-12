from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from straightjacket.engine.persistence import ChatMessage

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from straightjacket.engine.game import BurnOffer
    from straightjacket.engine.models import GameState


@dataclass(kw_only=True)
class Session:
    player: str
    game: GameState | None
    chat_messages: list[ChatMessage] = field(default_factory=list)
    processing: bool
    active_ws: WebSocket | None = field(repr=False)
    pending_burn: BurnOffer | None

    def take_game(self, game: GameState, chat_messages: list[ChatMessage]) -> None:
        self.game = game
        self.chat_messages = chat_messages
        self.pending_burn = None

    def begin_game(self, game: GameState, opening: str) -> None:
        self.take_game(game, [])
        self.append_chat("assistant", opening)

    def clear_game(self) -> None:
        self.game = None
        self.chat_messages = []
        self.pending_burn = None

    def append_chat(self, role: str, content: str, *, epilogue: bool = False) -> None:
        self.chat_messages.append(ChatMessage(role=role, content=content, epilogue=epilogue))

    def pop_last_user_message(self) -> None:
        if self.chat_messages and self.chat_messages[-1].role == "user":
            self.chat_messages.pop()

    def replace_last_assistant(self, content: str) -> None:
        for msg in reversed(self.chat_messages):
            if msg.role == "assistant":
                msg.content = content
                break

    def orphan_input(self) -> str | None:
        if self.chat_messages and self.chat_messages[-1].role == "user":
            return self.chat_messages[-1].content
        return None


def new_session() -> Session:
    return Session(
        player="",
        game=None,
        processing=False,
        active_ws=None,
        pending_burn=None,
    )
