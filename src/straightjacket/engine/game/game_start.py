from concurrent.futures import ThreadPoolExecutor

from ..ai.architect import call_story_architect
from ..ai.metadata import process_deceased_npcs
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..datasworn.loader import extract_title
from ..datasworn.settings import SettingPackage, load_package
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
    return set(eng().progress.track_types["default"].ticks_per_mark.keys())


def validate_stats(stats: dict[str, int]) -> None:
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
    _e = eng()

    if not isinstance(pkg, SettingPackage):
        return
    flow = pkg.creation_flow

    paths = creation_data.get("paths", [])
    max_paths = _e.creation.max_paths
    if len(paths) > max_paths:
        raise ValueError(f"Too many paths: {len(paths)} (max {max_paths})")

    for pid in paths:
        if not pkg.data.asset("path", pid):
            raise ValueError(f"Path '{pid}' not found in setting '{pkg.id}'")

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

    truths = creation_data.get("truths", {})
    if truths and not flow.has_truths:
        raise ValueError(f"Setting '{pkg.id}' does not support truths")

    vow_rank = creation_data.get("background_vow_rank", "")
    valid = _valid_ranks()
    if vow_rank and vow_rank not in valid:
        raise ValueError(f"Invalid vow rank: '{vow_rank}' (valid: {sorted(valid)})")


def _compute_chaos_start(vow_text: str) -> int:
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
                break


def _seed_vow_subject(game: GameState, vow_subject: str) -> None:
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
    setting_id = creation_data["setting_id"]
    stats = creation_data["stats"]
    player_name = creation_data["player_name"]
    pronouns = creation_data["pronouns"]
    background_vow = creation_data["background_vow"]
    paths = list(creation_data["paths"])
    backstory = creation_data["backstory"]

    if not background_vow:
        raise ValueError("creation_data['background_vow'] is empty. Opening clock requires a background vow.")
    if not player_name:
        raise ValueError("creation_data['player_name'] is empty.")

    log(f"[NewGame] Starting: setting={setting_id}")
    pkg = load_package(setting_id)
    validate_stats(stats)
    validate_creation(creation_data, pkg)

    path_names = []
    for pid in paths:
        asset = pkg.data.asset("path", pid)
        if asset:
            path_names.append(extract_title(asset, pid))
    concept = ", ".join(path_names) if path_names else ""

    _e = eng()
    stat_names = [n for n in _e.stats.names if n != "none"]
    stat_dict = {n: stats[n] for n in stat_names}

    assets = list(creation_data.get("assets", []))
    truths = dict(creation_data.get("truths", {}))
    wishes = creation_data.get("wishes", "")
    content_lines = creation_data.get("content_lines", "")
    vow_subject = creation_data.get("vow_subject", "")
    background_vow_rank = creation_data.get("background_vow_rank", "")

    game = GameState(
        player_name=player_name,
        character_concept=concept,
        pronouns=pronouns,
        paths=paths,
        background_vow=background_vow,
        setting_id=setting_id,
        setting_genre=pkg.id,
        setting_tone="",
        setting_archetype="",
        setting_description=pkg.description,
        backstory=backstory,
        assets=assets,
        truths=truths,
        stats=stat_dict,
    )

    game.narrative.scene_count = 1
    game.world.chaos_factor = _compute_chaos_start(background_vow)
    game.preferences.player_wishes = wishes
    game.preferences.content_lines = content_lines

    _seed_background_vow(game, background_vow, background_vow_rank)
    _seed_truth_threads(game)
    _seed_vow_subject(game, vow_subject)

    _opening = _e.opening
    game.world.time_of_day = _opening.time_of_day

    _trigger = _opening.clock_trigger_template.format(player=game.player_name)
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

    if blueprint is not None:
        game.narrative.story_blueprint = StoryBlueprint.from_dict(blueprint)
    else:
        game.narrative.story_blueprint = None

    setup_data = {}
    if not game.npcs:
        setup_data = call_opening_setup(provider, narration, game, config)
        _apply_opening_setup(game, setup_data)

    for npc in game.npcs:
        npc.introduced = True

    for npc in game.npcs:
        if npc.status == "active":
            game.narrative.characters_list.append(
                CharacterListEntry(id=npc.id, name=npc.name, entry_type="npc", weight=1)
            )

    if setup_data.get("deceased_npcs"):
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    record_scene_intensity(game, "action")

    game.narrative.narration_history.append(
        NarrationEntry(
            scene=1,
            prompt_summary=f"Opening scene: {game.player_name} in {game.world.current_location}",
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary="Game start",
            result="opening",
        )
    )

    _db_sync(game)

    return game, narration


def _apply_opening_setup(game: GameState, data: dict) -> None:
    apply_opening_setup(game, data, clocks_mode="replace", label="OpeningSetup")
