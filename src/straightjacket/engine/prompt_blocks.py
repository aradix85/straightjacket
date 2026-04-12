#!/usr/bin/env python3
"""Prompt block builders: XML context blocks for narrator and other AI prompts.

Each function builds one self-contained XML block. The narrator system prompt
assembler (get_narrator_system) composes them. All blocks return empty string
when not applicable — callers never need to check."""

from ..i18n import E
from .config_loader import narration_language
from .engine_loader import eng
from .models import EngineConfig, GameState
from .prompt_loader import get_prompt
from .story_state import get_current_act, get_pending_revelations
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def get_narration_lang(config: EngineConfig) -> str:
    """Get the narration language (English name, e.g. 'English', 'German')."""
    return config.narration_lang or narration_language()


def content_boundaries_block(game: GameState | None = None, creation_data: dict | None = None) -> str:
    """Return content boundaries prompt block if any lines/wishes are set."""
    lines = ""
    wishes = ""
    if game:
        lines = game.preferences.content_lines or ""
        wishes = game.preferences.player_wishes or ""
    if not lines and not wishes and creation_data:
        lines = creation_data.get("content_lines", "")
        wishes = creation_data.get("wishes", "")
    if not lines and not wishes:
        return ""
    parts = ["<content_boundaries>"]
    if lines:
        parts.append(get_prompt("block_content_boundaries_lines", content_lines=_xe(lines)))
    if wishes:
        parts.append(get_prompt("block_content_boundaries_wishes", wishes=_xe(wishes)))
    parts.append("</content_boundaries>")
    return "\n".join(parts)


def backstory_block(game: GameState | None = None) -> str:
    """Return backstory prompt block if player provided backstory text."""
    if not game:
        return ""
    backstory = game.backstory or ""
    if not backstory.strip():
        return ""
    return get_prompt("block_backstory", backstory_text=_xe(backstory))


def vocabulary_block(game: GameState | None = None) -> str:
    """Build vocabulary control block from the active setting package."""
    if not game:
        return ""
    from .datasworn.settings import active_package

    pkg = active_package(game)
    if not pkg:
        return ""
    vocab = pkg.vocabulary
    palette = pkg.raw_config.get("vocabulary", {}).get("sensory_palette", "")
    if not vocab and not palette:
        return ""
    parts = ["<vocabulary>"]
    if vocab:
        lines = [f"  {term} → {replacement}" for term, replacement in vocab.items()]
        from .prompt_loader import get_prompt as _get_prompt

        parts.append(_get_prompt("vocabulary_instruction") + "\n" + "\n".join(lines))
    if palette:
        parts.append(f"<sensory_palette>{palette.strip()}</sensory_palette>")
    parts.append("</vocabulary>")
    return "\n".join(parts)


def truths_block(game: GameState | None = None) -> str:
    """Build world truths block from player's truth selections at creation."""
    if not game or not game.truths:
        return ""
    lines = [f"  {truth_id}: {summary}" for truth_id, summary in game.truths.items()]
    return (
        "<world_truths>\nEstablished facts about this world. Treat as canon.\n" + "\n".join(lines) + "\n</world_truths>"
    )


def tone_authority_block(game: GameState | None = None) -> str:
    """Build tone authority block from the player's chosen tone.
    Injected before <rules> so it outranks generic style defaults."""
    if not game or not game.setting_tone:
        return ""
    return (
        f'\n<tone_authority tone="{_xa(game.setting_tone)}">'
        f"This is the player's chosen creative register for the entire story. "
        f"It governs sentence rhythm, scene energy, what details get highlighted, "
        f"how NPCs behave, and what makes a moment land. Every scene must feel it. "
        f"Follow <director_guidance> for narrative direction, but never let it "
        f"override or dilute the tone.</tone_authority>"
    )


def narrative_direction_block(game: GameState, roll_result: str = "", is_player_caused: bool = True) -> str:
    """Derive narrative writing instructions from current game state.
    All thresholds and mappings read from engine.yaml narrative_direction."""
    nd = eng().get_raw("narrative_direction", {})
    parts = []

    h, sp = game.resources.health, game.resources.spirit
    low_resource = min(h, sp)
    intensity = nd.get("intensity", {})
    if game.game_over or game.crisis_mode or low_resource < intensity.get("critical_below", 1):
        parts.append("intensity:critical")
    elif low_resource < intensity.get("high_below", 3):
        parts.append("intensity:high")
    elif low_resource < intensity.get("moderate_below", 4):
        parts.append("intensity:moderate")
    else:
        parts.append("intensity:low")

    rm = nd.get("result_map", {})
    entry = rm.get(roll_result, rm.get("_default"))

    if entry and isinstance(entry, dict):
        parts.append(f"tempo:{entry.get('tempo', 'moderate')}")
        parts.append(f"perspective:{entry.get('perspective', 'action_detail')}")

    parts.append("player:caused_this" if is_player_caused else "player:witnessing")

    from .mechanics import get_pacing_hint

    hint = get_pacing_hint(game)
    if hint == "breather":
        parts.append("position:aftermath")
    elif hint == "action":
        parts.append("position:building")
    else:
        parts.append("position:steady")

    return f"<narrative_direction>{' '.join(parts)}</narrative_direction>"


def status_context_block(game: GameState | None = None) -> str:
    """Narrative status context mapping resource values to physical/mental states."""
    if not game:
        return ""
    h, sp, su = game.resources.health, game.resources.spirit, game.resources.supply

    health_desc = (
        "uninjured"
        if h >= 5
        else "bruised — minor aches, nothing that slows them down"
        if h == 4
        else "injured — clearly hurting, moving with effort"
        if h == 3
        else "seriously wounded — every motion costs something"
        if h == 2
        else "critically injured — barely holding together, on the edge of collapse"
        if h == 1
        else "at the physical limit — collapse is imminent (see <flags>)"
    )
    spirit_desc = (
        "steady and composed"
        if sp >= 5
        else "mildly unsettled — small cracks under the surface"
        if sp == 4
        else "shaken — stress is showing, focus is harder to maintain"
        if sp == 3
        else "deeply troubled — holding on by a thread, doubt and fear are present"
        if sp == 2
        else "near breaking — barely functioning, the weight is crushing"
        if sp == 1
        else "at the mental limit — breakdown is imminent (see <flags>)"
    )
    supply_desc = (
        "well-equipped"
        if su >= 5
        else "adequate — supplies are fine for now"
        if su == 4
        else "running low — rationing has begun, choices are being made"
        if su == 3
        else "critically short — scarcity is a real pressure"
        if su == 2
        else "nearly nothing — desperation is setting in"
        if su == 1
        else "out of resources entirely (see <flags>)"
    )

    return (
        "<character_state>\n"
        "Reflect these states through sensory detail, body language, and atmosphere. "
        "NEVER state numbers or game terms. Maintain consistency across scenes — "
        "do NOT describe the character as healthy if they are injured, or calm if they are shaken.\n"
        f"Physical: {health_desc}\n"
        f"Mental/Emotional: {spirit_desc}\n"
        f"Resources/Equipment: {supply_desc}\n"
        "</character_state>"
    )


def story_context_block(game: GameState) -> str:
    """Build compact story direction block for prompts."""
    bp = game.narrative.story_blueprint
    if not bp or not bp.acts:
        return ""
    act = get_current_act(game)

    pending = get_pending_revelations(game)
    rev_block = ""
    if pending:
        rev = pending[0]
        rev_block = f'\n<revelation_ready weight="{rev.dramatic_weight}">{rev.content}</revelation_ready>'

    ending_hint = ""
    if bp.story_complete and game.campaign.epilogue_dismissed:
        ending_hint = (
            f"\n<story_ending>The planned arc is complete and the player chose to continue "
            f"beyond it (scene {game.narrative.scene_count}). Do NOT push toward a conclusion. "
            f"Follow the player's organic lead — new threads, consequences, and character "
            f"moments are all valid. Treat this as open-ended play.</story_ending>"
        )
    elif bp.story_complete:
        endings = bp.possible_endings
        ending_hint = f"\n<story_ending>Story has EXCEEDED its planned arc (scene {game.narrative.scene_count}). Guide toward a satisfying conclusion in the next 1-2 scenes. Possible endings: {', '.join(e.type for e in endings)}. Let player actions determine which ending, but actively weave toward closure.</story_ending>"
    elif act.approaching_end:
        endings = bp.possible_endings
        ending_hint = f"\n<story_ending>Story nearing conclusion. Possible endings: {', '.join(e.type for e in endings)}. Let player actions determine which.</story_ending>"

    structure = bp.structure_type
    thematic = bp.thematic_thread
    thematic_attr = f' thematic_thread="{_xa(thematic)}"' if thematic else ""
    return (
        f'<story_arc structure="{_xa(structure)}" act="{act.act_number}/{act.total_acts}"'
        f' phase="{_xa(act.phase)}" progress="{act.progress}" mood="{_xa(act.mood)}"'
        f' conflict="{_xa(bp.central_conflict)}" act_goal="{_xa(act.goal)}"'
        f"{thematic_attr}/>"
        f"{rev_block}"
        f"{ending_hint}\n"
    )


def recent_events_block(game: GameState) -> str:
    """Build compact factual timeline from session_log for narrator consistency."""
    if not game.narrative.session_log or len(game.narrative.session_log) < 2:
        return ""
    entries = game.narrative.session_log[-8:-1] if len(game.narrative.session_log) > 1 else []
    if not entries:
        return ""
    lines = []
    for s in entries:
        summary = s.rich_summary or s.summary
        if summary:
            lines.append(f"Scene {s.scene}: {_xe(summary)}")
    if not lines:
        return ""
    return "\n<recent_events>\n" + "\n".join(lines) + "\n</recent_events>"


def campaign_history_block(game: GameState) -> str:
    """Build campaign history context for prompts."""
    cam = game.campaign
    if not cam.campaign_history:
        return ""
    parts = [f'<campaign_history chapters="{len(cam.campaign_history)}">']
    for ch in cam.campaign_history[-3:]:
        parts.append(f'  <chapter n="{ch.chapter}" title="{_xa(ch.title)}">{_xe(ch.summary)}</chapter>')
    parts.append("</campaign_history>")
    return "\n".join(parts)


def get_narrator_system(config: EngineConfig, game: GameState | None = None) -> str:
    """Build narrator system prompt with configured language."""
    lang = get_narration_lang(config)
    cb = content_boundaries_block(game)
    bs = backstory_block(game)
    sc = status_context_block(game)
    vc = vocabulary_block(game)
    tc = truths_block(game)
    ta = tone_authority_block(game)
    return (
        get_prompt(
            "narrator_system",
            lang=lang,
            content_boundaries_block=cb,
            backstory_block=bs,
            status_context_block=sc,
            tone_authority_block=ta,
            dash=E["dash"],
        )
        + ("\n" + vc if vc else "")
        + ("\n" + tc if tc else "")
    )
