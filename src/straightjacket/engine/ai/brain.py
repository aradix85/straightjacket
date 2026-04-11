#!/usr/bin/env python3
"""AI Brain calls: action parsing via two-phase call.

Phase 1 (optional): tool loop for context queries (NPC details, oracle rolls).
Phase 2: json_schema call for structured classification.

json_schema enforces complete output — without it the model defaults to dialog.
"""

import html
import json
import re

from ..config_loader import cfg, sampling_params
from ..logging_util import log
from ..models import BrainResult, EngineConfig, GameState, Revelation
from ..prompt_blocks import (
    content_boundaries_block,
    get_narration_lang,
)
from ..prompt_loader import get_prompt
from .provider_base import AIProvider, create_with_retry
from .schemas import get_brain_output_schema


def _build_moves_block(setting_id: str) -> str:
    """Build <moves> instruction block directing Brain to use available_moves tool."""
    return (
        "<moves>\n"
        "  Call available_moves to get the list of moves the player can make right now.\n"
        "  The tool returns move keys, stats, and roll types based on current game state.\n"
        "  dialog = pure conversation, no risk. ask_the_oracle = yes/no question about the fiction.\n"
        "  world_shaping = player declares something about the world (wits|heart|shadow).\n"
        "</moves>"
    )


# ── JSON extraction from text (used by Director) ────────────

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Extract JSON from text response. Handles bare JSON and fenced blocks."""
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


# ── Brain ────────────────────────────────────────────────────


def call_brain(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> BrainResult:
    """Classify player input into a game move.

    Two-phase call:
    1. Tool loop (optional): Brain queries NPCs or oracles if needed.
    2. json_schema call: enforces complete classification output.
    """
    from ..tools import get_tools, run_tool_loop

    _c = cfg()
    _cfg = config or EngineConfig()
    _brain_lang = get_narration_lang(_cfg)

    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[:100]}")

    system = get_prompt(
        "brain_parser",
        lang=_brain_lang,
        content_boundaries_block=content_boundaries_block(game),
        moves_block=_build_moves_block(game.setting_id),
    )

    w = game.world
    res = game.resources

    # Minimal NPC list for target_npc resolution
    npc_lines = []
    for n in game.npcs:
        if n.status in ("active", "background"):
            entry = f"- {n.name} (id:{n.id})"
            if n.aliases:
                entry += f" aliases:{','.join(n.aliases)}"
            npc_lines.append(entry)
    npc_list = "\n".join(npc_lines) or "(none)"

    user_msg = f"""<state>
loc:{w.current_location} | ctx:{w.current_scene_context}
time:{w.time_of_day or "unspecified"}
{game.player_name} H{res.health} Sp{res.spirit} Su{res.supply} M{res.momentum} chaos:{w.chaos_factor} | E{game.edge} H{game.heart} I{game.iron} Sh{game.shadow} W{game.wits}
</state>
<npcs>{npc_list}</npcs>
<input>{player_message}</input>"""

    tools = get_tools("brain")

    try:
        # Phase 1: tool loop for optional context queries
        tool_context = ""
        if tools:
            response = create_with_retry(
                provider,
                max_retries=1,
                model=_c.ai.brain_model,
                max_tokens=_c.ai.max_tokens.brain,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                tools=tools,
                **sampling_params("brain"),
                log_role="brain",
            )

            if response.stop_reason == "tool_use":
                final_content, tool_log = run_tool_loop(
                    provider,
                    response,
                    role="brain",
                    game=game,
                    model=_c.ai.brain_model,
                    system=system,
                    messages=[{"role": "user", "content": user_msg}],
                    max_tokens=_c.ai.max_tokens.brain,
                    max_tool_rounds=_c.ai.max_tool_rounds.brain,
                    **sampling_params("brain"),
                    log_role="brain",
                )
                if final_content.strip():
                    tool_context = f"\n<tool_results>\n{final_content[:1500]}\n</tool_results>"
                log(f"[Brain] Phase 1: {len(tool_log)} tool calls")
            else:
                log("[Brain] Phase 1: no tools called")

        # Phase 2: json_schema call for classification
        phase2_msg = user_msg
        if tool_context:
            phase2_msg = user_msg + tool_context

        response2 = create_with_retry(
            provider,
            max_retries=_c.ai.max_retries.brain,
            model=_c.ai.brain_model,
            max_tokens=_c.ai.max_tokens.brain,
            system=system,
            messages=[{"role": "user", "content": phase2_msg}],
            json_schema=get_brain_output_schema(),
            **sampling_params("brain"),
            log_role="brain",
        )

        result = BrainResult.from_dict(json.loads(response2.content))
        log(f"[Brain] move={result.move}, stat={result.stat}, intent={result.player_intent[:60]}")
        return result

    except Exception as e:
        log(f"[Brain] Failed ({type(e).__name__}: {e}), treating as dialog", level="warning")
        return BrainResult(move="dialog", dialog_only=True, player_intent=player_message, approach="error")


# ── Revelation check ─────────────────────────────────────────


def call_revelation_check(
    provider: AIProvider, narration: str, revelation: Revelation, config: EngineConfig | None = None
) -> bool:
    """Check whether the narrator actually wove a pending revelation into the narration."""
    from .schemas import REVELATION_CHECK_SCHEMA

    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    rev_content = revelation.content
    rev_weight = revelation.dramatic_weight

    _c = cfg()

    system = (
        f"You are a story-consistency checker for an RPG engine. "
        f"Your task is to determine whether a specific revelation was meaningfully "
        f"present in a narrator's prose passage.\n\n"
        f"A revelation is considered CONFIRMED (revelation_confirmed=true) when:\n"
        f"- The core insight or twist is clearly present in the narration, OR\n"
        f"- It is strongly and unambiguously foreshadowed (not just vaguely hinted), OR\n"
        f"- A character explicitly reveals information that matches the revelation content.\n\n"
        f"A revelation is NOT confirmed (revelation_confirmed=false) when:\n"
        f"- The narration does not touch on the revelation at all, OR\n"
        f"- Only a very superficial or incidental reference appears that a reader "
        f"would not recognise as the revelation.\n\n"
        f"The narration is in {lang}. Reason in {lang} if helpful, but the JSON fields "
        f"must always be populated."
    )

    prompt = (
        f'<revelation weight="{html.escape(rev_weight, quote=True)}">{html.escape(rev_content)}</revelation>\n\n'
        f"<narration>{narration}</narration>\n\n"
        f"Was this revelation meaningfully present in the narration above?"
    )

    try:
        response = create_with_retry(
            provider,
            max_retries=_c.ai.max_retries.revelation_check,
            model=_c.ai.brain_model,
            max_tokens=_c.ai.max_tokens.revelation_check,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=REVELATION_CHECK_SCHEMA,
            **sampling_params("revelation_check"),
            log_role="brain_correction",
        )
        result = json.loads(response.content)
        confirmed = result.get("revelation_confirmed", True)
        reasoning = result.get("reasoning", "")
        log(f"[Revelation] Check for '{revelation.id}': confirmed={confirmed} — {reasoning}")
        return confirmed
    except Exception as e:
        log(
            f"[Revelation] Check failed ({type(e).__name__}: {e}), defaulting to confirmed=True to avoid pending loop",
            level="warning",
        )
        return True
