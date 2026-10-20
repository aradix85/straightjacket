from typing import Any

import pytest

from straightjacket.engine.gamemaster.config import gm
from tests._helpers import make_game_state


@pytest.mark.parametrize(
    ("stats", "error_match"),
    [
        ({"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 2}, "must take"),
        ({"edge": 4, "heart": 2, "iron": 2, "shadow": 1, "wits": 0}, "must take"),
        ({"edge": 3, "heart": 3, "iron": 1, "shadow": 1, "wits": 1}, "must take"),
        ({"edge": 3, "heart": 2, "iron": 1, "shadow": 1}, "must be edge"),
        ({"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1, "luck": 0}, "must be edge"),
    ],
)
def test_validate_stats_rejects_invalid(load_engine: None, stats: dict, error_match: str) -> None:
    from straightjacket.engine.ruleset.stats import validate_stats

    with pytest.raises(ValueError, match=error_match):
        validate_stats(stats, "starforged")


@pytest.mark.parametrize("setting_id", ["classic", "delve", "starforged", "sundered_isles"])
def test_every_setting_takes_its_stats_from_its_datasworn_rules(load_engine: None, setting_id: str) -> None:
    from straightjacket.engine.ruleset.stats import stat_descriptions, validate_stats

    assert list(stat_descriptions(setting_id)) == ["edge", "heart", "iron", "shadow", "wits"]
    validate_stats({"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1}, setting_id)


def test_an_expansion_takes_the_stats_of_its_ruleset(load_engine: None) -> None:
    from straightjacket.engine.ruleset.stats import stat_descriptions

    assert stat_descriptions("delve") == stat_descriptions("classic")
    assert stat_descriptions("sundered_isles") == stat_descriptions("starforged")
    assert stat_descriptions("classic")["edge"] != stat_descriptions("starforged")["edge"]


@pytest.mark.parametrize(
    ("vow", "expected"),
    [
        ("I must survive the siege at all costs", 7),
        ("I will find my lost sister", 6),
        ("I want to explore the uncharted regions", 4),
        ("I seek redemption", 5),
    ],
)
def test_a_new_game_starts_its_chaos_factor_from_the_vow(load_engine: None, vow: str, expected: int) -> None:
    from tests._creation import create_game

    game = create_game(
        "starforged", location="Drift Station", npcs=[], stats=(3, 2, 2, 1, 1), player_name="Kael", background_vow=vow
    )
    assert game.world.chaos_factor == expected


def test_swear_background_vow(load_engine: None) -> None:
    from straightjacket.engine.ruleset.tracks import swear_background_vow

    game = make_game_state(player_name="Test")
    swear_background_vow(game, "Find my sister", "extreme")
    assert len(game.progress_tracks) == 1
    assert game.progress_tracks[0].rank == "extreme"
    assert game.progress_tracks[0].name == "Find my sister"
    assert len(game.narrative.threads) == 1
    assert game.narrative.threads[0].linked_track_id == "vow_background"
    assert game.narrative.threads[0].weight == 2


def test_swear_background_vow_custom_rank(load_engine: None) -> None:
    from straightjacket.engine.ruleset.tracks import swear_background_vow

    game = make_game_state(player_name="Test")
    swear_background_vow(game, "Minor task", "troublesome")
    assert game.progress_tracks[0].rank == "troublesome"


def test_a_background_vow_without_a_rank_takes_the_default_rank(load_engine: None) -> None:
    from straightjacket.engine.ruleset.config import rules
    from straightjacket.engine.ruleset.tracks import swear_background_vow

    game = make_game_state(player_name="Test")
    swear_background_vow(game, "Quest", "")
    assert game.progress_tracks[0].rank == rules().creation.background_vow_default_rank


@pytest.mark.parametrize(
    ("setting", "expected_flags"),
    [
        (
            "starforged",
            {"has_truths": True, "has_backstory_oracle": True, "has_name_tables": True, "has_ship_creation": False},
        ),
        ("classic", {"has_truths": True, "has_backstory_oracle": False}),
        ("sundered_isles", {"has_ship_creation": True}),
    ],
)
def test_setting_creation_flow(setting: str, expected_flags: dict) -> None:
    from straightjacket.engine.setting.packages import load_package

    pkg = load_package(setting)
    flow = pkg.creation_flow
    for flag, expected in expected_flags.items():
        assert getattr(flow, flag) is expected


def test_build_creation_options_has_stat_constraints(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    assert opts["stat_constraints"] == {"target_sum": 9, "min": 1, "max": 3}
    assert all(s["stats"] == ["edge", "heart", "iron", "shadow", "wits"] for s in opts["settings"])


def test_build_creation_options_has_creation_defaults(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    cd = opts["creation_defaults"]
    assert cd["max_paths"] == 2
    assert cd["max_starting_assets"] == 1
    assert cd["pronoun_options"] == ["he/him", "she/her", "they/them"]
    assert cd["background_vow_default_rank"] == "extreme"
    assert "epic" in cd["vow_ranks"]


def test_build_creation_options_settings_have_truths(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["truths"]) > 0
    assert "options" in sf["truths"][0]


def test_build_creation_options_settings_have_backstory(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["backstory_prompts"]) > 0


def test_build_creation_options_settings_have_name_tables(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert list(sf["name_tables"])[:2] == ["given_name", "family_name"]
    assert len(sf["name_tables"]["given_name"]) > 0


def test_every_setting_offers_a_known_tone_as_its_default(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    tones = [tone["id"] for tone in opts["tones"]]
    assert tones == gm().story.tones
    assert all(tone["label"] != f"tone.{tone['id']}" for tone in opts["tones"])
    assert {s["id"]: s["default_tone"] for s in opts["settings"]} == {
        "classic": "dark_gritty",
        "starforged": "epic_heroic",
        "sundered_isles": "pulp",
    }


def test_build_creation_options_settings_have_starting_assets(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert len(sf["starting_assets"]) > 0
    cats = {a["category"] for a in sf["starting_assets"]}
    assert "companion" in cats


def test_build_creation_options_classic_no_backstory(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    cl = next(s for s in opts["settings"] if s["id"] == "classic")
    assert len(cl["backstory_prompts"]) == 0


def test_build_creation_options_sends_what_the_creation_form_reads(load_engine: None) -> None:
    from straightjacket.web.serializers import build_creation_options

    opts = build_creation_options()
    sf = next(s for s in opts["settings"] if s["id"] == "starforged")
    assert set(sf) == {
        "id",
        "title",
        "description",
        "paths",
        "truths",
        "name_tables",
        "backstory_prompts",
        "starting_assets",
        "default_tone",
        "stats",
    }
    assert set(sf["truths"][0]["options"][0]) == {"summary", "description"}


def test_truths_block_with_truths() -> None:
    from straightjacket.engine.prompt_blocks import truths_block

    game = make_game_state(player_name="Test", truths={"cataclysm": "The Sun Plague", "exodus": "We fled"})
    block = truths_block(game)
    assert "<world_truths>" in block
    assert "The Sun Plague" in block
    assert "We fled" in block


def test_truths_block_empty() -> None:
    from straightjacket.engine.prompt_blocks import truths_block

    game = make_game_state(player_name="Test")
    assert truths_block(game) == ""


_VALID_PAYLOAD = {"player_name": "Kael", "truths": {}, "tone": "pulp"}


@pytest.mark.parametrize(
    ("setting", "payload", "error_match"),
    [
        ("delve", {"truths": {"x": "y"}}, "does not support truths"),
        ("starforged", {"tone": "whimsical"}, "Unknown tone"),
        ("starforged", {"player_name": ""}, "player_name'\\] is empty"),
    ],
)
def test_validate_creation_rejects_invalid(load_engine: None, setting: str, payload: dict, error_match: str) -> None:
    from straightjacket.engine.game.game_start import validate_creation
    from straightjacket.engine.setting.packages import load_package

    pkg = load_package(setting)
    with pytest.raises(ValueError, match=error_match):
        validate_creation({**_VALID_PAYLOAD, **payload}, pkg)


def test_validate_creation_valid_passes(load_engine: None) -> None:
    from straightjacket.engine.game.game_start import validate_creation
    from straightjacket.engine.setting.packages import load_package

    validate_creation({**_VALID_PAYLOAD, "truths": {"x": "y"}, "tone": "cozy"}, load_package("starforged"))


_CHARACTER = {
    "stats": {"edge": 3, "heart": 2, "iron": 2, "shadow": 1, "wits": 1},
    "paths": [],
    "assets": [],
    "background_vow": "Find the lost ship",
    "background_vow_rank": "",
}


@pytest.mark.parametrize(
    ("setting", "payload", "error_match"),
    [
        ("starforged", {"paths": ["a", "b", "c"]}, "Too many paths"),
        ("starforged", {"paths": ["alchemist"]}, "not among the paths of"),
        ("starforged", {"assets": ["a", "b"]}, "Too many starting assets"),
        ("starforged", {"assets": ["ace"]}, "not in allowed categories"),
        ("delve", {"assets": ["ace"]}, "not in allowed categories"),
        ("starforged", {"background_vow_rank": "legendary"}, "Invalid vow rank"),
        ("starforged", {"background_vow": ""}, "background_vow'\\] is empty"),
        ("starforged", {"stats": {"edge": 3}}, "Stats must be"),
    ],
)
def test_make_character_rejects_invalid(load_engine: None, setting: str, payload: dict, error_match: str) -> None:
    from straightjacket.engine.ruleset.character import make_character
    from straightjacket.engine.setting.packages import load_package

    with pytest.raises(ValueError, match=error_match):
        make_character({**_CHARACTER, **payload}, load_package(setting))


def test_a_character_takes_its_concept_from_its_paths(load_engine: None) -> None:
    from straightjacket.engine.ruleset.character import make_character
    from straightjacket.engine.ruleset.datasworn import load_ruleset
    from straightjacket.engine.setting.packages import load_package

    pkg = load_package("starforged")
    character = make_character({**_CHARACTER, "paths": ["ace", "explorer"], "background_vow_rank": "epic"}, pkg)
    own = load_ruleset("starforged").setting_file
    names = [own.asset("path", pid)["name"] for pid in ("ace", "explorer")]
    assert character.concept == ", ".join(names)
    assert character.background_vow_rank == "epic"


def _take_up(vow_subject: str) -> Any:
    from straightjacket.engine.game.game_start import take_up_character
    from straightjacket.engine.ruleset.character import make_character
    from straightjacket.engine.setting.packages import load_package

    pkg = load_package("starforged")
    creation = {
        **_CHARACTER,
        **_VALID_PAYLOAD,
        "paths": ["ace"],
        "pronouns": "she/her",
        "backstory": "Raised on a derelict.",
        "wishes": "",
        "content_lines": "",
        "vow_subject": vow_subject,
    }
    game = make_game_state(player_name="Old")
    take_up_character(game, make_character(creation, pkg), creation, pkg)
    return game


def test_a_new_game_and_a_successor_take_up_a_character_alike(load_engine: None) -> None:
    game = _take_up("my sister")
    assert (game.player_name, game.setting_id, game.paths) == ("Kael", "starforged", ["ace"])
    assert game.stats == _CHARACTER["stats"]
    assert [t.id for t in game.progress_tracks] == ["vow_background"]
    assert [(c.name, c.entry_type, c.weight) for c in game.narrative.characters_list] == [
        ("my sister", "abstract", gm().random_events.seeded_list_weight)
    ]


def test_a_character_without_a_vow_subject_puts_no_one_on_the_characters_list(load_engine: None) -> None:
    assert _take_up("").narrative.characters_list == []


@pytest.mark.parametrize(
    ("move", "outcome", "disposition", "expected_fragment"),
    [
        ("combat/clash", "failure", "hostile", "fear_pain_hostile"),
        ("adventure/compel", "success", "friendly", "trusting_open_warm"),
        ("dialog", "dialog", "neutral", "neutral"),
        ("unknown_move", "failure", "neutral", "frustrated_setback"),
    ],
)
def test_derive_memory_emotion(
    load_engine: None, move: str, outcome: str, disposition: str, expected_fragment: str
) -> None:
    from straightjacket.engine.gamemaster.engine_memories import derive_memory_emotion

    assert expected_fragment in derive_memory_emotion(move, outcome, disposition)


def test_derive_memory_emotion_recovery_strong(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.engine_memories import derive_memory_emotion

    assert "devoted" in derive_memory_emotion("suffer/endure_harm", "success", "loyal")
