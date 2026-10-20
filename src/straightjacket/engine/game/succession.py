from __future__ import annotations

import random as _random_module
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..ai.blueprint_voicing import call_blueprint_voicing
from ..ai.metadata import process_deceased_npcs
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..crafters.blueprint import assemble_blueprint_seed_from_ac, assemble_blueprint_seed_kishotenketsu
from ..director import new_guidance
from ..gamemaster.config import gm
from ..gamemaster.story import choose_story_structure
from ..gamemaster.world import clear_facts
from ..logging_util import log
from ..models import GameState, PredecessorRecord, ProgressTrack, ThreadEntry, ThreatData
from ..parser import parse_narrator_response
from ..prompt_boundary import build_new_game_prompt
from ..prompt_loader import get_prompt
from ..ruleset.character import make_character
from ..ruleset.meters import starting_resources
from ..ruleset.succession import (
    apply_npc_carryover,
    build_predecessor_record,
    run_inheritance_rolls,
    seed_successor_legacy,
    threads_for_successor,
)
from ..setting.packages import load_package
from .chapters import (
    _apply_blueprint,
    _close_previous_chapter,
    _prepare_npcs_for_new_chapter,
)
from .game_start import take_up_character
from .setup_common import apply_opening_setup, record_opening

END_REASONS: tuple[str, ...] = ("death", "despair", "retire")


def prepare_succession(game: GameState) -> None:
    end_reason = game.end_reason
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

    _close_previous_chapter(game)

    kept_npcs, kept_conn_tracks = apply_npc_carryover(game.npcs, game.progress_tracks)

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

    narration = _generate_succession_opening(provider, game)

    _record_succession_opening(game, narration, record)

    game.campaign.pending_succession = False

    return narration


def _generate_succession_opening(provider: AIProvider, game: GameState) -> str:
    structure = choose_story_structure(game.setting_tone)
    rng = _random_module.Random()
    if structure == "kishotenketsu":
        seed = assemble_blueprint_seed_kishotenketsu(rng, game)
    else:
        seed = assemble_blueprint_seed_from_ac(rng, game)
    log(f"[Succession] Blueprint seed assembled: structure={seed.structure_type}")

    narrator_prompt = build_new_game_prompt(game)

    def _run_narrator() -> str:
        return call_narrator(provider, narrator_prompt, game)

    def _run_voicing() -> dict[str, Any] | None:
        return call_blueprint_voicing(provider, game, seed)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(_run_narrator)
        fut_voicing = pool.submit(_run_voicing)
        raw = fut_narrator.result()
        voicing = fut_voicing.result()

    narration = parse_narrator_response(game, raw)

    _apply_blueprint(game, seed, voicing)

    setup_data = call_opening_setup(provider, narration, game)
    apply_opening_setup(game, setup_data, label="SuccessionSetup")
    if setup_data["deceased_npcs"]:
        process_deceased_npcs(game, setup_data["deceased_npcs"])

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
