#!/usr/bin/env python3
"""State serializers: game state → client JSON.

Every function builds a JSON-serializable dict. Label resolution for
roll data and NPC dispositions happens here. The HTML client hardcodes
its own display labels for status text.
"""

import re

from ..engine.models import GameState, RollResult
from ..engine.story_state import get_current_act
from ..engine.datasworn.loader import extract_title
from ..engine.datasworn.settings import list_packages, load_package
from ..engine.logging_util import log
from ..i18n import (
    get_disposition_labels,
    get_effect_labels,
    get_move_labels,
    get_position_labels,
    get_result_labels,
    get_stat_labels,
    get_story_phase_labels,
    get_time_labels,
    translate_consequence,
)


def build_state(game: GameState) -> dict:
    """Full game state dict for the client sidebar."""
    sl = get_stat_labels()
    dl = get_disposition_labels()
    tl = get_time_labels()
    pl = get_story_phase_labels()

    npcs = []
    for n in game.npcs:
        if n.status not in ("active", "background", "deceased"):
            continue
        npcs.append({
            "name": n.name,
            "status": n.status,
            "disposition": n.disposition,
            "disposition_label": dl.get(n.disposition, n.disposition),
            "bond": n.bond,
            "bond_max": n.bond_max,
            "aliases": list(n.aliases),
        })

    clocks = []
    for c in game.world.clocks:
        clocks.append({
            "name": c.name,
            "clock_type": c.clock_type,
            "filled": c.filled,
            "segments": c.segments,
            "fired": c.fired,
        })

    story_arc = None
    bp = game.narrative.story_blueprint
    if bp and bp.acts:
        act = get_current_act(game)
        story_arc = {
            "act_number": act.act_number,
            "total_acts": act.total_acts,
            "phase": act.phase,
            "phase_label": pl.get(act.phase, act.phase),
            "title": act.title,
            "progress": act.progress,
            "story_complete": bp.story_complete,
        }

    time_label = tl.get(game.world.time_of_day, "") if game.world.time_of_day else ""

    return {
        "player_name": game.player_name,
        "character_concept": game.character_concept,
        "location": game.world.current_location,
        "time_of_day": game.world.time_of_day,
        "time_label": time_label,
        "scene": game.narrative.scene_count,
        "chapter": game.campaign.chapter_number,
        "stats": {
            "edge": {"value": game.edge, "label": sl.get("edge", "Edge")},
            "heart": {"value": game.heart, "label": sl.get("heart", "Heart")},
            "iron": {"value": game.iron, "label": sl.get("iron", "Iron")},
            "shadow": {"value": game.shadow, "label": sl.get("shadow", "Shadow")},
            "wits": {"value": game.wits, "label": sl.get("wits", "Wits")},
        },
        "health": game.resources.health,
        "spirit": game.resources.spirit,
        "supply": game.resources.supply,
        "momentum": game.resources.momentum,
        "max_momentum": game.resources.max_momentum,
        "chaos": game.world.chaos_factor,
        "crisis_mode": game.crisis_mode,
        "game_over": game.game_over,
        "npcs": npcs,
        "clocks": clocks,
        "story_arc": story_arc,
        "epilogue_shown": game.campaign.epilogue_shown,
        "epilogue_dismissed": game.campaign.epilogue_dismissed,
    }


def build_roll_data(roll: RollResult, consequences: list | None = None,
                    clock_events: list | None = None,
                    brain=None, chaos_interrupt: str | None = None) -> dict:
    """Roll display dict with pre-resolved i18n labels."""
    rl = get_result_labels()
    result_label, severity = rl.get(roll.result, ("?", "info"))
    ml = get_move_labels()
    sl = get_stat_labels()
    pl = get_position_labels()
    el = get_effect_labels()

    if brain is None:
        pos, eff = "risky", "standard"
    elif isinstance(brain, dict):
        pos = brain.get("position", "risky")
        eff = brain.get("effect", "standard")
    else:
        pos = getattr(brain, "position", "risky")
        eff = getattr(brain, "effect", "standard")

    cons_translated = [translate_consequence(c) for c in (consequences or [])]
    clock_data = []
    for ce in (clock_events or []):
        if hasattr(ce, "clock"):
            clock_data.append({"clock": ce.clock, "trigger": ce.trigger})
        elif isinstance(ce, dict):
            clock_data.append({"clock": ce.get("clock", ""), "trigger": ce.get("trigger", "")})

    return {
        "move": roll.move,
        "move_label": ml.get(roll.move, roll.move),
        "stat_name": roll.stat_name,
        "stat_label": sl.get(roll.stat_name, roll.stat_name),
        "stat_value": roll.stat_value,
        "d1": roll.d1, "d2": roll.d2, "c1": roll.c1, "c2": roll.c2,
        "action_score": roll.action_score,
        "result": roll.result,
        "result_label": result_label,
        "severity": severity,
        "match": getattr(roll, "match", roll.c1 == roll.c2),
        "consequences": cons_translated,
        "clock_events": clock_data,
        "position": pos,
        "position_label": pl.get(pos, pos),
        "effect": eff,
        "effect_label": el.get(eff, eff),
        "chaos_interrupt": chaos_interrupt or "",
    }


def build_creation_options() -> dict:
    """All character creation data for the client form."""
    settings = []
    for pkg_id in list_packages():
        if pkg_id == "delve":
            continue
        try:
            pkg = load_package(pkg_id)
            paths = []
            for asset in pkg.data.paths():
                asset_id = asset.get("_id", "").rsplit("/", 1)[-1]
                paths.append({
                    "id": asset_id,
                    "title": extract_title(asset, asset_id),
                })
            settings.append({
                "id": pkg_id,
                "title": pkg.title,
                "description": pkg.description,
                "paths": paths,
            })
        except Exception as e:
            log(f"[Web] Failed to load package {pkg_id}: {e}", level="warning")
    return {"settings": settings}


def highlight_dialog(text: str) -> str:
    """Wrap quoted dialog in <span class="dialog"> for CSS styling."""
    def _wrap(open_q: str, content: str, close_q: str) -> str:
        inner = content.strip()
        if not inner:
            return open_q + content + close_q
        return f'{open_q}<span class="dialog">{inner}</span>{close_q}'

    # DE: „..."
    text = re.sub(
        r'(\u201e)([^\u201e\u201c\u201d"\n]{1,600}?)([\u201c\u201d"])',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # EN curly: "..."
    text = re.sub(
        r'(\u201c)([^\u201c\u201d\n]{1,600}?)(\u201d)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # Guillemets
    text = re.sub(
        r'(\u00bb)([^\u00ab\u00bb\n]{1,600}?)(\u00ab)'
        r'|(\u00ab)([^\u00ab\u00bb\n]{1,600}?)(\u00bb)',
        lambda m: (_wrap(m.group(1), m.group(2), m.group(3)) if m.group(1)
                   else _wrap(m.group(4), m.group(5), m.group(6))), text)
    # Straight ASCII
    text = re.sub(
        r'(?<!<span class="dialog">)"([^"\n]{1,600}?)"',
        lambda m: _wrap('"', m.group(1), '"'), text)
    # EN single curly
    text = re.sub(
        r'(\u2018)([^\u2018\u2019\n]{1,600}?)(\u2019)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # French single guillemets
    text = re.sub(
        r'(\u2039)([^\u2039\u203a\n]{1,600}?)(\u203a)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    return text
