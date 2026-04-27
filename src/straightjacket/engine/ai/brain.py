import html
import json

from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, EngineConfig, GameState, Revelation
from ..prompt_blocks import (
    content_boundaries_block,
    get_narration_lang,
)
from ..prompt_loader import get_prompt
from ..tools.builtins import available_moves
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_brain_output_schema, get_revelation_check_schema


def _build_moves_block(game: GameState) -> str:
    data = available_moves(game)
    moves = data.get("moves", [])
    combat_pos = data.get("combat_position", "")

    trigger_hints = eng().ai_text.brain_trigger_hints

    lines = []
    for m in moves:
        stats = ", ".join(m["stats"]) if m["stats"] else "none"
        hint = trigger_hints.get(m["move"], "")
        trigger = f" when:{hint}" if hint else ""
        lines.append(f"  {m['move']} ({m['name']}) stats:[{stats}] roll:{m['roll_type']}{trigger}")

    pos_line = f"  combat_position: {combat_pos}" if combat_pos else ""
    return "<moves>\n" + "\n".join(lines) + ("\n" + pos_line if pos_line else "") + "\n</moves>"


def build_stats_line(game: GameState) -> str:
    cfg = eng().stats
    parts = [game.player_name]
    for name in cfg.names:
        if name not in cfg.prompt_abbreviations:
            continue
        parts.append(f"{cfg.prompt_abbreviations[name]}{game.stats[name]}")
    return " ".join(parts)


def _build_tracks_block(game: GameState) -> str:
    tracks = [t for t in game.progress_tracks if t.status == "active"]
    if not tracks:
        return ""
    lines = [f"  {t.name} ({t.track_type}, {t.rank}) {t.filled_boxes}/10" for t in tracks]
    return "<tracks>\n" + "\n".join(lines) + "\n</tracks>"


def call_brain(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> BrainResult:
    _cfg = config or EngineConfig()
    _brain_lang = get_narration_lang(_cfg)

    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[: eng().truncations.log_long]}")

    system = get_prompt(
        "brain_parser",
        lang=_brain_lang,
        content_boundaries_block=content_boundaries_block(game),
        moves_block=_build_moves_block(game),
    )

    w = game.world
    _ai_text = eng().ai_text.narrator_defaults

    npc_lines = []
    for n in game.npcs:
        if n.status in ("active", "background"):
            entry = f"  {n.name} (id:{n.id}, {n.disposition})"
            if n.aliases:
                entry += f" aliases:{','.join(n.aliases)}"
            npc_lines.append(entry)
    npc_block = "<npcs>\n" + "\n".join(npc_lines) + "\n</npcs>" if npc_lines else f"<npcs>{_ai_text['no_npcs']}</npcs>"

    tracks_block = _build_tracks_block(game)

    user_msg = f"""<state>
loc:{w.current_location} | ctx:{w.current_scene_context}
time:{w.time_of_day or _ai_text["unknown_time"]}
{build_stats_line(game)}
</state>
{npc_block}
{tracks_block}
<input>{player_message}</input>"""

    try:
        spec = AICallSpec(
            model=model_for_role("brain"),
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=get_brain_output_schema(),
            log_role="brain",
            **sampling_params("brain"),
        )
        response = create_with_retry(provider, spec)

        result = BrainResult.from_dict(json.loads(response.content))
        log(
            f"[Brain] move={result.move}, stat={result.stat}, "
            f"intent={result.player_intent[: eng().truncations.log_short]}"
        )
        return result

    except Exception as e:
        log(f"[Brain] Failed ({type(e).__name__}: {e}), treating as dialog", level="warning")
        return BrainResult(
            type="action",
            move="dialog",
            stat="none",
            dialog_only=True,
            player_intent=player_message,
            approach="error",
        )


def call_revelation_check(
    provider: AIProvider, narration: str, revelation: Revelation, config: EngineConfig | None = None
) -> bool:
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)
    rev_content = revelation.content
    rev_weight = revelation.dramatic_weight

    system = get_prompt("revelation_check_system", lang=lang)

    prompt = (
        f'<revelation weight="{html.escape(rev_weight, quote=True)}">{html.escape(rev_content)}</revelation>\n\n'
        f"<narration>{narration}</narration>\n\n"
        f"{get_prompt('revelation_check_question', role='revelation_check')}"
    )

    try:
        spec = AICallSpec(
            model=model_for_role("revelation_check"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_revelation_check_schema(),
            log_role="revelation_check",
            **sampling_params("revelation_check"),
        )
        response = create_with_retry(provider, spec)
        result = json.loads(response.content)
        confirmed = result["revelation_confirmed"]
        reasoning = result.get("reasoning", "")
        log(f"[Revelation] Check for '{revelation.id}': confirmed={confirmed} — {reasoning}")
        return confirmed
    except Exception as e:
        log(
            f"[Revelation] Check failed ({type(e).__name__}: {e}), defaulting to confirmed=True to avoid pending loop",
            level="warning",
        )
        return True
