import json

from straightjacket.engine.models import GameState, ProgressTrack, ThreadEntry, ThreatData
from straightjacket.engine.models_story import ChapterSummary
from tests._helpers import (
    make_clock,
    make_game_state,
    make_memory,
    make_npc,
    make_progress_track,
    make_threat,
)
from tests._mocks import MockProvider


def _populated_game(load_engine: None) -> GameState:
    g = make_game_state(player_name="Aria", setting_id="starforged")
    g.world.current_location = "Drift Station"
    g.world.time_of_day = "evening"
    g.world.chaos_factor = 7
    g.world.clocks = [make_clock(name="Doom", clock_type="threat", segments=4, filled=2)]
    g.resources.health = 2
    g.resources.spirit = 3
    g.narrative.scene_count = 9
    g.crisis_mode = True
    g.game_over = True
    g.campaign.chapter_number = 2
    g.campaign.epilogue_shown = True
    g.campaign.epilogue_text = "End of last chapter."
    g.progress_tracks = [make_progress_track(id="v1", name="Old vow")]
    g.threats = [make_threat(id="t1", name="Old threat")]
    g.impacts = ["wounded"]
    g.assets = ["asset_a"]
    g.narrative.threads = [
        ThreadEntry(id="th1", name="Old thread", thread_type="vow", source="creation"),
    ]
    return g


def test_reset_chapter_mechanics_resets_resources(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.resources.health == eng().resources.health_start
    assert g.resources.spirit == eng().resources.spirit_start
    assert g.resources.supply == eng().resources.supply_start
    assert g.resources.momentum == eng().momentum.start


def test_reset_chapter_mechanics_clears_world_state(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.world.clocks == []
    assert g.world.time_of_day == ""
    assert g.world.location_history == []


def test_reset_chapter_mechanics_clears_narrative(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.narrative.scene_count == 1
    assert g.narrative.session_log == []
    assert g.narrative.narration_history == []
    assert g.narrative.story_blueprint is None


def test_reset_chapter_mechanics_clears_flags(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.crisis_mode is False
    assert g.game_over is False
    assert g.campaign.epilogue_shown is False
    assert g.campaign.epilogue_text == ""


def test_reset_chapter_mechanics_clears_collections(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.progress_tracks == []
    assert g.threats == []
    assert g.impacts == []
    assert g.assets == []
    assert g.narrative.threads == []


def _make_chapter_summary(load_engine: None) -> ChapterSummary:
    return ChapterSummary(
        chapter=1,
        title="Ch 1",
        summary="Things happened",
        unresolved_threads=["the relic"],
        character_growth="grew",
        npc_evolutions=[],
        thematic_question="?",
        post_story_location="Tavern",
        scenes=5,
        progress_tracks=[ProgressTrack(id="v1", name="Vow", track_type="vow", rank="dangerous", max_ticks=40, ticks=8)],
        threats=[
            ThreatData(
                id="t1",
                name="Threat",
                category="rampaging_creature",
                linked_vow_id="",
                rank="dangerous",
                max_menace_ticks=40,
                description="",
            )
        ],
        impacts=["wounded"],
        assets=["asset_a"],
        threads=[ThreadEntry(id="th1", name="Thread", thread_type="vow", source="creation")],
    )


def test_restore_chapter_mechanics_restores_collections(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _restore_chapter_mechanics

    g = make_game_state(player_name="X", setting_id="starforged")
    summary = _make_chapter_summary(None)
    _restore_chapter_mechanics(g, summary)
    assert len(g.progress_tracks) == 1
    assert g.progress_tracks[0].id == "v1"
    assert len(g.threats) == 1
    assert g.threats[0].id == "t1"
    assert g.impacts == ["wounded"]
    assert g.assets == ["asset_a"]
    assert len(g.narrative.threads) == 1


def test_prepare_npcs_keeps_active_with_agenda(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _prepare_npcs_for_new_chapter

    g = make_game_state(player_name="X", setting_id="starforged")
    g.npcs = [
        make_npc(id="npc_1", name="Major", status="active", agenda="serious goal"),
    ]
    _prepare_npcs_for_new_chapter(g)
    assert g.npcs[0].status == "active"


def test_prepare_npcs_retires_filler_to_background(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _prepare_npcs_for_new_chapter

    g = make_game_state(player_name="X", setting_id="starforged")
    g.npcs = [
        make_npc(id="npc_1", name="Filler", status="active", agenda="", memory=[]),
    ]
    _prepare_npcs_for_new_chapter(g)
    assert g.npcs[0].status == "background"


def test_prepare_npcs_skips_deceased(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _prepare_npcs_for_new_chapter

    g = make_game_state(player_name="X", setting_id="starforged")
    g.npcs = [make_npc(id="npc_1", name="Dead", status="deceased")]
    _prepare_npcs_for_new_chapter(g)
    assert g.npcs[0].status == "deceased"


def test_prepare_npcs_caps_memory_at_open_threads_max(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.game.chapters import _prepare_npcs_for_new_chapter

    g = make_game_state(player_name="X", setting_id="starforged")
    cap = eng().chapter.open_threads_max
    npc = make_npc(id="npc_1", name="Major", status="active", agenda="something")
    npc.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=5) for i in range(cap + 5)]
    g.npcs = [npc]
    _prepare_npcs_for_new_chapter(g)
    assert len(g.npcs[0].memory) <= cap


def test_merge_returning_npcs_appends_unique(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _merge_returning_npcs

    g = make_game_state(player_name="X", setting_id="starforged")
    g.npcs = [make_npc(id="npc_2", name="New One", status="active")]
    returning = [make_npc(id="npc_1_old", name="Returning", status="active")]
    _merge_returning_npcs(g, returning)
    names = {n.name for n in g.npcs}
    assert "Returning" in names
    assert "New One" in names


def test_merge_returning_npcs_skips_duplicates(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _merge_returning_npcs

    g = make_game_state(player_name="X", setting_id="starforged")
    g.npcs = [make_npc(id="npc_2", name="Kira", status="active")]
    returning = [make_npc(id="npc_1_old", name="kira", status="active")]
    _merge_returning_npcs(g, returning)
    assert len([n for n in g.npcs if n.name.lower() == "kira"]) == 1


def test_merge_returning_npcs_remaps_memory_about_npc(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _merge_returning_npcs

    g = make_game_state(player_name="X", setting_id="starforged")
    new_npc = make_npc(
        id="npc_2",
        name="New",
        status="active",
        memory=[make_memory(scene=1, event="X", type="observation", importance=3, about_npc="npc_1_old")],
    )
    g.npcs = [new_npc]
    returning = [make_npc(id="npc_1_old", name="Returning", status="active")]
    _merge_returning_npcs(g, returning)
    remapped_id = next(n.id for n in g.npcs if n.name == "Returning")
    assert g.npcs[0].memory[0].about_npc == remapped_id


def test_merge_returning_npcs_seeds_location_history(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _merge_returning_npcs

    g = make_game_state(player_name="X", setting_id="starforged")
    g.world.current_location = "Tavern"
    g.world.location_history = []
    _merge_returning_npcs(g, [])
    assert "Tavern" in g.world.location_history


def test_apply_blueprint_with_blueprint_dict(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _apply_blueprint

    g = make_game_state(player_name="X", setting_id="starforged")
    provider = MockProvider(json.dumps({"pass": True, "violations": [], "fixed_conflict": "", "fixed_antagonist": ""}))
    blueprint = {
        "central_conflict": "Find the relic",
        "antagonist_force": "The cult",
        "thematic_thread": "trust",
        "structure_type": "3act",
        "acts": [],
        "revelations": [],
        "possible_endings": [],
        "revealed": [],
        "triggered_transitions": [],
        "story_complete": False,
    }
    _apply_blueprint(g, provider, blueprint)
    assert g.narrative.story_blueprint is not None
    assert g.narrative.story_blueprint.central_conflict == "Find the relic"


def test_apply_blueprint_with_none_clears(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _apply_blueprint
    from straightjacket.engine.models_story import StoryBlueprint

    g = make_game_state(player_name="X", setting_id="starforged")
    g.narrative.story_blueprint = StoryBlueprint(central_conflict="old")
    provider = MockProvider("")
    _apply_blueprint(g, provider, None)
    assert g.narrative.story_blueprint is None


def test_record_chapter_opening_appends_log(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _record_chapter_opening

    g = make_game_state(player_name="Aria", setting_id="starforged")
    g.world.current_location = "Tavern"
    g.campaign.chapter_number = 2
    _record_chapter_opening(g, "Opening narration")
    assert len(g.narrative.narration_history) == 1
    assert g.narrative.narration_history[0].narration == "Opening narration"
    assert len(g.narrative.session_log) == 1
    assert g.narrative.session_log[0].result == "opening"


def test_close_previous_chapter_archives_and_advances(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import _close_previous_chapter

    fake_summary = {
        "title": "Chapter 1",
        "summary": "Things happened",
        "unresolved_threads": ["thread1"],
        "character_growth": "grew",
        "npc_evolutions": [{"name": "Kira", "projection": "wary"}],
        "thematic_question": "?",
        "post_story_location": "New Place",
    }
    provider = MockProvider(json.dumps(fake_summary))
    g = make_game_state(player_name="X", setting_id="starforged")
    g.campaign.chapter_number = 1
    g.narrative.scene_count = 5

    summary = _close_previous_chapter(provider, g, None)

    assert summary.title == "Chapter 1"
    assert g.campaign.chapter_number == 2
    assert g.world.current_location == "New Place"
    assert len(g.campaign.campaign_history) == 1


def test_generate_epilogue_returns_narration(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("The journey ended quietly.")
    g = make_game_state(player_name="Aria", setting_id="starforged")
    g.world.current_location = "Tavern"
    _, narration = generate_epilogue(provider, g)
    assert "ended quietly" in narration
    assert g.campaign.epilogue_shown is True
    assert g.campaign.epilogue_text == narration


def test_generate_epilogue_strips_epilogue_header(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("# Epilogue\n\nThe story ends here.")
    g = make_game_state(player_name="Aria", setting_id="starforged")
    _, narration = generate_epilogue(provider, g)
    assert "Epilogue" not in narration.split("\n")[0]


def test_generate_epilogue_fallback_on_empty(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("")
    g = make_game_state(player_name="Aria", setting_id="starforged")
    _, narration = generate_epilogue(provider, g)
    assert narration != ""


def test_apply_chapter_opening_setup_routes_to_apply(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import _apply_chapter_opening_setup

    g = make_game_state(player_name="X", setting_id="starforged")
    g.world.current_location = "Tavern"
    data = {
        "clocks": [],
        "location": "Tavern",
        "scene_context": "Quiet morning",
        "time_of_day": "morning",
    }
    _apply_chapter_opening_setup(g, data, returning_npcs=[])
    assert g.world.current_scene_context == "Quiet morning"
