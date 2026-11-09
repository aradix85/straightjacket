from __future__ import annotations

from typing import TYPE_CHECKING, Any

from straightjacket.engine.ai.metadata import process_deceased_npcs
from straightjacket.engine.director import new_guidance
from straightjacket.engine.game.chapters import _close_previous_chapter, _prepare_npcs_for_new_chapter
from straightjacket.engine.game.game_start import take_up_character
from straightjacket.engine.game.setup_common import generate_opening, record_opening
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.keyed_scenes import drop_keyed_scenes_from
from straightjacket.engine.gamemaster.spawn_sources import AC_SOURCE_PREFIX, CLOCK_KEYED_SOURCE_PREFIX
from straightjacket.engine.gamemaster.world import clear_facts
from straightjacket.engine.logging_util import log
from straightjacket.engine.prompt_boundary import build_new_game_prompt
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.ruleset.character import make_character
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.ruleset.succession import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
    threads_for_successor,
)
from straightjacket.engine.setting.packages import load_package

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import AIProvider
    from straightjacket.engine.models import GameState, PredecessorRecord, ProgressTrack, ThreadEntry, ThreatData

END_REASONS: tuple[str, ...] = ("death", "despair", "retire")


def prepare_succession(game: GameState) -> None:
    end_reason = game.end_reason
    if end_reason not in END_REASONS:
        msg = f"Unknown succession end_reason: {end_reason!r} (valid: {END_REASONS})"
        raise ValueError(msg)
    if game.campaign.pending_succession:
        msg = (
            "prepare_succession called while pending_succession is already set. "
            "Call start_succession_with_character to complete the existing succession first."
        )
        raise ValueError(msg)
    record = build_predecessor_record(game, end_reason)
    rolls = run_inheritance_rolls(game)
    record.inheritance_rolls = list(rolls)
    game.campaign.predecessors.append(record)
    game.campaign.pending_succession = True
    log(
        f"[Succession] Predecessor {record.player_name} ({end_reason}) archived at chapter "
        f"{record.chapters_played}, scene {record.scenes_played}: "
        f"legacy boxes {record.legacy_filled_boxes}. pending_succession=True."
    )


def _reset_for_successor(
    game: GameState,
    surviving_threads: list[ThreadEntry],
    surviving_threats: list[ThreatData],
    surviving_npcs: list[Any],
    surviving_connection_tracks: list[ProgressTrack],
) -> None:
    game.resources = starting_resources(game.setting_id)
    game.narrative.scene_count = 1
    game.world.chaos_factor = gm().chaos.start
    game.crisis_mode = False
    game.end_reason = ""
    game.last_turn_snapshot = None

    game.campaign.epilogue_dismissed = False

    game.world.clocks = []
    drop_keyed_scenes_from(game.narrative, (AC_SOURCE_PREFIX, CLOCK_KEYED_SOURCE_PREFIX))
    game.world.combat_position = ""
    game.world.time_of_day = gm().opening.time_of_day
    game.world.location_history = []
    clear_facts(game)

    game.narrative.session_log = []
    game.narrative.narration_history = []
    game.narrative.scene_intensity_history = []
    game.narrative.story_blueprint = None
    game.narrative.director_guidance = new_guidance()

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


def _replace_character_identity(game: GameState, creation_data: dict[str, Any]) -> None:
    pkg = load_package(creation_data["setting_id"])
    take_up_character(game, make_character(creation_data, pkg), creation_data, pkg)
    log(f"[Succession] Successor character: {game.player_name}, concept={game.character_concept!r}, paths={game.paths}")


def start_succession_with_character(
    provider: AIProvider,
    game: GameState,
    creation_data: dict[str, Any],
) -> str:
    if not game.campaign.pending_succession:
        msg = (
            "start_succession_with_character called without pending_succession set. "
            "Call prepare_succession first to lock in inheritance rolls."
        )
        raise ValueError(msg)
    if not game.campaign.predecessors:
        msg = "pending_succession is True but predecessors archive is empty. Save state is corrupt."
        raise ValueError(msg)
    record = game.campaign.predecessors[-1]
    rolls = list(record.inheritance_rolls)

    log(
        f"[Succession] Starting succession at chapter {game.campaign.chapter_number}, "
        f"scene {game.narrative.scene_count}, end_reason={record.end_reason}, "
        f"predecessor={record.player_name}"
    )

    _close_previous_chapter(game)

    kept_npcs, kept_conn_tracks = apply_npc_carryover(game)

    surviving_threads = threads_for_successor(list(game.narrative.threads))
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

    _prepare_npcs_for_new_chapter(game)

    narration, setup_data = generate_opening(provider, game, build_new_game_prompt, label="SuccessionSetup")
    if setup_data["deceased_npcs"]:
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    _record_succession_opening(game, narration, record)

    game.campaign.pending_succession = False

    return narration


def _record_succession_opening(game: GameState, narration: str, predecessor: PredecessorRecord) -> None:
    record_opening(
        game,
        narration,
        history_summary=get_prompt(
            "history_succession_opening",
            player=game.player_name,
            predecessor=predecessor.player_name,
            reason=predecessor.end_reason,
            n=str(game.campaign.chapter_number),
            location=game.world.current_location,
        ),
        log_summary=get_prompt("scene_log_succession_start", predecessor=predecessor.player_name),
    )


__all__ = [
    "END_REASONS",
    "prepare_succession",
    "start_succession_with_character",
]
