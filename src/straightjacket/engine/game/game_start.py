#!/usr/bin/env python3
"""Game start: character creation and opening scene generation."""


from ..ai import call_narrator, call_story_architect
from ..ai.narrator import call_opening_setup
from ..ai.provider_base import AIProvider
from ..config_loader import default_player_name
from ..engine_loader import eng
from ..logging_util import load_user_config, log, save_user_config
from ..mechanics import (
    choose_story_structure,
    record_scene_intensity,
)
from ..models import (
    EngineConfig,
    GameState,
    NarrationEntry,
    SceneLogEntry,
)
from ..parser import parse_narrator_response
from ..prompt_builders import build_new_game_prompt


def start_new_game(provider: AIProvider, creation_data: dict,
                   config: EngineConfig | None = None,
                   username: str = "") -> tuple[GameState, str]:
    """Create character from structured creation data, generate opening scene.

    creation_data keys:
        setting_id: str          — package ID (e.g. "starforged")
        player_name: str         — character name
        pronouns: str            — "he/him", "she/her", "they/them", or custom
        paths: list[str]         — 2 Datasworn path IDs
        backstory: str           — backstory text
        background_vow: str      — what drives this character
        stats: dict              — {edge, heart, iron, shadow, wits}
        wishes: str              — story wishes
        content_lines: str       — content exclusions
    """
    setting_id = creation_data.get("setting_id", "starforged")
    log(f"[NewGame] Starting: setting={setting_id}")

    from ..datasworn.loader import extract_title
    from ..datasworn.settings import active_package, load_package
    pkg = load_package(setting_id)

    stats = creation_data.get("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 1, "wits": 2})
    paths = creation_data.get("paths", [])

    # Build character concept from paths
    path_names = []
    for pid in paths:
        asset = pkg.data.asset("path", pid)
        if asset:
            path_names.append(extract_title(asset, pid))
    concept = ", ".join(path_names) if path_names else ""

    _e = eng()
    game = GameState(
        player_name=creation_data.get("player_name", default_player_name()),
        character_concept=concept,
        pronouns=creation_data.get("pronouns", ""),
        paths=paths,
        background_vow=creation_data.get("background_vow", ""),
        setting_id=setting_id,
        setting_genre=pkg.id,
        setting_tone="",
        setting_archetype="",
        setting_description=pkg.description,
        edge=stats.get("edge", 1), heart=stats.get("heart", 2),
        iron=stats.get("iron", 1), shadow=stats.get("shadow", 1),
        wits=stats.get("wits", 2),
        backstory=creation_data.get("backstory", ""),
    )
    game.resources.health = _e.resources.health_start
    game.resources.spirit = _e.resources.spirit_start
    game.resources.supply = _e.resources.supply_start
    game.resources.momentum = _e.momentum.start
    game.resources.max_momentum = _e.momentum.max
    game.narrative.scene_count = 1
    game.world.chaos_factor = _e.chaos.start
    game.preferences.player_wishes = creation_data.get("wishes", "")
    game.preferences.content_lines = creation_data.get("content_lines", "")
    log(f"[NewGame] Character: {game.player_name}, paths={paths}")

    if username:
        user_cfg = load_user_config(username)
        user_cfg["content_lines"] = game.preferences.content_lines
        save_user_config(username, user_cfg)

    structure = choose_story_structure(pkg.id)
    narrator_prompt = build_new_game_prompt(game)

    from concurrent.futures import ThreadPoolExecutor

    def _run_narrator():
        return call_narrator(provider, narrator_prompt, game, config)

    def _run_architect():
        return call_story_architect(provider, game, structure_type=structure, config=config)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(_run_narrator)
        fut_architect = pool.submit(_run_architect)
        raw = fut_narrator.result()
        blueprint = fut_architect.result()

    narration = parse_narrator_response(game, raw)

    from ..ai.validator import validate_and_retry, validate_architect
    narration, val_report = validate_and_retry(
        provider, narration, narrator_prompt, "opening", game, config=config)

    _pkg = active_package(game)
    _gc = None
    if _pkg:
        _g = _pkg.genre_constraints
        _gc = {"forbidden_terms": _g.forbidden_terms, "forbidden_concepts": _g.forbidden_concepts, "genre_test": _g.genre_test}

    from ..models import StoryBlueprint
    if blueprint is not None:
        blueprint = validate_architect(provider, blueprint, game.setting_genre, game.setting_tone, genre_constraints=_gc)
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

    # Deceased NPCs in the opening scene (e.g. dramatic opener with a death).
    # NPCs are extracted with full schema first, so data is preserved.
    # No scene_present_ids guard — everything in the opening is witnessed.
    if setup_data.get("deceased_npcs"):
        from ..ai.metadata import process_deceased_npcs
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    record_scene_intensity(game, "action")

    game.narrative.narration_history.append(NarrationEntry(
        prompt_summary=f"Opening scene: {game.player_name} in {game.world.current_location}",
        narration=narration,
    ))
    game.narrative.session_log.append(SceneLogEntry(
        scene=1, summary="Game start", result="opening", validator=val_report,
    ))
    return game, narration


def _apply_opening_setup(game: GameState, data: dict):
    """Apply structured opening setup data to game state."""
    from .setup_common import apply_world_setup, register_extracted_npcs, seed_opening_memories

    if data.get("npcs"):
        register_extracted_npcs(game, data["npcs"], label="OpeningSetup")
        log(f"[OpeningSetup] Registered {len(game.npcs)} NPCs: "
            f"{[n.name for n in game.npcs]}")

    if data.get("memory_updates"):
        seed_opening_memories(game, data["memory_updates"], label="opening_setup")

    apply_world_setup(game, data, clocks_mode="replace")

