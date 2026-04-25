"""Character succession orchestration: Continue a Legacy.

When the player character ends — face_death MISS, double-zero crisis, or
manual /retire — the campaign continues with a new character who inherits a
portion of the predecessor's legacy progress and a curated set of NPCs.

Implementation pulls together:
- mechanics/succession.py: the inheritance roll, NPC carry-over rules, and
  the predecessor archive entry.
- game/chapters.py: chapter close (`_close_previous_chapter`) and per-chapter
  mechanical reset (`_reset_chapter_mechanics`). Succession is mechanically
  a chapter transition with character replacement.
- game/game_start.py: the seeding helpers for background vow, truth threads,
  and vow subject. The new character receives the same setup the first
  character did, on top of the surviving campaign state.

The leading underscore on imported helpers is intentional: they are private
to the chapter and game-start modules, but are sharable to this neighbouring
module that completes the same conceptual surface (character lifecycle).

The flow:

  prepare_succession  →  start_succession_with_character

prepare_succession archives the predecessor, runs the inheritance rolls, and
returns the records for the UI to display before the new character is built.
start_succession_with_character accepts the new creation_data and finishes
the transition: chapter close, mechanical reset with succession-specific
filtering, character replacement, NPC carry-over, opening narration.
"""

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


# Reasons a character ends. The web layer maps incoming triggers to these
# values; engine code reads them as opaque strings except in the predecessor
# record. Kept here as the canonical list rather than yaml because the engine
# itself enumerates them.
END_REASONS: tuple[str, ...] = ("death", "despair", "retire")


def determine_end_reason(game: GameState) -> str:
    """Classify why the predecessor's run is ending.

    Used when the web layer triggers succession from a `game_over` flag and
    needs to know whether it was death (health) or despair (spirit) or both.
    Manual /retire is set explicitly by the handler, not via this function.
    """
    res = game.resources
    if res.health <= 0 and res.spirit <= 0:
        return "death"
    if res.health <= 0:
        return "death"
    if res.spirit <= 0:
        return "despair"
    # game_over set by face_death MISS without crisis — treat as death.
    return "death"


def prepare_succession(game: GameState, end_reason: str) -> PredecessorRecord:
    """Archive the predecessor and roll inheritance against each legacy track.

    Persists the predecessor with rolls into game.campaign.predecessors and
    sets game.campaign.pending_succession=True. Does not mutate legacy tracks
    yet; that happens in start_succession_with_character once the new
    character's creation_data is known. Calling this twice on the same
    GameState is rejected — once a succession is pending, the next step is
    start_succession_with_character or save-load-resume.

    Returning the record (also reachable via game.campaign.predecessors[-1])
    is for the immediate caller; the persistence guarantee is the campaign
    archive plus the pending_succession flag.
    """
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
    """Drop predecessor-specific threads, keep world-narrative threads.

    Vow threads (thread_type=='vow') are PC-specific by definition. Tension
    and goal threads sourced from creation are also PC-specific (truth
    threads, character backstory). Director- and event-sourced threads are
    world narrative and survive succession.
    """
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
    surviving_npcs: list,  # list[NpcData]
    surviving_connection_tracks: list[ProgressTrack],
) -> None:
    """Reset per-character state for the successor; carry world-level state.

    Differs from chapters._reset_chapter_mechanics: threads and threats
    survive (filtered for PC-specific entries), connection tracks survive
    (already filtered+rescaled), but PC-specific tracks (vows, combat,
    expedition, scene_challenge) and impacts and assets are wiped.
    Resources reset to defaults; world clocks cleared (a new character does
    not inherit narrative clocks); story blueprint cleared (new arc).

    Legacy tracks on CampaignState are not touched here — seed_successor_legacy
    runs separately and overwrites them from the inheritance rolls.
    The predecessor archive entry was added in prepare_succession.
    """
    _e = eng()
    game.resources = Resources.from_config()
    game.narrative.scene_count = 1
    game.world.chaos_factor = _e.chaos.start
    game.crisis_mode = False
    game.game_over = False

    # Wipe predecessor-only narrative artefacts. campaign_history persists
    # (it's the accumulated record of previous chapters), but the in-flight
    # epilogue display state belonged to the predecessor.
    game.campaign.epilogue_shown = False
    game.campaign.epilogue_dismissed = False
    game.campaign.epilogue_text = ""

    game.world.clocks = []
    game.world.time_of_day = ""
    game.world.location_history = []
    # Current location may carry from the chapter close (post_story_location);
    # the successor's opening narration may reposition them. Leave it.

    game.narrative.session_log = []
    game.narrative.narration_history = []
    game.narrative.scene_intensity_history = []
    game.narrative.story_blueprint = None
    game.narrative.director_guidance = DirectorGuidance()

    # Filter narrative.threads (already filtered, just install).
    game.narrative.threads = surviving_threads
    # Drop the vow_subject and other abstract PC-anchored character_list
    # entries; keep NPC entries (they correspond to surviving NPCs).
    surviving_npc_ids = {n.id for n in surviving_npcs}
    game.narrative.characters_list = [
        c for c in game.narrative.characters_list if c.entry_type == "npc" and c.id in surviving_npc_ids
    ]

    # Threats: world-level, survive untouched.
    game.threats = surviving_threats

    # Impacts and assets are PC-specific.
    game.impacts = []
    game.assets = []

    # Tracks: only carry connection-tracks (already filtered+rescaled).
    # Vow, combat, expedition, scene_challenge tracks were predecessor-owned.
    # Custom tracks: depends on creator. Conservative call: drop all
    # non-connection tracks; the successor establishes their own.
    game.progress_tracks = surviving_connection_tracks

    # NPCs: install the filtered roster.
    game.npcs = surviving_npcs

    log(
        f"[Succession] Reset complete. Surviving: {len(surviving_npcs)} NPCs, "
        f"{len(surviving_connection_tracks)} connection tracks, "
        f"{len(surviving_threats)} threats, {len(surviving_threads)} threads."
    )


def _replace_character_identity(game: GameState, creation_data: dict) -> None:
    """Replace the PC-identifying fields with the new character's data.

    Mirrors the GameState construction in start_new_game but mutates in
    place to preserve the campaign-wide and world-wide state already on
    the GameState. Fields touched: player_name, character_concept, paths,
    pronouns, background_vow, backstory, assets, truths, stats, plus the
    re-seeded background-vow track / vow thread / truth threads / vow
    subject character entry.

    creation_data is WebSocket input and falls under the external-boundary
    parsing exception, but succession runs through a single client flow
    we control — the client knows exactly which fields to send. Required
    fields are subscripted directly and raise on absence; only fields
    that are genuinely optional per the setting (truths, wishes, vow
    subject, etc.) tolerate absence.
    """
    # Required: setting_id, stats — used for package + stat validation.
    pkg = load_package(creation_data["setting_id"])
    stats = creation_data["stats"]
    validate_stats(stats)
    validate_creation(creation_data, pkg)

    # Required: player_name, pronouns, background_vow, paths, backstory.
    # paths and backstory may be empty list/string but must be present.
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
    # setting_tone, setting_archetype, setting_description: keep — same campaign world.
    game.backstory = backstory
    game.stats = stat_dict

    # Genuinely optional per setting / UI flow. External-boundary exception:
    # absent → empty/default. Each one is intrinsically optional: assets and
    # truths depend on setting flow flags; player_wishes/content_lines/vow
    # subject/vow rank are UI surfaces a setting may not have at all.
    game.assets = list(creation_data.get("assets", []))
    game.truths = dict(creation_data.get("truths", {}))
    game.preferences.player_wishes = creation_data.get("wishes", "")
    game.preferences.content_lines = creation_data.get("content_lines", "")
    vow_subject = creation_data.get("vow_subject", "")
    background_vow_rank = creation_data.get("background_vow_rank", "")

    # Re-seed PC-specific narrative artefacts.
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
    """Complete a pending character succession: replace character, generate opening.

    Requires prepare_succession to have run first — the predecessor must be
    archived in game.campaign.predecessors and pending_succession must be True.
    The inheritance rolls were locked in at prepare time and persist on the
    predecessor record; this function reads them and applies. Re-rolling at
    start time would let players reload-roll for better outcomes.

    Phase ordering:
      1. read predecessor + rolls from campaign archive (raises if no pending)
      2. close previous chapter (AI summary + chapter_validator)
      3. apply NPC carry-over to current state
      4. reset for successor (clears PC-specific state, keeps world)
      5. seed successor legacy from the locked-in rolls
      6. replace character identity from creation_data
      7. generate opening narration with surviving NPCs as returning roster
      8. clear pending_succession; db reset + sync
    """
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

    # Use the chapter_summary's post_story_location as the successor's
    # starting location, same way start_new_chapter does.
    if chapter_summary.post_story_location:
        game.world.current_location = chapter_summary.post_story_location

    # The successor opens at chapter_number that _close_previous_chapter
    # already incremented. Consolidate NPC memory to make the surviving
    # roster feel weighted-by-importance.
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
    """Generate the new character's opening scene narration and architect blueprint.

    Reuses build_new_game_prompt — the successor is starting their own arc
    against the campaign's world, which is what new_game prompt produces.
    The narrator already sees the surviving NPCs in context (they are on
    game.npcs) and the world state (clocks empty, threads carry).
    """
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

    # If the successor opens with no on-screen NPCs and the surviving roster
    # is small, the parser may not extract anything new. Run opening_setup
    # only if needed — same gating as start_new_game.
    if not [n for n in game.npcs if n.introduced]:
        _ = call_opening_setup(provider, narration, game, config)
        # opening_setup data is intentionally not auto-applied here. The
        # surviving NPCs are already on the roster; auto-applying opening_setup
        # could create duplicates. The narration text is the canonical source
        # for who is on-screen; the parser-extracted NPCs handle that.

    return narration, val_report


def _record_succession_opening(
    game: GameState, narration: str, val_report: dict, predecessor: PredecessorRecord
) -> None:
    """Log the succession opening into narration history and session log."""
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


# Re-exports — mypy-friendly. Symbols imported but never referenced trip
# unused-import warnings; these are referenced via the public API.
__all__ = [
    "END_REASONS",
    "determine_end_reason",
    "prepare_succession",
    "start_succession_with_character",
]
