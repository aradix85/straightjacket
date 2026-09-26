from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from straightjacket.engine.ai.api_client import provider_named
from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, post_process_response
from straightjacket.engine.models import GameState
from straightjacket.engine.story_state import get_current_act

_HERE = Path(__file__).resolve().parent.parent
_PROMPTS_PATH = _HERE / "elvira_prompts.yaml"

ELVIRA_ROLE = "elvira"

_prompts: dict[str, Any] | None = None
_bot: dict[str, Any] = {}


def _load_prompts() -> dict[str, Any]:
    global _prompts
    if _prompts is None:
        if not _PROMPTS_PATH.exists():
            raise FileNotFoundError(f"Elvira prompts not found: {_PROMPTS_PATH}")
        with Path(_PROMPTS_PATH).open(encoding="utf-8") as f:
            _prompts = yaml.safe_load(f)
    return _prompts


def _p(key: str, **kwargs: Any) -> str:
    prompts = _load_prompts()
    template = prompts[key]
    if not isinstance(template, str):
        raise TypeError(f"Elvira prompt '{key}' is not a string (got {type(template).__name__})")
    return template.format(**kwargs) if kwargs else template


def configure_bot(ai_cfg: dict[str, Any]) -> None:
    _bot.clear()
    _bot.update(
        provider=provider_named(ai_cfg["provider"]),
        label=f"{ai_cfg['provider']}/{ai_cfg['model']}",
        model=ai_cfg["model"],
        temperature=float(ai_cfg["temperature"]),
        extra_body=dict(ai_cfg["extra_body"]),
    )


def bot_label() -> str:
    return str(_bot["label"])


def bot_model() -> str:
    return str(_bot["model"])


def bot_provider() -> AIProvider:
    provider: AIProvider = _bot["provider"]
    return provider


def available_styles() -> list[str]:
    return sorted(k.removeprefix("style_") for k in _load_prompts() if k.startswith("style_"))


def get_persona(style: str) -> str:
    prompts = _load_prompts()
    key = f"style_{style}"
    if key not in prompts:
        valid = sorted(k.removeprefix("style_") for k in prompts if k.startswith("style_"))
        raise KeyError(f"Unknown Elvira style '{style}'. Valid styles: {', '.join(valid)}")
    return prompts[key]


def ask_bot(system: str, user: str, max_tokens: int = 300) -> str:
    spec = AICallSpec(
        model=bot_model(),
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=_bot["temperature"],
        extra_body=dict(_bot["extra_body"]),
        log_role=ELVIRA_ROLE,
    )
    response = post_process_response(bot_provider().create_message(spec))
    return response.content.strip()


def _resolve_turn_directive(turn: int, directive_key: str | None = None) -> tuple[str, str]:
    prompts = _load_prompts()
    rotation = prompts["bot_turn_rotation"]
    if not isinstance(rotation, list) or not rotation:
        raise ValueError("Elvira prompt 'bot_turn_rotation' must be a non-empty list")
    directive_key = directive_key or rotation[(turn - 1) % len(rotation)]
    full = _p(directive_key)
    short = full.split(" — ")[0]
    return full, short


def build_turn_context(
    game: GameState, narration: str, turn: int, prev_action: str = "", directive_key: str | None = None
) -> str:
    res = game.resources
    world = game.world
    unknown = _p("bot_unknown_label")
    none_label = _p("bot_active_none_label")

    npc_lines = [_p("bot_npc_line", name=n.name, disposition=n.disposition) for n in game.npcs if n.status == "active"]
    active_npcs = "\n".join(npc_lines) if npc_lines else none_label

    clock_lines = [
        _p("bot_clock_line", name=c.name, filled=c.filled, segments=c.segments) for c in world.clocks if not c.fired
    ]
    active_clocks = "\n".join(clock_lines) if clock_lines else none_label

    track_lines = [
        _p(
            "bot_track_line",
            name=t.name,
            track_type=t.track_type,
            rank=t.rank,
            filled_boxes=t.filled_boxes,
        )
        for t in game.progress_tracks
        if t.status == "active"
    ]
    active_tracks = "\n".join(track_lines) if track_lines else none_label

    story_block = ""
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        sr = act.scene_range
        scene_range = _p("bot_scene_range", start=sr[0], end=sr[1]) if len(sr) == 2 else _p("bot_scene_range_unknown")
        story_block = _p(
            "bot_story_block",
            act_number=act.act_number,
            total_acts=act.total_acts,
            title=act.title,
            scene_range=scene_range,
        )
        conflict = bp.central_conflict
        if conflict:
            story_block += _p("bot_story_conflict", conflict=conflict[:120])

    turn_directive_full, turn_directive_short = _resolve_turn_directive(turn, directive_key)
    mandatory_action_block = _p(
        "bot_mandatory_action_block",
        turn_directive=turn_directive_full,
        turn_directive_short=turn_directive_short,
    )
    prev_action_block = "\n" + _p("bot_prev_action_block", prev_action=prev_action[:80]) if prev_action else ""

    return _p(
        "bot_turn_context",
        mandatory_action_block=mandatory_action_block,
        prev_action_block=prev_action_block,
        turn=turn,
        scene_count=game.narrative.scene_count,
        narration=narration.strip(),
        player_name=game.player_name,
        location=world.current_location or unknown,
        time_of_day=world.time_of_day or unknown,
        health=res.health,
        spirit=res.spirit,
        supply=res.supply,
        momentum=res.momentum,
        max_momentum=res.max_momentum,
        story_block=story_block,
        active_npcs=active_npcs,
        active_tracks=active_tracks,
        active_clocks=active_clocks,
    )


def decide_burn_momentum(game: GameState, burn_info: dict, style: str) -> bool:
    if style == "aggressor":
        return True
    prompt = _p(
        "burn_decision",
        current_result=burn_info["roll"].result,
        new_result=burn_info["new_result"],
        momentum=game.resources.momentum,
    )
    answer = ask_bot(_p("burn_decision_system"), prompt, max_tokens=10)
    return answer.lower().startswith("y")
