"""Game start: character creation and opening scene generation."""

from concurrent.futures import ThreadPoolExecutor

from ..ai.architect import call_story_architect
from ..ai.architect_validator import validate_architect
from ..ai.metadata import process_deceased_npcs
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..ai.validator import validate_and_retry
from ..config_loader import default_player_name
from ..datasworn.loader import extract_title
from ..datasworn.settings import SettingPackage, active_package, load_package
from ..db import sync as _db_sync
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    choose_story_structure,
    record_scene_intensity,
)
from ..models import (
    CharacterListEntry,
    ClockData,
    EngineConfig,
    GameState,
    NarrationEntry,
    ProgressTrack,
    SceneLogEntry,
    StoryBlueprint,
    ThreadEntry,
)
from ..parser import parse_narrator_response
from ..prompt_boundary import build_new_game_prompt
from ..user_management import load_user_config, save_user_config

from .setup_common import apply_opening_setup


def _valid_ranks() -> set[str]:
    """Valid progress-track ranks from engine.yaml."""
    return set(eng().progress.track_types["default"].ticks_per_mark.keys())


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
    allowed_cats = set(flow.starting_asset_categories)
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
    if truths and not flow.has_truths:
        raise ValueError(f"Setting '{pkg.id}' does not support truths")

    # Background vow rank must be valid
    vow_rank = creation_data.get("background_vow_rank", "")
    valid = _valid_ranks()
    if vow_rank and vow_rank not in valid:
        raise ValueError(f"Invalid vow rank: '{vow_rank}' (valid: {sorted(valid)})")


def _compute_chaos_start(vow_text: str) -> int:
    """Derive starting chaos factor from background vow keywords."""
    _e = eng()
    base = _e.chaos.start
    if not vow_text:
        return base
    vow_lower = vow_text.lower()
    modifiers = _e.creation.chaos_vow_modifiers
    values = _e.creation.chaos_modifier_values
    for level, keywords in modifiers.items():
        if any(kw in vow_lower for kw in keywords):
            adjustment = values[level]
            result = max(_e.chaos.min, min(_e.chaos.max, base + adjustment))
            log(f"[NewGame] Chaos start {base}→{result} (vow keyword match: {level})")
            return result
    return base


def _seed_background_vow(game: GameState, vow_text: str, rank: str = "") -> None:
    """Create a ProgressTrack and ThreadEntry for the background vow."""
    if not vow_text:
        return
    _e = eng()
    if rank:
        if rank not in _valid_ranks():
            raise ValueError(f"Invalid vow rank: '{rank}' (valid: {sorted(_valid_ranks())})")
        vow_rank = rank
    else:
        vow_rank = _e.creation.background_vow_default_rank
    track = ProgressTrack.new(
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
    if "setting_id" not in creation_data:
        raise ValueError("creation_data missing required key 'setting_id'")
    setting_id = creation_data["setting_id"]
    log(f"[NewGame] Starting: setting={setting_id}")

    pkg = load_package(setting_id)

    if "stats" not in creation_data:
        raise ValueError("creation_data missing required key 'stats'")
    stats = creation_data["stats"]
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
    stat_names = [n for n in _e.stats.names if n != "none"]
    stat_dict = {n: stats[n] for n in stat_names}

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
        backstory=creation_data.get("backstory", ""),
        assets=creation_data.get("assets", []),
        truths=creation_data.get("truths", {}),
        stats=stat_dict,
    )
    # Resources seeded via Resources.from_config on GameState; chaos overridden here
    # with vow-keyword-modified start rather than the base config value.
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

    _trigger = _opening.clock_trigger_template.format(player=game.player_name)
    if not game.background_vow:
        raise ValueError(
            "Opening clock requires a background vow. "
            "Character creation must populate game.background_vow before calling new-game setup."
        )
    game.world.clocks.append(
        ClockData(
            name=game.background_vow,
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

    _pkg = active_package(game)
    _gc = _pkg.genre_constraints if _pkg else None

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

    _db_sync(game)

    return game, narration


def _apply_opening_setup(game: GameState, data: dict) -> None:
    """Apply structured opening setup data to game state."""

    apply_opening_setup(game, data, clocks_mode="replace", label="OpeningSetup")
