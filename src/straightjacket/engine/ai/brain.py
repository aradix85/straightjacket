import json
from typing import TYPE_CHECKING, NoReturn

from straightjacket.engine.ai.provider_base import AICallSpec, AIProvider, AIUnavailableError, create_with_retry
from straightjacket.engine.ai.schemas import get_brain_output_schema
from straightjacket.engine.config_loader import model_for_role, narration_language, sampling_params
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.clocks import open_complications
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.config_types import GameMasterMove
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import BrainResult, GameState, NpcData, ThreatData
from straightjacket.engine.prompt_blocks import content_boundaries_block, world_tag
from straightjacket.engine.prompt_loader import get_prompt, get_prompt_prefix
from straightjacket.engine.ruleset.bond import connection_track, is_bonded, starts_a_connection
from straightjacket.engine.ruleset.bonuses import bonus_block, roll_bonuses
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.config_types import EngineMove
from straightjacket.engine.ruleset.move_availability import available_moves
from straightjacket.engine.ruleset.move_outcome import acts_on_an_npc, needs_a_connection
from straightjacket.engine.ruleset.moves import PICK_METHODS, Move, get_moves
from straightjacket.engine.ruleset.progress import filled_boxes, menace_boxes, menace_total_boxes
from straightjacket.engine.ruleset.roll_sources import roll_source_without_stat
from straightjacket.engine.ruleset.stats import stat_descriptions
from straightjacket.engine.ruleset.threats import active_threats, vow_against
from straightjacket.engine.ruleset.tracks import active_tracks, track_category_of_move
from straightjacket.engine.xml_utils import xe as _xe

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import Message


def _ways(move: Move) -> list[str]:
    ways: list[str] = []
    for condition in move.conditions:
        if condition.method in PICK_METHODS:
            options = [
                o.stat or o.condition_meter for o in condition.roll_options if o.using in {"stat", "condition_meter"}
            ]
            labels = [get_prompt("brain_pick_way", method=condition.method, options=", ".join(options))]
        else:
            labels = [o.stat for o in condition.roll_options if o.using == "stat" and o.stat]
        ways.extend(
            get_prompt("brain_way", way=label, text=condition.text) if condition.text else label for label in labels
        )
    return ways


def _offered_moves(game: GameState) -> dict[str, Move | GameMasterMove | EngineMove]:
    return {**available_moves(game), **gm().moves, **rules().engine_moves}


def _ways_and_roll(move: Move | GameMasterMove | EngineMove) -> tuple[list[str], str]:
    if isinstance(move, Move):
        return _ways(move), move.roll_type
    if isinstance(move, EngineMove):
        return move.stats, move.roll_type
    return [], eng().ai_text.no_roll_type


def _build_moves_block(game: GameState) -> str:
    combat_pos = game.world.combat_position
    trigger_hints = eng().ai_text.brain_trigger_hints

    lines = []
    for key, move in _offered_moves(game).items():
        ways, roll = _ways_and_roll(move)
        hint = trigger_hints.get(key)
        lines.append(
            get_prompt(
                "brain_move_line",
                key=key,
                move=move.name,
                stats=" | ".join(ways) if ways else eng().ai_text.no_stat,
                roll=roll,
                trigger=get_prompt("brain_move_trigger", hint=hint) if hint else "",
            )
        )
    if combat_pos:
        lines.append(get_prompt("brain_combat_position", position=combat_pos))
    return get_prompt("brain_moves_wrapper", lines="\n".join(lines))


def _stats_block(game: GameState) -> str:
    return " ".join(
        get_prompt("brain_stat", stat=name, description=_xe(text))
        for name, text in stat_descriptions(game.setting_id).items()
    )


def _build_stats_line(game: GameState) -> str:
    abbreviations = rules().stats.prompt_abbreviations
    stats = [
        get_prompt("brain_stat_value", abbreviation=abbreviations[name], value=str(game.stats[name]))
        for name in stat_descriptions(game.setting_id)
    ]
    return " ".join([_xe(game.player_name), *stats])


def _listed_npcs(game: GameState) -> list[NpcData]:
    return [n for n in game.npcs if n.status in gm().npc_status_groups.in_play]


def _build_tracks_block(game: GameState) -> str:
    tracks = active_tracks(game)
    if not tracks:
        return ""
    lines = [
        get_prompt(
            "brain_track_line",
            track=_xe(t.name),
            id=t.id,
            track_type=t.track_type,
            rank=t.rank,
            filled=str(filled_boxes(t)),
            boxes=str(rules().progress.boxes),
        )
        for t in tracks
    ]
    return get_prompt("brain_tracks_wrapper", lines="\n".join(lines))


def _threat_line(game: GameState, threat: ThreatData) -> str:
    texts = eng().ai_text.narrator_defaults
    line: str = texts["threat_danger"].format(
        name=_xe(threat.name), id=threat.id, filled=menace_boxes(threat), total=menace_total_boxes(threat)
    )
    vow = vow_against(game, threat)
    return line if vow is None else line + texts["threat_vow"].format(vow=_xe(vow.name))


def _build_dangers_block(game: GameState) -> str:
    lines = [
        get_prompt("brain_danger_clock_line", clock=_xe(c.name), filled=str(c.filled), segments=str(c.segments))
        for c in open_complications(game)
    ]
    lines += [_threat_line(game, t) for t in active_threats(game)]
    if not lines:
        return ""
    return get_prompt("brain_dangers_wrapper", lines="\n".join(lines))


def _build_fact_types_block() -> str:
    types = gm().fact_resolution.types
    lines = [
        get_prompt("brain_fact_type_line", fact_type=fact_type, subject=spec.subject, description=spec.description)
        for fact_type, spec in types.items()
    ]
    return get_prompt("brain_fact_types_wrapper", lines="\n".join(lines))


def _refuse(reason: str) -> NoReturn:
    log(f"[Brain] Refused: {reason}", level="warning")
    msg = f"brain: {reason}"
    raise AIUnavailableError(msg)


def _check_choices(result: BrainResult, move_keys: list[str], choices: dict[str, list[str]]) -> None:
    if result.move not in move_keys:
        _refuse(f"move {result.move!r} is not available in this situation")
    for field_name, allowed in choices.items():
        value = getattr(result, field_name)
        if value is not None and value not in allowed:
            _refuse(f"{field_name} {value!r} is not one of the choices offered")
    _check_fact_requests(result, choices["target_npc"])
    change = result.location_change
    if change is not None and change.kind not in gm().generation.place_categories:
        _refuse(f"location kind {change.kind!r} is not one of the choices offered")
    if result.move in rules().track_creating_moves and not (result.track_name and result.track_name.strip()):
        _refuse(f"move {result.move!r} starts a track, but track_name is empty")
    if starts_a_connection(result.move) and result.target_npc is None:
        _refuse(f"move {result.move!r} makes a connection, but names no target_npc")
    boasts = rules().boasts
    if len(result.boasts) > boasts.max_per_roll or any(b not in boasts.options for b in result.boasts):
        _refuse(f"boasts {result.boasts!r} are not among the offered boasts")


def _check_target_npc(game: GameState, result: BrainResult) -> None:
    if result.dialog_only or result.move not in get_moves(game.setting_id):
        return
    if result.target_npc is None:
        if acts_on_an_npc(game, result.move):
            _refuse(f"move {result.move!r} acts on an NPC, but names no target_npc")
        return
    if needs_a_connection(game, result.move) and connection_track(game, result.target_npc) is None:
        _refuse(f"move {result.move!r} needs a connection, but target_npc {result.target_npc!r} has none")


def _check_target_track(game: GameState, result: BrainResult) -> None:
    category = track_category_of_move(game, result.move)
    if category is None:
        return
    wanted = rules().track_types_by_category[category]
    if result.target_track is None:
        if result.dialog_only or result.move in rules().track_creating_moves:
            return
        if len([t for t in active_tracks(game) if t.track_type == wanted]) > 1:
            _refuse(f"move {result.move!r} works on one of several active {wanted} tracks, but names no target_track")
        return
    track = next(t for t in game.progress_tracks if t.id == result.target_track)
    if track.track_type != wanted:
        _refuse(
            f"move {result.move!r} works on a {wanted} track, "
            f"but target_track {track.id!r} is a {track.track_type} track"
        )


def _wrong_stat(game: GameState, result: BrainResult) -> list[str]:
    ds_move = get_moves(game.setting_id).get(result.move)
    if result.dialog_only or result.move in gm().moves:
        return []
    if ds_move is None:
        return list(rules().engine_moves[result.move].stats) if result.stat in PICK_METHODS else []
    if not ds_move.is_action_roll:
        return []
    if not ds_move.valid_stats:
        if roll_source_without_stat(game, ds_move, result.target_npc) is None:
            _refuse(f"move {result.move!r} has nothing to roll with for target_npc {result.target_npc!r}")
        return []
    return [] if result.stat in ds_move.stat_answers else ds_move.stat_answers


def _check_fact_requests(result: BrainResult, npc_ids: list[str]) -> None:
    cfg = gm().fact_resolution
    if len(result.undetermined_facts) > cfg.max_per_turn:
        _refuse(f"{len(result.undetermined_facts)} undetermined facts, at most {cfg.max_per_turn} allowed")
    for request in result.undetermined_facts:
        if request.fact_type not in cfg.types:
            _refuse(f"fact_type {request.fact_type!r} is not one of the choices offered")
        allowed = [cfg.place_reference] if cfg.types[request.fact_type].subject == "place" else npc_ids
        if request.about not in allowed:
            _refuse(f"fact {request.fact_type!r} cannot be about {request.about!r}")


def _ask_brain(provider: AIProvider, spec: AICallSpec) -> tuple[str, BrainResult]:
    try:
        content = create_with_retry(provider, spec).content
        return content, BrainResult.from_dict(json.loads(content))
    except Exception as e:
        log(f"[Brain] Failed ({type(e).__name__}: {e})", level="warning")
        msg = f"brain: {type(e).__name__}: {e}"
        raise AIUnavailableError(msg) from e


def _system_prompt(game: GameState) -> tuple[str, str]:
    system_variables = {
        "lang": narration_language(),
        "world": world_tag(game),
        "content_boundaries_block": content_boundaries_block(game),
        "stats": _stats_block(game),
        "fact_types_block": _build_fact_types_block(),
        "max_facts": str(gm().fact_resolution.max_per_turn),
        "place": gm().fact_resolution.place_reference,
    }
    system = get_prompt("brain_parser", moves_block=_build_moves_block(game), **system_variables)
    return system, get_prompt_prefix("brain_parser", "moves_block", **system_variables)


def _build_npcs_block(game: GameState) -> str:
    npc_lines = []
    for n in _listed_npcs(game):
        connection = connection_track(game, n.id)
        entry = get_prompt(
            "brain_npc_line",
            npc=_xe(n.name),
            id=n.id,
            disposition=n.disposition,
            bonded=get_prompt("brain_npc_bonded") if connection is not None and is_bonded(connection) else "",
        )
        if n.aliases:
            entry += get_prompt("brain_npc_aliases", aliases=_xe(",".join(n.aliases)))
        npc_lines.append(entry)
    if npc_lines:
        return get_prompt("brain_npcs_wrapper", lines="\n".join(npc_lines))
    return get_prompt("brain_npcs_none", none=eng().ai_text.narrator_defaults["no_npcs"])


def _build_user_message(game: GameState, player_message: str) -> str:
    w = game.world
    return get_prompt(
        "brain_user_message",
        location=_xe(w.current_location),
        context=_xe(w.current_scene_context),
        time=w.time_of_day or eng().ai_text.narrator_defaults["unknown_time"],
        stats=_build_stats_line(game),
        npcs=_build_npcs_block(game),
        tracks=_build_tracks_block(game),
        dangers=_build_dangers_block(game),
        bonuses=bonus_block(game),
        input=_xe(player_message),
    )


def _choices(game: GameState) -> dict[str, list[str]]:
    return {
        "bonus_id": [b.id for b in roll_bonuses(game)],
        "target_npc": [n.id for n in _listed_npcs(game)],
        "target_track": [tr.id for tr in active_tracks(game)],
        "target_clock": [c.name for c in open_complications(game)],
        "target_threat": [t.id for t in active_threats(game) if vow_against(game, t) is None],
    }


def _log_result(result: BrainResult) -> None:
    log(
        f"[Brain] move={result.move}, stat={result.stat}, "
        f"intent={result.player_intent[: eng().truncations.log_short]}"
        + (f", target_clock={result.target_clock}" if result.target_clock else "")
        + (f", target_threat={result.target_threat}" if result.target_threat else "")
    )


def call_brain(provider: AIProvider, game: GameState, player_message: str) -> BrainResult:
    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[: eng().truncations.log_long]}")

    system, cached_prefix = _system_prompt(game)
    move_keys = list(_offered_moves(game))
    choices = _choices(game)
    schema = get_brain_output_schema(
        move_keys=move_keys,
        stat_names=list(stat_descriptions(game.setting_id)),
        bonus_ids=choices["bonus_id"],
        npc_ids=choices["target_npc"],
        track_ids=choices["target_track"],
        clock_names=choices["target_clock"],
        threat_ids=choices["target_threat"],
    )
    messages: list[Message] = [{"role": "user", "content": _build_user_message(game, player_message)}]
    retries_asked = 0
    while True:
        spec = AICallSpec(
            model=model_for_role("brain"),
            system=system,
            messages=list(messages),
            json_schema=schema,
            tools=None,
            log_role="brain",
            cached_system_prefix=cached_prefix,
            sampling=sampling_params("brain"),
        )
        content, result = _ask_brain(provider, spec)
        _check_choices(result, move_keys, choices)
        _check_target_npc(game, result)
        _check_target_track(game, result)
        stats = _wrong_stat(game, result)
        if not stats:
            _log_result(result)
            return result
        if retries_asked >= eng().retry.brain_stat_retries:
            _refuse(f"move {result.move!r} rolls with {stats}, but stat is {result.stat!r} after asking again")
        retries_asked += 1
        log(f"[Brain] {result.move} rolls with {stats}, not stat {result.stat!r}; asking again", level="warning")
        messages.extend(
            (
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": get_prompt(
                        "brain_stat_retry", move=result.move, stats=", ".join(stats), stat=result.stat
                    ),
                },
            )
        )
