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


def content_boundaries_block(game: GameState) -> str:
    lines = game.preferences.content_lines
    wishes = game.preferences.player_wishes
    if not lines and not wishes:
        return ""
    body_parts: list[str] = []
    if lines:
        body_parts.append(get_prompt("block_content_boundaries_lines", content_lines=_xe(lines)))
    if wishes:
        body_parts.append(get_prompt("block_content_boundaries_wishes", wishes=_xe(wishes)))
    return get_prompt("block_content_boundaries_wrapper", body="\n".join(body_parts))


def backstory_block(game: GameState) -> str:
    backstory = game.backstory
    if not backstory.strip():
        return ""
    return get_prompt("block_backstory", backstory_text=_xe(backstory))


def vocabulary_block(game: GameState) -> str:
    pkg = active_package(game)
    if not pkg:
        return ""
    vocab = pkg.vocabulary
    if vocab.is_empty():
        return ""
    body_parts: list[str] = []
    if vocab.substitutions:
        sub_lines = [
            get_prompt("block_vocabulary_substitution_line", term=term, replacement=replacement)
            for term, replacement in vocab.substitutions.items()
        ]
        body_parts.append(get_prompt("vocabulary_instruction") + "\n" + "\n".join(sub_lines))
    if vocab.sensory_palette:
        body_parts.append(get_prompt("block_vocabulary_sensory_palette", palette=vocab.sensory_palette.strip()))
    return "\n" + get_prompt("block_vocabulary_wrapper", body="\n".join(body_parts))


def truths_block(game: GameState) -> str:
    if not game.truths:
        return ""
    header = get_prompt("block_world_truths_header")
    lines = [
        get_prompt("block_world_truths_line", truth_id=truth_id, summary=summary)
        for truth_id, summary in game.truths.items()
    ]
    return "\n" + get_prompt("block_world_truths_wrapper", header=header, lines="\n".join(lines))


def tone_authority_block(game: GameState) -> str:
    if not game.setting_tone:
        return ""
    body = get_prompt("block_tone_authority")
    return "\n" + get_prompt("block_tone_authority_wrapper", tone=_xa(game.setting_tone), body=body)


def narrative_direction_block(game: GameState, roll_result: str = "", is_player_caused: bool = True) -> str:
    nd = eng().narrative_direction
    parts = []

    h, sp = game.resources.health, game.resources.spirit
    low_resource = min(h, sp)
    intensity = nd.intensity
    if game.game_over or game.crisis_mode or low_resource < intensity.critical_below:
        parts.append(get_prompt("narrative_direction_intensity_critical"))
    elif low_resource < intensity.high_below:
        parts.append(get_prompt("narrative_direction_intensity_high"))
    elif low_resource < intensity.moderate_below:
        parts.append(get_prompt("narrative_direction_intensity_moderate"))
    else:
        parts.append(get_prompt("narrative_direction_intensity_low"))

    entry = nd.entry_for(roll_result)
    parts.append(get_prompt("narrative_direction_tempo_label", tempo=entry.tempo))
    parts.append(get_prompt("narrative_direction_perspective_label", perspective=entry.perspective))

    parts.append(
        get_prompt("narrative_direction_player_caused")
        if is_player_caused
        else get_prompt("narrative_direction_player_witnessing")
    )

    hint = get_pacing_hint(game)
    if hint == "breather":
        parts.append(get_prompt("narrative_direction_position_aftermath"))
    elif hint == "action":
        parts.append(get_prompt("narrative_direction_position_building"))
    else:
        parts.append(get_prompt("narrative_direction_position_steady"))

    return get_prompt("block_narrative_direction_wrapper", tokens=" ".join(parts))


def _describe_narrator_resource(value: int, descriptions: dict[int, str]) -> str:
    for threshold in sorted(descriptions.keys(), reverse=True):
        if value >= threshold:
            return descriptions[threshold]
    return descriptions[min(descriptions.keys())]


def status_context_block(game: GameState) -> str:
    descriptions = eng().narrator_status_descriptions
    h, sp, su = game.resources.health, game.resources.spirit, game.resources.supply

    return get_prompt(
        "block_character_state_wrapper",
        instruction=get_prompt("block_character_state_instruction"),
        physical_label=get_prompt("label_character_state_physical"),
        mental_label=get_prompt("label_character_state_mental"),
        resources_label=get_prompt("label_character_state_resources"),
        health_desc=_describe_narrator_resource(h, descriptions.health),
        spirit_desc=_describe_narrator_resource(sp, descriptions.spirit),
        supply_desc=_describe_narrator_resource(su, descriptions.supply),
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
        rev_block = "\n" + get_prompt("block_revelation_ready", weight=str(rev.dramatic_weight), content=rev.content)

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

    thematic = bp.thematic_thread
    thematic_attr = get_prompt("block_story_arc_thematic_attr", thematic=_xa(thematic)) if thematic else ""
    arc = get_prompt(
        "block_story_arc",
        structure=_xa(bp.structure_type),
        act_pos=f"{act.act_number}/{act.total_acts}",
        phase=_xa(act.phase),
        progress=str(act.progress),
        mood=_xa(act.mood),
        conflict=_xa(bp.central_conflict),
        act_goal=_xa(act.goal),
        thematic_attr=thematic_attr,
    )
    return f"{arc}{rev_block}{ending_hint}\n"


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
            lines.append(get_prompt("block_recent_events_line", scene=str(s.scene), summary=_xe(summary)))
    if not lines:
        return ""
    return "\n" + get_prompt("block_recent_events_wrapper", lines="\n".join(lines))


def campaign_history_block(game: GameState) -> str:
    cam = game.campaign
    if not cam.campaign_history:
        return ""
    n = eng().prompt_display.campaign_history_chapters
    chapters = [
        get_prompt(
            "block_campaign_history_chapter",
            n=str(ch.chapter),
            title=_xa(ch.title),
            summary=_xe(ch.summary),
        )
        for ch in cam.campaign_history[-n:]
    ]
    return get_prompt(
        "block_campaign_history_wrapper", count=str(len(cam.campaign_history)), chapters="\n".join(chapters)
    )


def get_narrator_system(config: EngineConfig, game: GameState) -> str:
    lang = get_narration_lang(config)
    cb = content_boundaries_block(game)
    bs = backstory_block(game)
    sc = status_context_block(game)
    vc = vocabulary_block(game)
    tc = truths_block(game)
    ta = tone_authority_block(game)
    return get_prompt(
        "narrator_system",
        lang=lang,
        content_boundaries_block=cb,
        backstory_block=bs,
        status_context_block=sc,
        tone_authority_block=ta,
        vocabulary_block=vc,
        world_truths_block=tc,
    )
