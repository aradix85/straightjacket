from __future__ import annotations

import json

from ..ai.provider_base import AIProvider, AIResponse, create_with_retry
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .registry import get_handler, get_tools


def execute_tool_call(role: str, tool_call: dict, game: GameState) -> str:
    name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})

    handler = get_handler(role, name)
    if handler is None:
        log(f"[Tools] Unknown tool: {name} (role={role})", level="warning")
        return json.dumps({"error": f"unknown tool: {name}"})

    try:
        result = handler(game=game, **arguments)
        if isinstance(result, dict):
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
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    max_tool_rounds: int = 5,
    temperature: float | None = None,
    top_p: float | None = None,
    extra_body: dict | None = None,
    log_role: str = "",
) -> tuple[str, list[dict]]:
    tool_log: list[dict] = []
    current = response
    conversation = list(messages)

    for round_num in range(max_tool_rounds):
        if current.stop_reason != "tool_use" or not current.tool_calls:
            break

        log(f"[Tools] Round {round_num + 1}: {len(current.tool_calls)} tool call(s)")

        assistant_msg: dict = {"role": "assistant", "content": current.content or ""}
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

        current = create_with_retry(
            provider,
            max_retries=eng().retry.constraint_check_max_retries,
            model=model,
            system=system,
            messages=conversation,
            max_tokens=max_tokens,
            tools=get_tools(role),
            temperature=temperature,
            top_p=top_p,
            extra_body=extra_body,
            log_role=log_role,
        )

    if current.stop_reason == "tool_use":
        log(f"[Tools] Hit max rounds ({max_tool_rounds}), forcing text from last response", level="warning")

    final_content = current.content or ""
    log(f"[Tools] Loop done: {len(tool_log)} tool call(s), {len(final_content)} chars response")
    return final_content, tool_log
