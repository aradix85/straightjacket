import random as _random_module
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..ai.blueprint_voicing import call_blueprint_voicing
from ..ai.metadata import process_deceased_npcs
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..crafters.blueprint import (
    assemble_blueprint_seed_from_ac,
    assemble_blueprint_seed_kishotenketsu,
    materialize_blueprint,
)
from ..gamemaster.clocks import start_opening_clock
from ..gamemaster.config import gm
from ..gamemaster.pacing import record_scene_intensity
from ..gamemaster.story import choose_story_structure
from ..gamemaster.world import new_world
from ..logging_util import log
from ..models import (
    CharacterListEntry,
    GameState,
    NarrationEntry,
    SceneLogEntry,
)
from ..parser import parse_narrator_response
from ..prompt_boundary import build_new_game_prompt
from ..prompt_loader import get_prompt
from ..ruleset.character import Character, give_character, make_character
from ..ruleset.config import rules
from ..ruleset.legacy import new_campaign
from ..ruleset.meters import starting_resources
from ..setting.packages import SettingPackage, load_package
from .setup_common import apply_opening_setup


def validate_creation(creation_data: dict[str, Any], pkg: SettingPackage) -> None:
    if not creation_data["player_name"]:
        raise ValueError("creation_data['player_name'] is empty.")
    if creation_data["truths"] and not pkg.creation_flow.has_truths:
        raise ValueError(f"Setting '{pkg.id}' does not support truths")
    tone = creation_data["tone"]
    tones = gm().story.kishotenketsu_probability
    if tone not in tones:
        raise ValueError(f"Unknown tone '{tone}' (valid: {sorted(tones)})")


def take_up_character(
    game: GameState, character: Character, creation_data: dict[str, Any], pkg: SettingPackage
) -> None:
    validate_creation(creation_data, pkg)
    game.player_name = creation_data["player_name"]
    game.pronouns = creation_data["pronouns"]
    game.backstory = creation_data["backstory"]
    game.setting_id = pkg.id
    game.setting_genre = pkg.id
    game.truths = dict(creation_data["truths"])
    game.preferences.player_wishes = creation_data["wishes"]
    game.preferences.content_lines = creation_data["content_lines"]
    give_character(game, character)
    _seed_vow_subject(game, creation_data["vow_subject"])


def _compute_chaos_start(vow_text: str) -> int:
    base = gm().chaos.start
    vow_lower = vow_text.lower()
    modifiers = rules().creation.chaos_vow_modifiers
    values = rules().creation.chaos_modifier_values
    for level, keywords in modifiers.items():
        if any(kw in vow_lower for kw in keywords):
            adjustment = values[level]
            result = max(gm().chaos.min, min(gm().chaos.max, base + adjustment))
            log(f"[NewGame] Chaos start {base}→{result} (vow keyword match: {level})")
            return result
    return base


def _seed_vow_subject(game: GameState, vow_subject: str) -> None:
    if not vow_subject:
        return
    game.narrative.characters_list.append(
        CharacterListEntry(
            id="char_vow_subject",
            name=vow_subject,
            entry_type="abstract",
            weight=gm().random_events.seeded_list_weight,
        )
    )
    log(f"[NewGame] Vow subject seeded in characters list: {vow_subject}")


def start_new_game(provider: AIProvider, creation_data: dict[str, Any]) -> tuple[GameState, str]:
    setting_id = creation_data["setting_id"]
    log(f"[NewGame] Starting: setting={setting_id}")
    pkg = load_package(setting_id)
    character = make_character(creation_data, pkg)

    game = GameState(
        setting_tone=creation_data["tone"],
        setting_description=pkg.description,
        stats=character.stats,
        resources=starting_resources(setting_id),
        world=new_world(),
        campaign=new_campaign(setting_id),
    )
    take_up_character(game, character, creation_data, pkg)

    game.narrative.scene_count = 1
    game.world.chaos_factor = _compute_chaos_start(game.background_vow)

    game.world.time_of_day = gm().opening.time_of_day
    start_opening_clock(game)

    log(f"[NewGame] Character: {game.player_name}, paths={game.paths}, assets={game.assets}")

    structure = choose_story_structure(game.setting_tone)
    rng = _random_module.Random()
    if structure == "kishotenketsu":
        seed = assemble_blueprint_seed_kishotenketsu(rng, game)
    else:
        seed = assemble_blueprint_seed_from_ac(rng, game)
    log(f"[NewGame] Blueprint seed assembled: structure={seed.structure_type}, themes={seed.themes}")

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

    if voicing is not None:
        game.narrative.story_blueprint = materialize_blueprint(seed, voicing)
    else:
        game.narrative.story_blueprint = None

    setup_data = call_opening_setup(provider, narration, game)
    apply_opening_setup(game, setup_data, label="OpeningSetup")

    for npc in game.npcs:
        npc.introduced = True

    for npc in game.npcs:
        if npc.status == "active":
            game.narrative.characters_list.append(
                CharacterListEntry(id=npc.id, name=npc.name, entry_type="npc", weight=1)
            )

    if setup_data["deceased_npcs"]:
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    record_scene_intensity(game, "action")

    game.narrative.narration_history.append(
        NarrationEntry(
            scene=1,
            prompt_summary=get_prompt("history_opening", player=game.player_name, location=game.world.current_location),
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary=get_prompt("scene_log_game_start"),
            result="opening",
        )
    )

    return game, narration
