"""Bot player AI helpers: action generation and tactical decisions."""

from __future__ import annotations

import yaml
from pathlib import Path

from straightjacket.engine.ai.provider_base import AIProvider, post_process_response
from straightjacket.engine.config_loader import cfg
from straightjacket.engine.models import GameState
from straightjacket.engine.story_state import get_current_act

_HERE = Path(__file__).resolve().parent.parent
_PROMPTS_PATH = _HERE / "elvira_prompts.yaml"

_prompts: dict[str, str] | None = None


def _load_prompts() -> dict[str, str]:
    global _prompts
    if _prompts is None:
        if not _PROMPTS_PATH.exists():
            raise FileNotFoundError(f"Elvira prompts not found: {_PROMPTS_PATH}")
        with open(_PROMPTS_PATH, encoding="utf-8") as f:
            _prompts = yaml.safe_load(f)
    return _prompts


def get_persona(style: str) -> str:
    """Get the system prompt for a play style."""
    prompts = _load_prompts()
    return prompts.get(f"style_{style}", prompts.get("style_balanced", ""))


def ask_bot(provider: AIProvider, system: str, user: str,
            max_tokens: int = 300, model: str = "") -> str:
    """Single-shot call to the bot player model."""
    _model = model or cfg().ai.brain_model
    response = provider.create_message(
        model=_model,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
    )
    response = post_process_response(response)
    return response.content.strip()


def build_turn_context(game: GameState, narration: str, turn: int) -> str:
    """Build what the bot-Claude sees each turn. Uses engine's get_current_act()."""
    res = game.resources
    world = game.world

    active_npcs = "\n".join(
        f"  - {n.name} [{n.disposition}]"
        for n in game.npcs if n.status == "active"
    ) or "  (none)"

    active_clocks = "\n".join(
        f"  - {c.name}: {c.filled}/{c.segments} ticks"
        for c in world.clocks if not c.fired
    ) or "  (none)"

    story_block = ""
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        sr = act.scene_range
        r_str = f"Scene {sr[0]}-{sr[1]}" if len(sr) == 2 else "?"
        story_block = (
            f"\nSTORY PHASE : Act {act.act_number}/{act.total_acts}"
            f" - {act.title} ({r_str})"
        )
        conflict = bp.central_conflict
        if conflict:
            story_block += f"\nCENTRAL CONFLICT: {conflict[:120]}"

    return f"""TURN {turn} - Scene {game.narrative.scene_count}

--- LATEST NARRATION ---
{narration.strip()}
--- END NARRATION ---

CHARACTER : {game.player_name}
Location  : {world.current_location or "(unknown)"}
Time      : {world.time_of_day or "(unknown)"}

STATS     : Edge {game.edge} | Heart {game.heart} | Iron {game.iron} | Shadow {game.shadow} | Wits {game.wits}
RESOURCES : Health {res.health}/5 | Spirit {res.spirit}/5 | Supply {res.supply}/5 | Momentum {res.momentum}/{res.max_momentum}
CHAOS     : {world.chaos_factor}  |  Chapter {game.campaign.chapter_number}{story_block}

ACTIVE NPCs:
{active_npcs}
ACTIVE CLOCKS:
{active_clocks}

NOTE: Vary your approach — don't repeat the same action type multiple turns in a row.
What does {game.player_name} do next? Write only the player action."""


def decide_burn_momentum(provider: AIProvider, game: GameState,
                         burn_info: dict, style: str) -> bool:
    """Decide whether to burn momentum. Aggressor always burns."""
    if style == "aggressor":
        return True
    prompts = _load_prompts()
    prompt = prompts["burn_decision"].format(
        current_result=burn_info["roll"].result,
        new_result=burn_info["new_result"],
        momentum=game.resources.momentum,
    )
    answer = ask_bot(provider, "You are a solo RPG player making a tactical decision.",
                     prompt, max_tokens=10)
    return answer.lower().startswith("y")
