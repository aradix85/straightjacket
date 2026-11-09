from typing import Any

from straightjacket.engine.ai.metadata import process_deceased_npcs
from straightjacket.engine.ai.provider_base import AIProvider
from straightjacket.engine.director import new_guidance
from straightjacket.engine.game.setup_common import generate_opening, record_opening
from straightjacket.engine.gamemaster.clocks import start_opening_clock
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.random_events import add_character
from straightjacket.engine.gamemaster.world import new_world
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import GameState, NarrativeState, PlayerPreferences
from straightjacket.engine.prompt_boundary import build_new_game_prompt
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.ruleset.character import Character, give_character, make_character
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.legacy import new_campaign
from straightjacket.engine.ruleset.meters import starting_resources
from straightjacket.engine.setting.packages import SettingPackage, load_package


def validate_creation(creation_data: dict[str, Any], pkg: SettingPackage) -> None:
    if not creation_data["player_name"]:
        msg = "creation_data['player_name'] is empty."
        raise ValueError(msg)
    if creation_data["truths"] and not pkg.creation_flow.has_truths:
        msg = f"Setting '{pkg.id}' does not support truths"
        raise ValueError(msg)
    tone = creation_data["tone"]
    tones = gm().story.tones
    if tone not in tones:
        msg = f"Unknown tone '{tone}' (valid: {sorted(tones)})"
        raise ValueError(msg)


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
    game.preferences = PlayerPreferences(
        player_wishes=creation_data["wishes"], content_lines=creation_data["content_lines"]
    )
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
    add_character(game, "char_vow_subject", vow_subject, "abstract", gm().random_events.seeded_list_weight)
    log(f"[NewGame] Vow subject seeded in characters list: {vow_subject}")


def start_new_game(provider: AIProvider, creation_data: dict[str, Any]) -> tuple[GameState, str]:
    setting_id = creation_data["setting_id"]
    log(f"[NewGame] Starting: setting={setting_id}")
    pkg = load_package(setting_id)
    character = make_character(creation_data, pkg)

    game = GameState(
        player_name="",
        character_concept="",
        pronouns="",
        background_vow="",
        setting_id=pkg.id,
        setting_genre=pkg.id,
        setting_tone=creation_data["tone"],
        setting_description=pkg.description,
        stats={},
        backstory="",
        resources=starting_resources(setting_id),
        world=new_world(),
        narrative=NarrativeState(scene_count=1, story_blueprint=None, director_guidance=new_guidance()),
        campaign=new_campaign(setting_id),
        preferences=PlayerPreferences(player_wishes="", content_lines=""),
        crisis_mode=False,
        end_reason="",
        last_turn_snapshot=None,
        post_epilogue_director_done=False,
    )
    take_up_character(game, character, creation_data, pkg)

    game.world.chaos_factor = _compute_chaos_start(game.background_vow)

    game.world.time_of_day = gm().opening.time_of_day
    start_opening_clock(game)

    log(f"[NewGame] Character: {game.player_name}, paths={game.paths}, assets={game.assets}")

    narration, setup_data = generate_opening(provider, game, build_new_game_prompt, label="OpeningSetup")

    for npc in game.npcs:
        npc.introduced = True

    for npc in game.npcs:
        if npc.status == "active":
            add_character(game, npc.id, npc.name, "npc", 1)

    if setup_data["deceased_npcs"]:
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    record_opening(
        game,
        narration,
        history_summary=get_prompt("history_opening", player=game.player_name, location=game.world.current_location),
        log_summary=get_prompt("scene_log_game_start"),
    )

    return game, narration
