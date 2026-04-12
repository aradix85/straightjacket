#!/usr/bin/env python3
"""AI Brain: single-call action classification via prompt injection + json_schema.

Brain receives full game state context (NPCs, moves, tracks) in the prompt.
No tool calling — all info is static and compact. json_schema enforces output.
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


def _build_moves_block(game: GameState) -> str:
    """Build <moves> block with available moves pre-computed by the engine."""
    from ..tools.builtins import available_moves

    data = available_moves(game)
    moves = data.get("moves", [])
    combat_pos = data.get("combat_position", "")

    lines = []
    for m in moves:
        stats = ", ".join(m["stats"]) if m["stats"] else "none"
        lines.append(f"  {m['move']} ({m['name']}) stats:[{stats}] roll:{m['roll_type']}")

    pos_line = f"  combat_position: {combat_pos}" if combat_pos else ""
    return "<moves>\n" + "\n".join(lines) + ("\n" + pos_line if pos_line else "") + "\n</moves>"


def _build_tracks_block(game: GameState) -> str:
    """Build compact tracks context for Brain."""
    tracks = [t for t in game.progress_tracks if t.status == "active"]
    if not tracks:
        return ""
    lines = [f"  {t.name} ({t.track_type}, {t.rank}) {t.filled_boxes}/10" for t in tracks]
    return "<tracks>\n" + "\n".join(lines) + "\n</tracks>"


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
    """Classify player input into a game move. Single call with injected context.

    All game state (NPCs, moves, tracks) is in the prompt. No tool calling.
    fate_question and oracle_table fields on BrainResult are resolved by the
    engine after classification (see turn.py).
    """
    _c = cfg()
    _cfg = config or EngineConfig()
    _brain_lang = get_narration_lang(_cfg)

    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[:100]}")

    system = get_prompt(
        "brain_parser",
        lang=_brain_lang,
        content_boundaries_block=content_boundaries_block(game),
        moves_block=_build_moves_block(game),
    )

    w = game.world

    # NPC list with dispositions for target_npc resolution
    npc_lines = []
    for n in game.npcs:
        if n.status in ("active", "background"):
            entry = f"  {n.name} (id:{n.id}, {n.disposition})"
            if n.aliases:
                entry += f" aliases:{','.join(n.aliases)}"
            npc_lines.append(entry)
    npc_block = "<npcs>\n" + "\n".join(npc_lines) + "\n</npcs>" if npc_lines else "<npcs>(none)</npcs>"

    tracks_block = _build_tracks_block(game)

    user_msg = f"""<state>
loc:{w.current_location} | ctx:{w.current_scene_context}
time:{w.time_of_day or "unspecified"}
{game.player_name} E{game.edge} H{game.heart} I{game.iron} Sh{game.shadow} W{game.wits}
</state>
{npc_block}
{tracks_block}
<input>{player_message}</input>"""

    try:
        response = create_with_retry(
            provider,
            max_retries=_c.ai.max_retries.brain,
            model=_c.ai.brain_model,
            max_tokens=_c.ai.max_tokens.brain,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_brain_output_schema(),
            **sampling_params("brain"),
            log_role="brain",
        )

        result = BrainResult.from_dict(json.loads(response.content))
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
