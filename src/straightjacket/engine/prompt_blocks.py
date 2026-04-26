from .config_loader import narration_language
from .datasworn.settings import active_package
from .engine_loader import eng
from .mechanics import get_pacing_hint
from .models import EngineConfig, GameState
from .prompt_loader import get_prompt
from .story_state import get_current_act, get_pending_revelations
from .xml_utils import xa as _xa
from .xml_utils import xe as _xe


def get_narration_lang(config: EngineConfig) -> str:
    return config.narration_lang or narration_language()


def content_boundaries_block(game: GameState | None = None, creation_data: dict | None = None) -> str:
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
    if not game:
        return ""
    backstory = game.backstory or ""
    if not backstory.strip():
        return ""
    return get_prompt("block_backstory", backstory_text=_xe(backstory))


def vocabulary_block(game: GameState | None = None) -> str:
    if not game:
        return ""

    pkg = active_package(game)
    if not pkg:
        return ""
    vocab = pkg.vocabulary
    if vocab.is_empty():
        return ""
    parts = ["<vocabulary>"]
    if vocab.substitutions:
        lines = [f"  {term} → {replacement}" for term, replacement in vocab.substitutions.items()]
        parts.append(get_prompt("vocabulary_instruction") + "\n" + "\n".join(lines))
    if vocab.sensory_palette:
        parts.append(f"<sensory_palette>{vocab.sensory_palette.strip()}</sensory_palette>")
    parts.append("</vocabulary>")
    return "\n".join(parts)


def truths_block(game: GameState | None = None) -> str:
    if not game or not game.truths:
        return ""
    header = get_prompt("block_world_truths_header")
    lines = [f"  {truth_id}: {summary}" for truth_id, summary in game.truths.items()]
    return f"<world_truths>\n{header}\n" + "\n".join(lines) + "\n</world_truths>"


def tone_authority_block(game: GameState | None = None) -> str:
    if not game or not game.setting_tone:
        return ""
    body = get_prompt("block_tone_authority")
    return f'\n<tone_authority tone="{_xa(game.setting_tone)}">{body}</tone_authority>'


def narrative_direction_block(game: GameState, roll_result: str = "", is_player_caused: bool = True) -> str:
    nd = eng().narrative_direction
    parts = []

    h, sp = game.resources.health, game.resources.spirit
    low_resource = min(h, sp)
    intensity = nd.intensity
    if game.game_over or game.crisis_mode or low_resource < intensity.critical_below:
        parts.append("intensity:critical")
    elif low_resource < intensity.high_below:
        parts.append("intensity:high")
    elif low_resource < intensity.moderate_below:
        parts.append("intensity:moderate")
    else:
        parts.append("intensity:low")

    entry = nd.entry_for(roll_result)
    parts.append(f"tempo:{entry.tempo}")
    parts.append(f"perspective:{entry.perspective}")

    parts.append("player:caused_this" if is_player_caused else "player:witnessing")

    hint = get_pacing_hint(game)
    if hint == "breather":
        parts.append("position:aftermath")
    elif hint == "action":
        parts.append("position:building")
    else:
        parts.append("position:steady")

    return f"<narrative_direction>{' '.join(parts)}</narrative_direction>"


def _describe_narrator_resource(value: int, descriptions: dict[int, str]) -> str:
    for threshold in sorted(descriptions.keys(), reverse=True):
        if value >= threshold:
            return descriptions[threshold]
    return descriptions[min(descriptions.keys())]


def status_context_block(game: GameState | None = None) -> str:
    if not game:
        return ""
    descriptions = eng().narrator_status_descriptions
    h, sp, su = game.resources.health, game.resources.spirit, game.resources.supply

    health_desc = _describe_narrator_resource(h, descriptions.health)
    spirit_desc = _describe_narrator_resource(sp, descriptions.spirit)
    supply_desc = _describe_narrator_resource(su, descriptions.supply)

    instruction = get_prompt("block_character_state_instruction")
    physical_label = get_prompt("label_character_state_physical")
    mental_label = get_prompt("label_character_state_mental")
    resources_label = get_prompt("label_character_state_resources")

    return (
        "<character_state>\n"
        f"{instruction}\n"
        f"{physical_label}: {health_desc}\n"
        f"{mental_label}: {spirit_desc}\n"
        f"{resources_label}: {supply_desc}\n"
        "</character_state>"
    )


def story_context_block(game: GameState) -> str:
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
        ending_hint = "\n" + get_prompt("block_story_ending_exceeded_continuing", scene=str(game.narrative.scene_count))
    elif bp.story_complete:
        endings_text = ", ".join(e.type for e in bp.possible_endings)
        ending_hint = "\n" + get_prompt(
            "block_story_ending_exceeded", scene=str(game.narrative.scene_count), endings=endings_text
        )
    elif act.approaching_end:
        endings_text = ", ".join(e.type for e in bp.possible_endings)
        ending_hint = "\n" + get_prompt("block_story_ending_approaching", endings=endings_text)

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
    if not game.narrative.session_log or len(game.narrative.session_log) < 2:
        return ""
    window = eng().prompt_display.recent_events_window
    entries = game.narrative.session_log[-(window + 1) : -1] if len(game.narrative.session_log) > 1 else []
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
    cam = game.campaign
    if not cam.campaign_history:
        return ""
    parts = [f'<campaign_history chapters="{len(cam.campaign_history)}">']
    n = eng().prompt_display.campaign_history_chapters
    for ch in cam.campaign_history[-n:]:
        parts.append(f'  <chapter n="{ch.chapter}" title="{_xa(ch.title)}">{_xe(ch.summary)}</chapter>')
    parts.append("</campaign_history>")
    return "\n".join(parts)


def get_narrator_system(config: EngineConfig, game: GameState | None = None) -> str:
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
            role="narrator",
            lang=lang,
            content_boundaries_block=cb,
            backstory_block=bs,
            status_context_block=sc,
            tone_authority_block=ta,
        )
        + ("\n" + vc if vc else "")
        + ("\n" + tc if tc else "")
    )
