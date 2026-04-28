import json

from straightjacket.engine.models import SceneLogEntry
from straightjacket.engine.models_story import ChapterSummary, StoryAct, StoryBlueprint
from tests._helpers import make_game_state, make_npc
from tests._mocks import MockProvider


def _full_game(load_engine: None) -> object:
    g = make_game_state(
        player_name="Aria",
        character_concept="exiled archivist",
        setting_genre="dark_fantasy",
        setting_tone="serious",
        setting_description="A grim world.",
        backstory="She fled the temple.",
    )
    g.world.current_location = "Tavern"
    g.world.current_scene_context = "Quiet morning."
    return g


def test_clean_act_moods_strips_forbidden(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _clean_act_moods
    from straightjacket.engine.engine_loader import eng

    forbidden = next(iter(eng().architect.forbidden_moods))
    blueprint = {
        "acts": [
            {"phase": "setup", "mood": f"{forbidden}, hopeful"},
        ]
    }
    _clean_act_moods(blueprint)
    assert forbidden not in blueprint["acts"][0]["mood"]
    assert "hopeful" in blueprint["acts"][0]["mood"]


def test_clean_act_moods_uses_fallback_when_all_forbidden(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _clean_act_moods
    from straightjacket.engine.engine_loader import eng

    forbidden_list = list(eng().architect.forbidden_moods)
    if len(forbidden_list) < 2:
        return
    blueprint = {"acts": [{"phase": "setup", "mood": f"{forbidden_list[0]}, {forbidden_list[1]}"}]}
    _clean_act_moods(blueprint)
    assert blueprint["acts"][0]["mood"] != ""


def test_clean_act_moods_skips_clean_mood(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _clean_act_moods

    original = "tense, hopeful"
    blueprint = {"acts": [{"phase": "setup", "mood": original}]}
    _clean_act_moods(blueprint)
    assert blueprint["acts"][0]["mood"] == original


def test_clean_act_moods_skips_empty_mood(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _clean_act_moods

    blueprint = {"acts": [{"phase": "setup", "mood": ""}]}
    _clean_act_moods(blueprint)
    assert blueprint["acts"][0]["mood"] == ""


def test_validate_scene_ranges_replaces_invalid(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _validate_scene_ranges
    from straightjacket.engine.engine_loader import eng

    default = list(eng().scene_range_default)
    blueprint = {
        "acts": [
            {"phase": "setup", "scene_range": "not a list"},
            {"phase": "rising", "scene_range": [1]},
            {"phase": "climax", "scene_range": [1, 5, 10]},
        ]
    }
    _validate_scene_ranges(blueprint)
    for act in blueprint["acts"]:
        assert act["scene_range"] == default


def test_validate_scene_ranges_keeps_valid(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _validate_scene_ranges

    blueprint = {"acts": [{"phase": "setup", "scene_range": [1, 5]}]}
    _validate_scene_ranges(blueprint)
    assert blueprint["acts"][0]["scene_range"] == [1, 5]


def test_build_architect_user_msg_basic(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _build_architect_user_msg

    g = _full_game(None)
    msg = _build_architect_user_msg(g)
    assert "Aria" in msg
    assert "exiled archivist" in msg
    assert "dark_fantasy" in msg
    assert "Tavern" in msg
    assert "She fled the temple" in msg


def test_build_architect_user_msg_no_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _build_architect_user_msg
    from straightjacket.engine.engine_loader import eng

    g = _full_game(None)
    g.npcs = []
    msg = _build_architect_user_msg(g)
    no_npcs_label = eng().ai_text.narrator_defaults["no_npcs_yet"]
    assert no_npcs_label in msg


def test_build_architect_user_msg_with_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _build_architect_user_msg

    g = _full_game(None)
    g.npcs = [make_npc(id="npc_1", name="Kira"), make_npc(id="npc_2", name="Borin")]
    msg = _build_architect_user_msg(g)
    assert "Kira" in msg
    assert "Borin" in msg


def test_build_architect_user_msg_includes_campaign(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _build_architect_user_msg

    g = _full_game(None)
    g.campaign.chapter_number = 2
    g.campaign.campaign_history = [
        ChapterSummary(
            chapter=1,
            title="Ch 1",
            summary="The fall of the temple",
            unresolved_threads=["the relic"],
            character_growth="grew wary",
            npc_evolutions=[],
            thematic_question="trust?",
            post_story_location="Tavern",
            scenes=5,
            progress_tracks=[],
            threats=[],
            impacts=[],
            assets=[],
            threads=[],
        )
    ]
    msg = _build_architect_user_msg(g)
    assert "campaign_chapter:2" in msg
    assert "fall of the temple" in msg
    assert "the relic" in msg
    assert "grew wary" in msg
    assert "trust?" in msg


def test_build_architect_user_msg_no_backstory(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import _build_architect_user_msg

    g = _full_game(None)
    g.backstory = ""
    msg = _build_architect_user_msg(g)
    assert "backstory(canon past):" not in msg


def test_call_recap_returns_content(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_recap

    provider = MockProvider("Last time, Aria fled.")
    g = _full_game(None)
    result = call_recap(provider, g)
    assert result == "Last time, Aria fled."


def test_call_recap_falls_back_on_api_error(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_recap
    from straightjacket.engine.engine_loader import eng

    provider = MockProvider(fail=True)
    g = _full_game(None)
    result = call_recap(provider, g)
    fallback = eng().ai_text.narrator_defaults["recap_fallback"].format(player_name=g.player_name)
    assert result == fallback


def test_call_recap_with_arc(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_recap

    provider = MockProvider("recap text")
    g = _full_game(None)
    g.narrative.story_blueprint = StoryBlueprint(
        central_conflict="x",
        acts=[StoryAct(phase="setup", title="Act 1", scene_range=[1, 5])],
    )
    g.narrative.scene_count = 3
    result = call_recap(provider, g)
    assert result == "recap text"


def test_call_recap_with_active_npcs(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_recap

    provider = MockProvider("recap")
    g = _full_game(None)
    g.npcs = [
        make_npc(id="npc_1", name="Kira", disposition="friendly", status="active", introduced=True),
    ]
    result = call_recap(provider, g)
    assert result == "recap"


def test_call_recap_with_session_log(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_recap

    provider = MockProvider("recap")
    g = _full_game(None)
    g.narrative.session_log = [
        SceneLogEntry(scene=1, summary="Met Kira", result="STRONG_HIT", scene_type="expected"),
    ]
    assert call_recap(provider, g) == "recap"


def test_call_story_architect_returns_blueprint_dict(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_story_architect

    fake_blueprint = {
        "central_conflict": "Find the relic",
        "antagonist_force": "The cult",
        "thematic_thread": "trust",
        "acts": [
            {"phase": "setup", "title": "Act 1", "goal": "g", "mood": "tense", "scene_range": [1, 5]},
            {"phase": "climax", "title": "Act 2", "goal": "g", "mood": "rising", "scene_range": [6, 10]},
        ],
        "revelations": [],
        "possible_endings": [],
    }
    provider = MockProvider(json.dumps(fake_blueprint))
    g = _full_game(None)
    result = call_story_architect(provider, g)
    assert result is not None
    assert result["central_conflict"] == "Find the relic"
    assert result["story_complete"] is False
    assert result["revealed"] == []
    assert result["triggered_transitions"] == []
    assert result["structure_type"] == "3act"


def test_call_story_architect_kishotenketsu_structure(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_story_architect

    fake_blueprint = {
        "central_conflict": "x",
        "antagonist_force": "y",
        "thematic_thread": "z",
        "acts": [],
        "revelations": [],
        "possible_endings": [],
    }
    provider = MockProvider(json.dumps(fake_blueprint))
    g = _full_game(None)
    result = call_story_architect(provider, g, structure_type="kishotenketsu")
    assert result["structure_type"] == "kishotenketsu"


def test_call_story_architect_returns_none_on_api_error(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_story_architect

    provider = MockProvider(fail=True)
    g = _full_game(None)
    assert call_story_architect(provider, g) is None


def test_call_story_architect_returns_none_on_invalid_json(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_story_architect

    provider = MockProvider("this is not json")
    g = _full_game(None)
    assert call_story_architect(provider, g) is None


def test_call_chapter_summary_returns_parsed_json(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_chapter_summary

    fake_summary = {
        "title": "Chapter Title",
        "summary": "What happened",
        "unresolved_threads": ["thread1"],
        "character_growth": "grew",
        "npc_evolutions": [],
        "thematic_question": "?",
        "post_story_location": "Tavern",
    }
    provider = MockProvider(json.dumps(fake_summary))
    g = _full_game(None)
    result = call_chapter_summary(provider, g)
    assert result["title"] == "Chapter Title"


def test_call_chapter_summary_falls_back_on_api_error(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_chapter_summary

    provider = MockProvider(fail=True)
    g = _full_game(None)
    g.campaign.chapter_number = 3
    result = call_chapter_summary(provider, g)
    assert "title" in result
    assert "summary" in result
    assert "unresolved_threads" in result


def test_call_chapter_summary_with_blueprint(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_chapter_summary

    fake_summary = {
        "title": "T",
        "summary": "S",
        "unresolved_threads": [],
        "character_growth": "",
        "npc_evolutions": [],
        "thematic_question": "?",
        "post_story_location": "X",
    }
    provider = MockProvider(json.dumps(fake_summary))
    g = _full_game(None)
    g.narrative.story_blueprint = StoryBlueprint(central_conflict="The conflict")
    result = call_chapter_summary(provider, g)
    assert result["title"] == "T"


def test_call_chapter_summary_with_epilogue(load_engine: None) -> None:
    from straightjacket.engine.ai.architect import call_chapter_summary

    fake_summary = {
        "title": "T",
        "summary": "S",
        "unresolved_threads": [],
        "character_growth": "",
        "npc_evolutions": [],
        "thematic_question": "?",
        "post_story_location": "X",
    }
    provider = MockProvider(json.dumps(fake_summary))
    g = _full_game(None)
    result = call_chapter_summary(provider, g, epilogue_text="The end was bittersweet.")
    assert result["title"] == "T"
