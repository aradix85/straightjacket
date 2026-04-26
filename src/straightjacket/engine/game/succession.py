from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..ai.architect import call_story_architect
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..ai.validator import validate_and_retry
from ..datasworn.loader import extract_title
from ..datasworn.settings import load_package
from ..db import sync as _db_sync
from ..db.connection import reset_db
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    apply_npc_carryover,
    build_predecessor_record,
    choose_story_structure,
    record_scene_intensity,
    run_inheritance_rolls,
    seed_successor_legacy,
)
from ..models import (
    DirectorGuidance,
    EngineConfig,
    GameState,
    NarrationEntry,
    PredecessorRecord,
    ProgressTrack,
    Resources,
    SceneLogEntry,
    ThreadEntry,
    ThreatData,
)
from ..parser import parse_narrator_response
from ..prompt_boundary import build_new_game_prompt
from .chapters import (
    _apply_blueprint,
    _close_previous_chapter,
    _prepare_npcs_for_new_chapter,
)
from .game_start import (
    _seed_background_vow,
    _seed_truth_threads,
    _seed_vow_subject,
    validate_creation,
    validate_stats,
)


END_REASONS: tuple[str, ...] = ("death", "despair", "retire")


def determine_end_reason(game: GameState) -> str:
    res = game.resources
    if res.health <= 0 and res.spirit <= 0:
        return "death"
    if res.health <= 0:
        return "death"
    if res.spirit <= 0:
        return "despair"

    return "death"


def prepare_succession(game: GameState, end_reason: str) -> PredecessorRecord:
    if end_reason not in END_REASONS:
        raise ValueError(f"Unknown succession end_reason: {end_reason!r} (valid: {END_REASONS})")
    if game.campaign.pending_succession:
        raise ValueError(
            "prepare_succession called while pending_succession is already set. "
            "Call start_succession_with_character to complete the existing succession first."
        )
    record = build_predecessor_record(game, end_reason)
    rolls = run_inheritance_rolls(game)
    record.inheritance_rolls = list(rolls)
    game.campaign.predecessors.append(record)
    game.campaign.pending_succession = True
    log(
        f"[Succession] Predecessor {record.player_name} ({end_reason}) archived at chapter "
        f"{record.chapters_played}, scene {record.scenes_played}: "
        f"quests={record.legacy_quests_filled_boxes} bonds={record.legacy_bonds_filled_boxes} "
        f"discoveries={record.legacy_discoveries_filled_boxes}. pending_succession=True."
    )
    return record


def _filter_threads_for_successor(threads: list[ThreadEntry]) -> list[ThreadEntry]:
    kept: list[ThreadEntry] = []
    for t in threads:
        if t.thread_type == "vow":
            log(f"[Succession] Drop predecessor vow thread: {t.name}")
            continue
        if t.source == "creation":
            log(f"[Succession] Drop predecessor creation thread: {t.name}")
            continue
        kept.append(t)
    return kept


def _reset_for_successor(
    game: GameState,
    surviving_threads: list[ThreadEntry],
    surviving_threats: list[ThreatData],
    surviving_npcs: list,
    surviving_connection_tracks: list[ProgressTrack],
) -> None:
    _e = eng()
    game.resources = Resources.from_config()
    game.narrative.scene_count = 1
    game.world.chaos_factor = _e.chaos.start
    game.crisis_mode = False
    game.game_over = False

    game.campaign.epilogue_shown = False
    game.campaign.epilogue_dismissed = False
    game.campaign.epilogue_text = ""

    game.world.clocks = []
    game.world.time_of_day = ""
    game.world.location_history = []

    game.narrative.session_log = []
    game.narrative.narration_history = []
    game.narrative.scene_intensity_history = []
    game.narrative.story_blueprint = None
    game.narrative.director_guidance = DirectorGuidance()

    game.narrative.threads = surviving_threads

    surviving_npc_ids = {n.id for n in surviving_npcs}
    game.narrative.characters_list = [
        c for c in game.narrative.characters_list if c.entry_type == "npc" and c.id in surviving_npc_ids
    ]

    game.threats = surviving_threats

    game.impacts = []
    game.assets = []

    game.progress_tracks = surviving_connection_tracks

    game.npcs = surviving_npcs

    log(
        f"[Succession] Reset complete. Surviving: {len(surviving_npcs)} NPCs, "
        f"{len(surviving_connection_tracks)} connection tracks, "
        f"{len(surviving_threats)} threats, {len(surviving_threads)} threads."
    )


def _replace_character_identity(game: GameState, creation_data: dict) -> None:
    pkg = load_package(creation_data["setting_id"])
    stats = creation_data["stats"]
    validate_stats(stats)
    validate_creation(creation_data, pkg)

    player_name = creation_data["player_name"]
    pronouns = creation_data["pronouns"]
    background_vow = creation_data["background_vow"]
    paths = list(creation_data["paths"])
    backstory = creation_data["backstory"]

    if not background_vow:
        raise ValueError(
            "creation_data['background_vow'] is empty. Opening clock requires a background vow on the new character."
        )
    if not player_name:
        raise ValueError("creation_data['player_name'] is empty.")

    path_names = []
    for pid in paths:
        asset = pkg.data.asset("path", pid)
        if asset:
            path_names.append(extract_title(asset, pid))
    concept = ", ".join(path_names) if path_names else ""

    _e = eng()
    stat_names = [n for n in _e.stats.names if n != "none"]
    stat_dict = {n: stats[n] for n in stat_names}

    game.player_name = player_name
    game.character_concept = concept
    game.pronouns = pronouns
    game.paths = paths
    game.background_vow = background_vow
    game.setting_id = creation_data["setting_id"]
    game.setting_genre = pkg.id

    game.backstory = backstory
    game.stats = stat_dict

    game.assets = list(creation_data.get("assets", []))
    game.truths = dict(creation_data.get("truths", {}))
    game.preferences.player_wishes = creation_data.get("wishes", "")
    game.preferences.content_lines = creation_data.get("content_lines", "")
    vow_subject = creation_data.get("vow_subject", "")
    background_vow_rank = creation_data.get("background_vow_rank", "")

    _seed_background_vow(game, background_vow, background_vow_rank)
    _seed_truth_threads(game)
    _seed_vow_subject(game, vow_subject)

    log(f"[Succession] Successor character: {game.player_name}, concept={concept!r}, paths={paths}")


def start_succession_with_character(
    provider: AIProvider,
    game: GameState,
    creation_data: dict,
    config: EngineConfig | None = None,
) -> tuple[GameState, str]:
    if not game.campaign.pending_succession:
        raise ValueError(
            "start_succession_with_character called without pending_succession set. "
            "Call prepare_succession first to lock in inheritance rolls."
        )
    if not game.campaign.predecessors:
        raise ValueError("pending_succession is True but predecessors archive is empty. Save state is corrupt.")
    record = game.campaign.predecessors[-1]
    rolls = list(record.inheritance_rolls)

    log(
        f"[Succession] Starting succession at chapter {game.campaign.chapter_number}, "
        f"scene {game.narrative.scene_count}, end_reason={record.end_reason}, "
        f"predecessor={record.player_name}"
    )

    chapter_summary = _close_previous_chapter(provider, game, config)

    connection_tracks = [t for t in game.progress_tracks if t.track_type == "connection"]
    kept_npcs, kept_conn_tracks = apply_npc_carryover(game.npcs, connection_tracks)

    surviving_threads = _filter_threads_for_successor(list(game.narrative.threads))
    surviving_threats = list(game.threats)

    _reset_for_successor(
        game,
        surviving_threads=surviving_threads,
        surviving_threats=surviving_threats,
        surviving_npcs=kept_npcs,
        surviving_connection_tracks=kept_conn_tracks,
    )

    seed_successor_legacy(game, rolls)
    _replace_character_identity(game, creation_data)

    if chapter_summary.post_story_location:
        game.world.current_location = chapter_summary.post_story_location

    _prepare_npcs_for_new_chapter(game)

    narration, val_report = _generate_succession_opening(provider, game, config)

    _record_succession_opening(game, narration, val_report, record)

    game.campaign.pending_succession = False

    reset_db()
    _db_sync(game)

    return game, narration


def _generate_succession_opening(
    provider: AIProvider, game: GameState, config: EngineConfig | None
) -> tuple[str, dict]:
    structure = choose_story_structure(game.setting_genre)
    narrator_prompt = build_new_game_prompt(game)

    def _run_narrator() -> str:
        return call_narrator(provider, narrator_prompt, game, config)

    def _run_architect() -> dict | None:
        return call_story_architect(provider, game, structure_type=structure, config=config)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(_run_narrator)
        fut_architect = pool.submit(_run_architect)
        raw = fut_narrator.result()
        blueprint = fut_architect.result()

    narration = parse_narrator_response(game, raw)
    narration, val_report = validate_and_retry(provider, narration, narrator_prompt, "opening", game, config=config)

    _apply_blueprint(game, provider, blueprint)

    if not [n for n in game.npcs if n.introduced]:
        _ = call_opening_setup(provider, narration, game, config)

    return narration, val_report


def _record_succession_opening(
    game: GameState, narration: str, val_report: dict, predecessor: PredecessorRecord
) -> None:
    record_scene_intensity(game, "action")
    summary = (
        f"Succession opening: {game.player_name} continues after {predecessor.player_name} "
        f"({predecessor.end_reason}) — chapter {game.campaign.chapter_number}, "
        f"location {game.world.current_location}"
    )
    game.narrative.narration_history.append(
        NarrationEntry(
            scene=1,
            prompt_summary=summary,
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary=f"Succession from {predecessor.player_name}",
            result="opening",
            validator=val_report,
        )
    )


__all__ = [
    "END_REASONS",
    "determine_end_reason",
    "prepare_succession",
    "start_succession_with_character",
]
