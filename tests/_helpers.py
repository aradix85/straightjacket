"""Shared test helpers.

GameState.stats is a required kwarg in production; tests that don't care
about specific stat values get the canonical 3-2-2-1-1 array here. Tests
that do care pass stats= themselves, which wins via setdefault.
"""

from __future__ import annotations

from typing import Any


def make_game_state(**kwargs: Any) -> Any:
    from straightjacket.engine.models import GameState

    kwargs.setdefault("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    return GameState(**kwargs)
