from __future__ import annotations

from typing import Any
import inspect
import json
from dataclasses import replace

from ..ai.provider_base import AICallSpec, AIProvider, AIResponse, create_with_retry
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .registry import get_handler, get_tools


def _unknown_arguments(handler: Any, arguments: dict[str, Any]) -> list[str]:
    params = inspect.signature(handler).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return []
    return sorted(key for key in arguments if key not in params or key == "game")


def execute_tool_call(role: str, tool_call: dict[str, Any], game: GameState) -> str:
    name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})

    handler = get_handler(role, name)
    if handler is None:
        log(f"[Tools] Unknown tool: {name} (role={role})", level="warning")
        return json.dumps({"error": f"unknown tool: {name}"})

    unknown = _unknown_arguments(handler, arguments)
    if unknown:
        log(f"[Tools] {name}: ignored arguments it does not take: {', '.join(unknown)}", level="warning")
        arguments = {key: value for key, value in arguments.items() if key not in unknown}

    try:
        result = handler(game=game, **arguments)
        if isinstance(result, dict):
            if unknown:
                result = {**result, "ignored_arguments": unknown}
            return json.dumps(result, ensure_ascii=False)
        return str(result)
    except Exception as e:
        log(f"[Tools] {name} failed: {e}", level="warning")
        return json.dumps({"error": f"{name} failed: {e}"})


def run_tool_loop(
    provider: AIProvider,
    response: AIResponse,
    *,
    role: str,
    game: GameState,
    initial_spec: AICallSpec,
) -> tuple[str, list[dict[str, Any]]]:
    tool_log: list[dict[str, Any]] = []
    current = response
    conversation = list(initial_spec.messages)
    max_tool_rounds = eng().pacing.max_tool_rounds

    for round_num in range(max_tool_rounds):
        if current.stop_reason != "tool_use" or not current.tool_calls:
            break

        log(f"[Tools] Round {round_num + 1}: {len(current.tool_calls)} tool call(s)")

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": current.content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.get("id", f"call_{round_num}_{i}"),
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                },
            }
            for i, tc in enumerate(current.tool_calls)
        ]
        conversation.append(assistant_msg)

        _trunc = eng().truncations
        for tc in current.tool_calls:
            result_str = execute_tool_call(role, tc, game)
            tool_log.append(
                {
                    "name": tc["name"],
                    "arguments": tc.get("arguments", {}),
                    "result": result_str[: _trunc.prompt_long],
                }
            )
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{round_num}"),
                    "content": result_str,
                }
            )
            log(f"[Tools] {tc['name']}({tc.get('arguments', {})}) → {result_str[: _trunc.log_medium]}")

        next_spec = replace(
            initial_spec,
            messages=conversation,
            max_retries=eng().retry.tool_loop_round_max_retries,
            tools=get_tools(role),
            json_schema=None,
        )
        current = create_with_retry(provider, next_spec)

    if current.stop_reason == "tool_use":
        log(f"[Tools] Hit max rounds ({max_tool_rounds}), forcing text from last response", level="warning")

    final_content = current.content or ""
    log(f"[Tools] Loop done: {len(tool_log)} tool call(s), {len(final_content)} chars response")
    return final_content, tool_log
