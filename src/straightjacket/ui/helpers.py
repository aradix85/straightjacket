#!/usr/bin/env python3
"""Shared UI helpers: session access, config builders, scroll."""

import contextlib
import re

from nicegui import app, ui

from ..engine import (
    EngineConfig,
    GameState,
    RollResult,
    load_global_config,
    load_user_config,
    narration_language,
    user_default,
)
from ..i18n import (
    get_move_labels,
    get_result_labels,
    get_stat_labels,
)

# Module-level state set by app.py after server config is loaded
SERVER_API_KEY: str = ""
SCROLL_DELAY_MS: int = 500

def configure(*, server_api_key: str = "", scroll_delay_ms: int = 500):
    """Called once from app.py to inject server-level config into UI helpers."""
    global SERVER_API_KEY, SCROLL_DELAY_MS
    SERVER_API_KEY = server_api_key
    SCROLL_DELAY_MS = scroll_delay_ms

# Session helpers (per-tab via app.storage.tab)

def S() -> dict:
    """Shortcut to per-tab storage."""
    return app.storage.tab

def init_session() -> None:
    """Initialize session state for a new tab."""
    s = S()
    s.setdefault("authenticated", False)
    s.setdefault("current_user", "")
    s.setdefault("api_key", "")
    s.setdefault("messages", [])
    s.setdefault("game", None)
    s.setdefault("creation", None)
    s.setdefault("pending_burn", None)
    s.setdefault("active_save", "autosave")
    s.setdefault("global_config_loaded", False)
    s.setdefault("processing", False)
    s.setdefault("_turn_gen", 0)
    if not s["global_config_loaded"]:
        if SERVER_API_KEY:
            s["api_key"] = SERVER_API_KEY
        else:
            gcfg = load_global_config()
            s["api_key"] = gcfg.get("api_key", "")
        s["global_config_loaded"] = True

def get_engine_config() -> EngineConfig:
    return EngineConfig(
        narration_lang=narration_language(),
    )

def load_user_settings(username: str) -> None:
    s = S()
    cfg = load_user_config(username)
    raw_dice = cfg.get("dice_display", user_default("dice_display"))
    if isinstance(raw_dice, str):
        raw_dice = dice_string_to_index(raw_dice)
    s["dice_display"] = raw_dice
    s["sr_chat"] = cfg.get("sr_chat", user_default("sr_chat"))
    s["narrator_font"] = cfg.get("narrator_font", "serif")

def dice_string_to_index(val: str) -> int:
    """Migrate old localized dice_display strings to language-neutral index."""
    lower = val.lower()
    if "detail" in lower or "detailliert" in lower:
        return 2
    elif "einfach" in lower or "simple" in lower:
        return 1
    return 0

def build_roll_data(roll: RollResult, consequences=None, clock_events=None,
                    brain=None, chaos_interrupt=None) -> dict:
    rl = get_result_labels()
    result_label, _ = rl.get(roll.result, ("?", "info"))
    ml = get_move_labels()
    sl = get_stat_labels()
    # brain can be BrainResult (attribute access) or dict (from serialized data)
    if brain is None:
        pos, eff = "risky", "standard"
    elif isinstance(brain, dict):
        pos = brain.get("position", "risky")
        eff = brain.get("effect", "standard")
    else:
        pos = getattr(brain, "position", "risky")
        eff = getattr(brain, "effect", "standard")
    return {
        "move": roll.move, "move_label": ml.get(roll.move, roll.move),
        "stat_name": roll.stat_name, "stat_label": sl.get(roll.stat_name, roll.stat_name),
        "stat_value": roll.stat_value,
        "d1": roll.d1, "d2": roll.d2, "c1": roll.c1, "c2": roll.c2,
        "action_score": roll.action_score,
        "result": roll.result, "result_label": result_label,
        "match": getattr(roll, "match", roll.c1 == roll.c2),
        "consequences": consequences or [], "clock_events": clock_events or [],
        "position": pos,
        "effect": eff,
        "chaos_interrupt": chaos_interrupt or "",
    }

def clean_narration(text: str) -> str:
    """Strip any leaked metadata from narration before display."""
    text = re.sub(r'<(?:game_data|new_npcs|memory_updates|scene_context|npc_rename)>[\s\S]*$', '', text)
    text = re.sub(r'```\s*(?:\w+)\s*(?:\{[\s\S]*)?$', '', text)
    text = re.sub(r'```\w*\s*$', '', text)
    text = re.sub(r'\*{0,2}\[(?:[^\]]*\|){2,}[^\]]*\]\*{0,2}\s*$', '', text)
    return text.strip()

# Dialog highlighting (Design mode)

def highlight_dialog(text: str) -> str:
    """Wrap quoted dialog in ***bold-italic*** markdown for Design mode.

    Quote characters are placed OUTSIDE the *** delimiters so CommonMark
    left/right-flanking rules are satisfied for all Unicode quote styles.
    CSS margin-left/padding-right on em strong visually encompasses both
    the opening and closing quote characters."""
    def _wrap(open_q: str, content: str, close_q: str) -> str:
        inner = content.strip()
        if not inner:
            return open_q + content + close_q
        return f"{open_q}***{inner}***{close_q}"

    # DE standard: „..." — U+201E open, U+201D/U+201C/ASCII close
    text = re.sub(
        r'(\u201e)([^\u201e\u201c\u201d"\n]{1,600}?)([\u201c\u201d"])',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # EN curly: "..."
    text = re.sub(
        r'(\u201c)([^\u201c\u201d\n]{1,600}?)(\u201d)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # Guillemets — both directions in a single pass to prevent cross-matching
    text = re.sub(
        r'(\u00bb)([^\u00ab\u00bb\n]{1,600}?)(\u00ab)'
        r'|(\u00ab)([^\u00ab\u00bb\n]{1,600}?)(\u00bb)',
        lambda m: (_wrap(m.group(1), m.group(2), m.group(3)) if m.group(1)
                   else _wrap(m.group(4), m.group(5), m.group(6))), text)
    # Straight ASCII double quotes — lookbehind prevents re-matching DE trailing "
    text = re.sub(
        r'(?<!\*\*\*)"([^"\n]{1,600}?)"',
        lambda m: _wrap('"', m.group(1), '"'), text)
    # EN single curly: '...' — UK style, nested inside double
    text = re.sub(
        r'(\u2018)([^\u2018\u2019\n]{1,600}?)(\u2019)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    # French single guillemets: ‹...› — nested inside «»
    text = re.sub(
        r'(\u2039)([^\u2039\u203a\n]{1,600}?)(\u203a)',
        lambda m: _wrap(m.group(1), m.group(2), m.group(3)), text)
    return text


_DISPOSITION_CSS = {
    "friendly": "et-npc-warm",
    "loyal": "et-npc-warm",
    "hostile": "et-npc-hostile",
    "aggressive": "et-npc-hostile",
    "distrustful": "et-npc-wary",
    "wary": "et-npc-wary",
    "fearful": "et-npc-wary",
}

def build_entity_data(game: GameState) -> dict:
    """Build entity highlight payload for JS _etHighlight().

    NPC names colored by disposition. Neutral NPCs get no coloring (blend
    with text). Player name in accent. Sorted longest-first to avoid
    partial matches (e.g. 'Anna' inside 'Annabelle')."""
    entities: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(name: str, cls: str) -> None:
        if name and name not in seen and len(name) >= 3:
            entities.append({"name": name, "cls": cls})
            seen.add(name)

    # Player name — full name + individual parts ≥ 4 chars
    if game.player_name:
        _add(game.player_name, "et-player")
        for part in game.player_name.split():
            if len(part) >= 4:
                _add(part, "et-player")

    # NPC names — colored by disposition, neutral skipped
    for npc in game.npcs:
        if npc.status not in ("active", "background"):
            continue
        if not npc.introduced:
            continue
        css_cls = _DISPOSITION_CSS.get(npc.disposition, "")
        if not css_cls:
            continue
        _add(npc.name, css_cls)
        for part in npc.name.split():
            if len(part) >= 4:
                _add(part, css_cls)
        for alias in npc.aliases:
            if len(alias) >= 4:
                _add(alias, css_cls)

    entities.sort(key=lambda e: len(e["name"]), reverse=True)
    return {"entities": entities}

# Scroll helpers

async def scroll_chat_bottom(delay_ms: int = 0) -> None:
    """Scroll to bottom of page."""
    with contextlib.suppress(TimeoutError):
        await ui.run_javascript(f'''
            setTimeout(() => {{
                document.documentElement.scrollTo({{top: document.documentElement.scrollHeight}});
            }}, {delay_ms or 10});
        ''', timeout=3.0)

async def scroll_to_element(element_id: str) -> None:
    """Scroll smoothly so element is near top of viewport."""
    with contextlib.suppress(TimeoutError):
        await ui.run_javascript(f'''
            setTimeout(() => {{
                const el = document.getElementById("{element_id}");
                if (el) el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }}, {SCROLL_DELAY_MS});
        ''', timeout=3.0)
