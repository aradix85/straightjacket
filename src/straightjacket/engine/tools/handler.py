from __future__ import annotations

import json
from typing import TYPE_CHECKING

from straightjacket.engine.logging_util import log
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.tools.registry import get_handler

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState


def execute_tool_call(name: str, arguments: dict[str, object], game: GameState) -> str:
    handler = get_handler(name)
    if handler is None:
        log(f"[Tools] Unknown tool: {name}", level="warning")
        return json.dumps({"error": get_prompt("tool_error_unknown", tool=name)})
    result = handler(game)
    if arguments:
        ignored = sorted(arguments)
        log(f"[Tools] {name}: ignored arguments it does not take: {', '.join(ignored)}", level="warning")
        result = {**result, "ignored_arguments": ignored}
    return json.dumps(result, ensure_ascii=False)
