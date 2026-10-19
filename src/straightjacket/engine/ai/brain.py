import html
import json
from typing import Any, NoReturn

from ..config_loader import model_for_role, narration_language, sampling_params
from ..engine_loader import eng
from ..gamemaster.clocks import open_complications
from ..gamemaster.config import gm
from ..gamemaster.config_types import GameMasterMove
from ..logging_util import log
from ..models import BrainResult, GameState, Revelation, ThreatData
from ..prompt_blocks import (
    content_boundaries_block,
    world_tag,
)
from ..prompt_loader import get_prompt, get_prompt_prefix
from ..ruleset.bond import connection_track, is_bonded, starts_a_connection
from ..ruleset.bonuses import bonus_block, roll_bonuses
from ..ruleset.config import rules
from ..ruleset.config_types import EngineMove
from ..ruleset.move_availability import available_moves
from ..ruleset.move_outcome import acts_on_an_npc
from ..ruleset.moves import PICK_METHODS, Move, get_moves
from ..ruleset.progress import filled_boxes, menace_boxes, menace_total_boxes
from ..ruleset.roll_sources import roll_source_without_stat
from ..ruleset.stats import stat_descriptions
from ..ruleset.threats import active_threats, vow_against
from ..ruleset.tracks import active_tracks, track_category_of_move
from ..xml_utils import xe as _xe
from .provider_base import AICallSpec, AIProvider, AIUnavailableError, create_with_retry
from .schemas import get_brain_output_schema, get_revelation_check_schema


def _ways(move: Move) -> list[str]:
    ways: list[str] = []
    for condition in move.conditions:
        if condition.method in PICK_METHODS:
            options = [
                o.stat or o.condition_meter for o in condition.roll_options if o.using in ("stat", "condition_meter")
            ]
            labels = [get_prompt("brain_pick_way", method=condition.method, options=", ".join(options))]
        else:
            labels = [o.stat for o in condition.roll_options if o.using == "stat" and o.stat]
        ways.extend(f"{label}: {condition.text}" if condition.text else label for label in labels)
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
        stats = " | ".join(ways) if ways else eng().ai_text.no_stat
        hint = trigger_hints.get(key, "")
        trigger = f" when:{hint}" if hint else ""
        lines.append(f"  {key} ({move.name}) stats:[{stats}] roll:{roll}{trigger}")

    pos_line = f"  combat_position: {combat_pos}" if combat_pos else ""
    return "<moves>\n" + "\n".join(lines) + ("\n" + pos_line if pos_line else "") + "\n</moves>"


def _stats_block(game: GameState) -> str:
    return " ".join(f"{name}={_xe(text)}" for name, text in stat_descriptions(game.setting_id).items())


def _build_stats_line(game: GameState) -> str:
    abbreviations = rules().stats.prompt_abbreviations
    stats = [f"{abbreviations[name]}{game.stats[name]}" for name in stat_descriptions(game.setting_id)]
    return " ".join([_xe(game.player_name), *stats])


def _listed_npcs(game: GameState) -> list[Any]:
    return [n for n in game.npcs if n.status in gm().npc_status_groups.in_play]


def _build_tracks_block(game: GameState) -> str:
    tracks = active_tracks(game)
    if not tracks:
        return ""
    lines = [
        f"  {_xe(t.name)} (id:{t.id}, {t.track_type}, {t.rank}) {filled_boxes(t)}/{rules().progress.boxes}"
        for t in tracks
    ]
    return "<tracks>\n" + "\n".join(lines) + "\n</tracks>"


def _threat_line(game: GameState, threat: ThreatData) -> str:
    texts = eng().ai_text.narrator_defaults
    line: str = texts["threat_danger"].format(
        name=_xe(threat.name), id=threat.id, filled=menace_boxes(threat), total=menace_total_boxes(threat)
    )
    vow = vow_against(game, threat)
    return line if vow is None else line + texts["threat_vow"].format(vow=_xe(vow.name))


def _build_dangers_block(game: GameState) -> str:
    lines = [f"  {_xe(c.name)} {c.filled}/{c.segments}" for c in open_complications(game)]
    lines += [_threat_line(game, t) for t in active_threats(game)]
    if not lines:
        return ""
    return "<dangers>\n" + "\n".join(lines) + "\n</dangers>"


def _build_fact_types_block() -> str:
    types = gm().fact_resolution.types
    lines = [f"  {name} [{spec.subject}]: {spec.description}" for name, spec in types.items()]
    return "<fact_types>\n" + "\n".join(lines) + "\n</fact_types>"


def _refuse(reason: str) -> NoReturn:
    log(f"[Brain] Refused: {reason}", level="warning")
    raise AIUnavailableError(f"brain: {reason}")


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
    if result.move in rules().get_raw("track_creating_moves") and not (result.track_name and result.track_name.strip()):
        _refuse(f"move {result.move!r} starts a track, but track_name is empty")
    if starts_a_connection(result.move) and result.target_npc is None:
        _refuse(f"move {result.move!r} makes a connection, but names no target_npc")
    boasts = rules().boasts
    if len(result.boasts) > boasts.max_per_roll or any(b not in boasts.options for b in result.boasts):
        _refuse(f"boasts {result.boasts!r} are not among the offered boasts")


def _check_target_npc(game: GameState, result: BrainResult) -> None:
    if result.target_npc is not None or result.dialog_only or result.move not in get_moves(game.setting_id):
        return
    if acts_on_an_npc(game, result.move):
        _refuse(f"move {result.move!r} acts on an NPC, but names no target_npc")


def _check_target_track(game: GameState, result: BrainResult) -> None:
    if result.target_track is None:
        return
    category = track_category_of_move(game, result.move)
    if category is None:
        return
    wanted = rules().get_raw("track_types_by_category")[category]
    track = next(t for t in game.progress_tracks if t.id == result.target_track)
    if track.track_type != wanted:
        _refuse(
            f"move {result.move!r} works on a {wanted} track, but target_track {track.id!r} is a {track.track_type} track"
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
        raise AIUnavailableError(f"brain: {type(e).__name__}: {e}") from e


def call_brain(provider: AIProvider, game: GameState, player_message: str) -> BrainResult:
    _brain_lang = narration_language()

    log(f"[Brain] Scene {game.narrative.scene_count + 1} | Input: {player_message[: eng().truncations.log_long]}")

    system_variables = {
        "lang": _brain_lang,
        "world": world_tag(game),
        "content_boundaries_block": content_boundaries_block(game),
        "stats": _stats_block(game),
        "fact_types_block": _build_fact_types_block(),
        "max_facts": str(gm().fact_resolution.max_per_turn),
        "place": gm().fact_resolution.place_reference,
    }
    system = get_prompt("brain_parser", moves_block=_build_moves_block(game), **system_variables)
    cached_prefix = get_prompt_prefix("brain_parser", "moves_block", **system_variables)

    w = game.world
    _ai_text = eng().ai_text.narrator_defaults

    npc_lines = []
    for n in _listed_npcs(game):
        connection = connection_track(game, n.id)
        bonded = ", bonded" if connection is not None and is_bonded(connection) else ""
        entry = f"  {_xe(n.name)} (id:{n.id}, {n.disposition}{bonded})"
        if n.aliases:
            entry += f" aliases:{_xe(','.join(n.aliases))}"
        npc_lines.append(entry)
    npc_block = "<npcs>\n" + "\n".join(npc_lines) + "\n</npcs>" if npc_lines else f"<npcs>{_ai_text['no_npcs']}</npcs>"

    tracks_block = _build_tracks_block(game)
    dangers_block = _build_dangers_block(game)
    bonuses = bonus_block(game)

    user_msg = f"""<state>
loc:{_xe(w.current_location)} | ctx:{_xe(w.current_scene_context)}
time:{w.time_of_day or _ai_text["unknown_time"]}
{_build_stats_line(game)}
</state>
{npc_block}
{tracks_block}
{dangers_block}
{bonuses}
<input>{_xe(player_message)}</input>"""

    move_keys = list(_offered_moves(game))
    choices = {
        "bonus_id": [b.id for b in roll_bonuses(game)],
        "target_npc": [n.id for n in _listed_npcs(game)],
        "target_track": [tr.id for tr in active_tracks(game)],
        "target_clock": [c.name for c in open_complications(game)],
        "target_threat": [t.id for t in active_threats(game) if vow_against(game, t) is None],
    }
    schema = get_brain_output_schema(
        move_keys,
        list(stat_descriptions(game.setting_id)),
        choices["bonus_id"],
        choices["target_npc"],
        choices["target_track"],
        choices["target_clock"],
        choices["target_threat"],
    )
    model = model_for_role("brain")
    params = sampling_params("brain")
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_msg}]
    for _attempt in range(eng().retry.brain_stat_retries + 1):
        spec = AICallSpec(
            model=model,
            system=system,
            messages=list(messages),
            json_schema=schema,
            log_role="brain",
            cached_system_prefix=cached_prefix,
            **params,
        )
        content, result = _ask_brain(provider, spec)
        _check_choices(result, move_keys, choices)
        _check_target_npc(game, result)
        _check_target_track(game, result)
        stats = _wrong_stat(game, result)
        if not stats:
            log(
                f"[Brain] move={result.move}, stat={result.stat}, "
                f"intent={result.player_intent[: eng().truncations.log_short]}"
                + (f", target_clock={result.target_clock}" if result.target_clock else "")
                + (f", target_threat={result.target_threat}" if result.target_threat else "")
            )
            return result
        log(f"[Brain] {result.move} rolls with {stats}, not stat {result.stat!r}; asking again", level="warning")
        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": get_prompt("brain_stat_retry", move=result.move, stats=", ".join(stats), stat=result.stat),
            }
        )
    _refuse(f"move {result.move!r} rolls with {stats}, but stat is {result.stat!r} after asking again")


def call_revelation_check(provider: AIProvider, narration: str, revelation: Revelation) -> bool:
    lang = narration_language()
    rev_content = revelation.content
    rev_weight = revelation.dramatic_weight

    system = get_prompt("revelation_check_system", lang=lang)

    prompt = (
        f'<revelation weight="{html.escape(rev_weight, quote=True)}">{html.escape(rev_content)}</revelation>\n\n'
        f"<narration>{narration}</narration>\n\n"
        f"{get_prompt('revelation_check_question')}"
    )

    spec = AICallSpec(
        model=model_for_role("revelation_check"),
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_revelation_check_schema(),
        log_role="revelation_check",
        **sampling_params("revelation_check"),
    )
    try:
        result = json.loads(create_with_retry(provider, spec).content)
        confirmed: bool = result["revelation_confirmed"]
        reasoning = result["reasoning"]
        log(f"[Revelation] Check for '{revelation.id}': confirmed={confirmed} — {reasoning}")
        return confirmed
    except Exception as e:
        log(f"[Revelation] Check failed ({type(e).__name__}: {e}), counting as not yet confirmed", level="warning")
        return False
