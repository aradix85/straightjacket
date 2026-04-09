#!/usr/bin/env python3
"""AI Brain calls: action parsing and character/world generation."""

import html
import json

from ..config_loader import cfg, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, EngineConfig, GameState, NpcData, Revelation
from ..prompt_blocks import (
    content_boundaries_block,
    get_narration_lang,
    story_context_block,
)
from ..prompt_loader import get_prompt
from .provider_base import AIProvider, create_with_retry
from .schemas import get_brain_output_schema


def _build_moves_block() -> str:
    """Build <moves> block from engine.yaml move_stats mapping."""
    _e = eng()
    move_stats = _e.move_stats
    lines = [f"  {move}:{stats}" for move, stats in move_stats.items()]
    return "<moves>\n" + "\n".join(lines) + "\n  </moves>"


def call_brain(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> BrainResult:
    _c = cfg()
    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[:100]}")

    def _brain_npc_line(n: NpcData) -> str:
        line = f'- {n.name} (id:{n.id}): {n.disposition}, bond={n.bond}/{n.bond_max}, agenda="{n.agenda}"'
        if n.aliases:
            line += f" aliases:{','.join(n.aliases)}"
        return line

    npc_summary = "\n".join(_brain_npc_line(n) for n in game.npcs if n.status == "active") or "(none)"
    bg_npcs = [n for n in game.npcs if n.status == "background"]
    bg_summary = "\n".join(
        f"- {n.name} (id:{n.id}): {n.disposition}, bond={n.bond}"
        + (f" aliases:{','.join(n.aliases)}" if n.aliases else "")
        for n in bg_npcs
    )
    if bg_summary:
        npc_summary += f"\n(background, not currently present but known):\n{bg_summary}"
    lore_npcs = [n for n in game.npcs if n.status == "lore"]
    if lore_npcs:
        lore_summary = "\n".join(
            f"- {n.name} (id:{n.id}): lore figure" + (f" aliases:{','.join(n.aliases)}" if n.aliases else "")
            for n in lore_npcs
        )
        npc_summary += f"\n(lore, historically significant, never physically present):\n{lore_summary}"
    clock_summary = (
        "\n".join(
            f"- {c.name} ({c.clock_type}): {c.filled}/{c.segments}" for c in game.world.clocks if c.filled < c.segments
        )
        or "(none)"
    )
    last_scenes = (
        "\n".join(f"Scene {s.scene}: {s.rich_summary or s.summary}" for s in game.narrative.session_log[-5:])
        or "(Start)"
    )

    _cfg = config or EngineConfig()
    _brain_lang = get_narration_lang(_cfg)

    system = get_prompt(
        "brain_parser",
        lang=_brain_lang,
        content_boundaries_block=content_boundaries_block(game),
        moves_block=_build_moves_block(),
    )

    campaign_ctx = ""
    cam = game.campaign
    if cam.campaign_history:
        campaign_ctx = (
            f"\n<campaign>Chapter {cam.chapter_number}. Previous: "
            + "; ".join(f"Ch{ch.chapter}:{ch.title}" for ch in cam.campaign_history[-3:])
            + "</campaign>"
        )

    backstory_ctx = ""
    if game.backstory:
        backstory_ctx = f"\n<backstory>{game.backstory}</backstory>"

    w = game.world
    res = game.resources
    loc_hist_n = eng().location.history_size
    user_msg = f"""<state>
loc:{w.current_location} | ctx:{w.current_scene_context}
time:{w.time_of_day or "unspecified"} | prev_locations:{", ".join(w.location_history[-loc_hist_n:]) or "none"}
{game.player_name} H{res.health} Sp{res.spirit} Su{res.supply} M{res.momentum} chaos:{w.chaos_factor} | E{game.edge} H{game.heart} I{game.iron} Sh{game.shadow} W{game.wits}
</state>
<npcs>{npc_summary}</npcs>
<clocks>{clock_summary}</clocks>
<recent>{last_scenes}</recent>
{story_context_block(game)}{campaign_ctx}{backstory_ctx}<input>{player_message}</input>"""

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
        log(f"[Brain] Result: move={result.move}, stat={result.stat}, intent={result.player_intent[:60]}")
        return result
    except Exception as e:
        log(f"[Brain] Structured output failed ({type(e).__name__}: {e}), falling back to dialog", level="warning")
        return BrainResult(move="dialog", dialog_only=True, player_intent=player_message, approach="fallback")


def call_revelation_check(
    provider: AIProvider, narration: str, revelation: Revelation, config: EngineConfig | None = None
) -> bool:
    """Check whether the narrator actually wove a pending revelation into the narration.

    Called after call_narrator_metadata() when pending_revs was non-empty.
    Returns True if the revelation was meaningfully present (and should be marked used),
    False if the narrator skipped or barely touched it (stays pending for next scene).

    On any failure, returns True (safe default: avoid infinite pending loops).
    """
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
