#!/usr/bin/env python3
"""Server session state. One active session at a time.

All mutable state lives here. Handlers receive the session object,
never access globals. This makes the server testable and the state
transitions explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from starlette.websockets import WebSocket

from ..engine.models import BrainResult, EngineConfig, GameState, RollResult, TurnSnapshot


@dataclass
class BurnOffer:
    """Pending momentum burn offer. Stored between burn_offer and burn_momentum messages."""

    roll: RollResult
    new_result: str
    cost: int
    brain: BrainResult
    player_words: str
    pre_snapshot: TurnSnapshot
    chaos_interrupt: str | None = None


@dataclass
class Session:
    """All mutable server state. One instance per server lifetime."""

    player: str = ""
    game: GameState | None = None
    chat_messages: list[dict] = field(default_factory=list)
    config: EngineConfig = field(default_factory=EngineConfig)
    save_name: str = "autosave"
    processing: bool = False
    active_ws: WebSocket | None = field(default=None, repr=False)
    pending_burn: BurnOffer | None = None

    @property
    def has_game(self) -> bool:
        return self.game is not None

    def clear_game(self) -> None:
        """Reset game state for new player or new game."""
        self.game = None
        self.chat_messages = []
        self.save_name = "autosave"
        self.pending_burn = None

    def append_chat(self, role: str, content: str, **extra: Any) -> None:
        """Append a message to chat history."""
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        self.chat_messages.append(msg)

    def pop_last_user_message(self) -> None:
        """Remove the last user message (on turn failure)."""
        if self.chat_messages and self.chat_messages[-1].get("role") == "user":
            self.chat_messages.pop()

    def replace_last_assistant(self, content: str) -> None:
        """Replace the last assistant message content (momentum burn rewrites narration)."""
        for msg in reversed(self.chat_messages):
            if msg.get("role") == "assistant":
                msg["content"] = content
                break

    def orphan_input(self) -> str | None:
        """Return the last user message text if it has no response, else None."""
        if self.chat_messages and self.chat_messages[-1].get("role") == "user":
            return self.chat_messages[-1].get("content", "")
        return None

    def filtered_messages(self) -> list[dict]:
        """Chat messages for client display — no audio binary, no recaps."""
        return [
            {k: v for k, v in m.items() if k not in ("audio_bytes", "audio_format")}
            for m in self.chat_messages if not m.get("recap")
        ]
