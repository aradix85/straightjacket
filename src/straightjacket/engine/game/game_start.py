#!/usr/bin/env python3
"""Game start: character creation and opening scene generation."""

from ..ai.architect import call_story_architect
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..config_loader import default_player_name
from ..engine_loader import eng
from ..logging_util import log
from ..user_management import load_user_config, save_user_config
from ..mechanics import (
    choose_story_structure,
    record_scene_intensity,
)
from ..models import (
    CharacterListEntry,
    EngineConfig,
    GameState,
    NarrationEntry,
    ProgressTrack,
    SceneLogEntry,
    ThreadEntry,
)
from ..models_base import PROGRESS_RANKS
from ..parser import parse_narrator_response
from ..prompt_builders import build_new_game_prompt


def validate_stats(stats: dict[str, int]) -> None:
    """Validate stat distribution against engine.yaml constraints."""
    _e = eng()
    stat_names = [n for n in _e.stats.names if n != "none"]
    for name in stat_names:
        if name not in stats:
            raise ValueError(f"Missing stat: {name}")
    values = [stats[n] for n in stat_names]
    if sum(values) != _e.stats.target_sum:
        raise ValueError(f"Stats must total {_e.stats.target_sum}, got {sum(values)}")
    for name in stat_names:
        v = stats[name]
        if v < _e.stats.min or v > _e.stats.max:
            raise ValueError(f"Stat {name}={v} outside [{_e.stats.min}, {_e.stats.max}]")
    if sorted(values, reverse=True) not in [list(a) for a in _e.stats.valid_arrays]:
        raise ValueError(f"Invalid stat distribution: {sorted(values, reverse=True)}")


def validate_creation(creation_data: dict, pkg: object) -> None:
    """Validate creation data against engine.yaml and setting constraints."""
    _e = eng()
    from ..datasworn.settings import SettingPackage

    if not isinstance(pkg, SettingPackage):
        return
    flow = pkg.creation_flow

    # Path count
    paths = creation_data.get("paths", [])
    max_paths = _e.creation.max_paths
    if len(paths) > max_paths:
        raise ValueError(f"Too many paths: {len(paths)} (max {max_paths})")

    # Paths must exist in this setting
    for pid in paths:
        if not pkg.data.asset("path", pid):
            raise ValueError(f"Path '{pid}' not found in setting '{pkg.id}'")

    # Asset count and categories
    assets = creation_data.get("assets", [])
    max_assets = _e.creation.max_starting_assets
    if len(assets) > max_assets:
        raise ValueError(f"Too many starting assets: {len(assets)} (max {max_assets})")
    allowed_cats = set(flow.get("starting_asset_categories", []))
    if allowed_cats:
        for asset_id in assets:
            found = False
            for cat in allowed_cats:
                if pkg.data.asset(cat, asset_id):
                    found = True
                    break
            if not found:
                raise ValueError(f"Asset '{asset_id}' not in allowed categories: {allowed_cats}")

    # Truths: only allowed if setting has them
    truths = creation_data.get("truths", {})
    if truths and not flow.get("has_truths"):
        raise ValueError(f"Setting '{pkg.id}' does not support truths")

    # Background vow rank must be valid
    vow_rank = creation_data.get("background_vow_rank", "")
    if vow_rank and vow_rank not in PROGRESS_RANKS:
        raise ValueError(f"Invalid vow rank: '{vow_rank}' (valid: {list(PROGRESS_RANKS.keys())})")


def _compute_chaos_start(vow_text: str) -> int:
    """Derive starting chaos factor from background vow keywords."""
    _e = eng()
    base = _e.chaos.start
    if not vow_text:
        return base
    vow_lower = vow_text.lower()
    modifiers = _e.creation.chaos_vow_modifiers
    values = _e.creation.chaos_modifier_values
    for level in ("desperate", "tense", "calm"):
        keywords = modifiers.get(level, [])
        if any(kw in vow_lower for kw in keywords):
            adjustment = values.get(level, 0)
            result = max(_e.chaos.min, min(_e.chaos.max, base + adjustment))
            log(f"[NewGame] Chaos start {base}→{result} (vow keyword match: {level})")
            return result
    return base


def _seed_background_vow(game: GameState, vow_text: str, rank: str = "") -> None:
    """Create a ProgressTrack and ThreadEntry for the background vow."""
    if not vow_text:
        return
    _e = eng()
    vow_rank = rank if rank and rank in PROGRESS_RANKS else _e.creation.background_vow_default_rank
    track = ProgressTrack(
        id="vow_background",
        name=vow_text,
        track_type="vow",
        rank=vow_rank,
    )
    game.progress_tracks.append(track)
    game.narrative.threads.append(
        ThreadEntry(
            id="thread_background_vow",
            name=vow_text,
            thread_type="vow",
            weight=2,
            source="creation",
            linked_track_id="vow_background",
        )
    )
    log(f"[NewGame] Background vow track: rank={vow_rank}, thread seeded")


def _seed_truth_threads(game: GameState) -> None:
    """Derive initial tension threads from truth selections."""
    if not game.truths:
        return
    _e = eng()
    truth_map = _e.creation.truth_threads
    counter = 0
    for _truth_id, summary in game.truths.items():
        summary_lower = summary.lower()
        for pattern, thread_name in truth_map.items():
            if pattern.lower() in summary_lower:
                counter += 1
                game.narrative.threads.append(
                    ThreadEntry(
                        id=f"thread_truth_{counter}",
                        name=thread_name,
                        thread_type="tension",
                        weight=1,
                        source="creation",
                    )
                )
                log(f"[NewGame] Truth thread seeded: {thread_name}")
                break  # One thread per truth


def _seed_vow_subject(game: GameState, vow_subject: str) -> None:
    """Add the vow's implied subject to the Mythic characters list."""
    if not vow_subject:
        return
    game.narrative.characters_list.append(
        CharacterListEntry(
            id="char_vow_subject",
            name=vow_subject,
            entry_type="abstract",
            weight=2,
        )
    )
    log(f"[NewGame] Vow subject seeded in characters list: {vow_subject}")


def start_new_game(
    provider: AIProvider, creation_data: dict, config: EngineConfig | None = None, username: str = ""
) -> tuple[GameState, str]:
    """Create character from structured creation data, generate opening scene.

    creation_data keys:
        setting_id: str          — package ID (e.g. "starforged")
        player_name: str         — character name
        pronouns: str            — "he/him", "she/her", "they/them", or custom
        paths: list[str]         — 2 Datasworn path IDs
        backstory: str           — backstory text
        background_vow: str      — what drives this character
        background_vow_rank: str — vow rank (default from engine.yaml)
        vow_subject: str         — implied person/entity in the vow (for Mythic characters list)
        stats: dict              — {edge, heart, iron, shadow, wits}
        assets: list[str]        — additional asset IDs (non-path)
        truths: dict[str, str]   — {truth_id: chosen_summary}
        wishes: str              — story wishes
        content_lines: str       — content exclusions
    """
    setting_id = creation_data.get("setting_id", "starforged")
    log(f"[NewGame] Starting: setting={setting_id}")

    from ..datasworn.loader import extract_title
    from ..datasworn.settings import active_package, load_package

    pkg = load_package(setting_id)

    stats = creation_data.get("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    validate_stats(stats)
    validate_creation(creation_data, pkg)

    paths = creation_data.get("paths", [])

    # Build character concept from paths
    path_names = []
    for pid in paths:
        asset = pkg.data.asset("path", pid)
        if asset:
            path_names.append(extract_title(asset, pid))
    concept = ", ".join(path_names) if path_names else ""

    _e = eng()
    background_vow = creation_data.get("background_vow", "")

    game = GameState(
        player_name=creation_data.get("player_name", default_player_name()),
        character_concept=concept,
        pronouns=creation_data.get("pronouns", ""),
        paths=paths,
        background_vow=background_vow,
        setting_id=setting_id,
        setting_genre=pkg.id,
        setting_tone="",
        setting_archetype="",
        setting_description=pkg.description,
        edge=stats.get("edge", 1),
        heart=stats.get("heart", 2),
        iron=stats.get("iron", 1),
        shadow=stats.get("shadow", 1),
        wits=stats.get("wits", 2),
        backstory=creation_data.get("backstory", ""),
        assets=creation_data.get("assets", []),
        truths=creation_data.get("truths", {}),
    )
    game.resources.health = _e.resources.health_start
    game.resources.spirit = _e.resources.spirit_start
    game.resources.supply = _e.resources.supply_start
    game.resources.momentum = _e.momentum.start
    game.resources.max_momentum = _e.momentum.max
    game.narrative.scene_count = 1
    game.world.chaos_factor = _compute_chaos_start(background_vow)
    game.preferences.player_wishes = creation_data.get("wishes", "")
    game.preferences.content_lines = creation_data.get("content_lines", "")

    _seed_background_vow(game, background_vow, creation_data.get("background_vow_rank", ""))
    _seed_truth_threads(game)
    _seed_vow_subject(game, creation_data.get("vow_subject", ""))

    # Engine-determined opening state (no AI needed)
    _opening = _e.opening
    game.world.time_of_day = _opening.time_of_day
    from ..models import ClockData

    _trigger = _opening.clock_trigger_template.format(player=game.player_name)
    game.world.clocks.append(
        ClockData(
            name=game.background_vow or _opening.clock_fallback_name,
            clock_type="threat",
            segments=_opening.clock_segments,
            filled=_opening.clock_filled,
            trigger_description=_trigger,
            owner="",
        )
    )
    log(f"[NewGame] Engine-created opening clock and time_of_day={_opening.time_of_day}")

    log(f"[NewGame] Character: {game.player_name}, paths={paths}, assets={game.assets}")

    if username:
        user_cfg = load_user_config(username)
        user_cfg["content_lines"] = game.preferences.content_lines
        save_user_config(username, user_cfg)

    structure = choose_story_structure(pkg.id)
    narrator_prompt = build_new_game_prompt(game)

    from concurrent.futures import ThreadPoolExecutor

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

    from ..ai.validator import validate_and_retry, validate_architect

    narration, val_report = validate_and_retry(provider, narration, narrator_prompt, "opening", game, config=config)

    _pkg = active_package(game)
    _gc = None
    if _pkg:
        _g = _pkg.genre_constraints
        _gc = {
            "forbidden_terms": _g.forbidden_terms,
            "forbidden_concepts": _g.forbidden_concepts,
            "genre_test": _g.genre_test,
        }

    from ..models import StoryBlueprint

    if blueprint is not None:
        blueprint = validate_architect(
            provider, blueprint, game.setting_genre, game.setting_tone, genre_constraints=_gc
        )
        game.narrative.story_blueprint = StoryBlueprint.from_dict(blueprint)
    else:
        game.narrative.story_blueprint = None

    setup_data = {}
    if not game.npcs:
        setup_data = call_opening_setup(provider, narration, game, config)
        _apply_opening_setup(game, setup_data)

    # Opening-scene NPCs are extracted FROM the narration — introduced by definition
    for npc in game.npcs:
        npc.introduced = True

    # Seed Mythic characters list from opening NPCs
    for npc in game.npcs:
        if npc.status == "active":
            game.narrative.characters_list.append(
                CharacterListEntry(id=npc.id, name=npc.name, entry_type="npc", weight=1)
            )

    # Deceased NPCs in the opening scene (e.g. dramatic opener with a death).
    # NPCs are extracted with full schema first, so data is preserved.
    # No scene_present_ids guard — everything in the opening is witnessed.
    if setup_data.get("deceased_npcs"):
        from ..ai.metadata import process_deceased_npcs

        process_deceased_npcs(game, setup_data["deceased_npcs"])

    record_scene_intensity(game, "action")

    game.narrative.narration_history.append(
        NarrationEntry(
            prompt_summary=f"Opening scene: {game.player_name} in {game.world.current_location}",
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            summary="Game start",
            result="opening",
            validator=val_report,
        )
    )

    # Sync initial game state to database
    from ..db import sync as _db_sync

    _db_sync(game)

    return game, narration


def _apply_opening_setup(game: GameState, data: dict) -> None:
    """Apply structured opening setup data to game state."""
    from .setup_common import apply_world_setup, register_extracted_npcs, seed_opening_memories

    if data.get("npcs"):
        register_extracted_npcs(game, data["npcs"], label="OpeningSetup")
        log(f"[OpeningSetup] Registered {len(game.npcs)} NPCs: {[n.name for n in game.npcs]}")

    if data.get("memory_updates"):
        seed_opening_memories(game, data["memory_updates"], label="opening_setup")

    apply_world_setup(game, data, clocks_mode="replace")
