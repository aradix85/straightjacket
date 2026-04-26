from __future__ import annotations

import yaml
from pathlib import Path

from straightjacket.engine.ai.provider_base import AIProvider, post_process_response
from straightjacket.engine.models import GameState
from straightjacket.engine.story_state import get_current_act

_HERE = Path(__file__).resolve().parent.parent
_PROMPTS_PATH = _HERE / "elvira_prompts.yaml"
_CONFIG_PATH = _HERE / "elvira_config.yaml"

_prompts: dict[str, str] | None = None
_bot_model: str | None = None
_bot_temperature: float | None = None
_bot_config_loaded: bool = False


def _load_prompts() -> dict[str, str]:
    global _prompts
    if _prompts is None:
        if not _PROMPTS_PATH.exists():
            raise FileNotFoundError(f"Elvira prompts not found: {_PROMPTS_PATH}")
        with open(_PROMPTS_PATH, encoding="utf-8") as f:
            _prompts = yaml.safe_load(f)
    return _prompts


def _load_bot_config() -> None:
    global _bot_model, _bot_temperature, _bot_config_loaded
    if _bot_config_loaded:
        return
    _bot_config_loaded = True
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            ecfg = yaml.safe_load(f) or {}
        ai_cfg = ecfg.get("ai", {})
        _bot_model = ai_cfg.get("bot_model", "") or None
        temp = ai_cfg.get("temperature")
        if temp is not None:
            _bot_temperature = float(temp)
    if not _bot_model:
        from straightjacket.engine.config_loader import model_for_role

        _bot_model = model_for_role("brain")


def get_persona(style: str) -> str:
    prompts = _load_prompts()
    return prompts.get(f"style_{style}", prompts.get("style_balanced", ""))


def ask_bot(provider: AIProvider, system: str, user: str, max_tokens: int = 300, model: str = "") -> str:
    _load_bot_config()
    from straightjacket.engine.config_loader import model_for_role

    _model = model or _bot_model or model_for_role("brain")
    response = provider.create_message(
        model=_model,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=_bot_temperature,
    )
    response = post_process_response(response)
    return response.content.strip()


def build_turn_context(game: GameState, narration: str, turn: int, prev_action: str = "") -> str:
    res = game.resources
    world = game.world

    active_npcs = "\n".join(f"  - {n.name} [{n.disposition}]" for n in game.npcs if n.status == "active") or "  (none)"

    active_clocks = (
        "\n".join(f"  - {c.name}: {c.filled}/{c.segments}" for c in world.clocks if not c.fired) or "  (none)"
    )

    active_tracks = (
        "\n".join(
            f"  - {t.name} ({t.track_type}, {t.rank}): {t.filled_boxes}/10"
            for t in game.progress_tracks
            if t.status == "active"
        )
        or "  (none)"
    )

    story_block = ""
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        sr = act.scene_range
        r_str = f"Scene {sr[0]}-{sr[1]}" if len(sr) == 2 else "?"
        story_block = f"\nSTORY PHASE : Act {act.act_number}/{act.total_acts} - {act.title} ({r_str})"
        conflict = bp.central_conflict
        if conflict:
            story_block += f"\nCENTRAL CONFLICT: {conflict[:120]}"

    turn_types = [
        "DIALOG — talk to an NPC, ask a question, no pressure",
        "INVESTIGATE — examine, search, study something in the environment",
        "PHYSICAL RISK — face danger, fight, climb, force something",
        "DIALOG or INVESTIGATE — follow up on what you learned",
        "SOCIAL PRESSURE — compel, threaten, persuade, negotiate",
        "TRAVEL — move to a new location, explore a new area",
        "INVESTIGATE — study what you find in the new location",
        "PHYSICAL RISK — take a dangerous action based on what you know",
        "DIALOG — talk to someone about what happened",
        "ACT ON YOUR VOW — whatever move fits best",
    ]
    turn_idx = (turn - 1) % len(turn_types)
    turn_directive = turn_types[turn_idx]

    prev_block = ""
    if prev_action:
        prev_block = f"\nYour previous action was: {prev_action[:80]}\nDo NOT repeat that type of action."

    return f"""=== MANDATORY ACTION TYPE: {turn_directive} ===
You MUST write a {turn_directive.split(" — ")[0]} action this turn.
Only deviate if you are wounded, under attack, or in immediate danger.
{prev_block}

TURN {turn} - Scene {game.narrative.scene_count}

--- LATEST NARRATION ---
{narration.strip()}
--- END NARRATION ---

CHARACTER : {game.player_name}
Location  : {world.current_location or "(unknown)"}
Time      : {world.time_of_day or "(unknown)"}

RESOURCES : Health {res.health}/5 | Spirit {res.spirit}/5 | Supply {res.supply}/5 | Momentum {res.momentum}/{res.max_momentum}
{story_block}
ACTIVE NPCs:
{active_npcs}
ACTIVE TRACKS (vows, connections, combat):
{active_tracks}
ACTIVE CLOCKS:
{active_clocks}

What does {game.player_name} do next? Write only the player action."""


def decide_burn_momentum(provider: AIProvider, game: GameState, burn_info: dict, style: str) -> bool:
    if style == "aggressor":
        return True
    prompts = _load_prompts()
    prompt = prompts["burn_decision"].format(
        current_result=burn_info["roll"].result,
        new_result=burn_info["new_result"],
        momentum=game.resources.momentum,
    )
    answer = ask_bot(provider, "You are a solo RPG player making a tactical decision.", prompt, max_tokens=10)
    return answer.lower().startswith("y")
