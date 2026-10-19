import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import GameState, ThreadEntry
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
    g.resources.meters["health"] = 2
    g.resources.meters["spirit"] = 3
    g.narrative.scene_count = 9
    g.crisis_mode = True
    g.end_reason = "death"
    g.campaign.chapter_number = 2
    g.campaign.epilogue_dismissed = True
    g.progress_tracks = [make_progress_track(id="v1", name="Old vow")]
    g.threats = [make_threat(id="t1", name="Old threat")]
    g.impacts = ["wounded"]
    g.assets = ["asset_a"]
    g.narrative.threads = [
        ThreadEntry(id="th1", name="Old thread", thread_type="vow", source="creation"),
    ]
    return g


def test_a_new_chapter_keeps_the_character_and_the_clocks(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics
    from tests._helpers import make_clock

    g = _populated_game(None)
    (
        g.resources.meters["health"],
        g.resources.meters["spirit"],
        g.resources.meters["supply"],
        g.resources.meters["momentum"],
    ) = 2, 3, 1, 7
    g.world.clocks = [make_clock(name="The flood rises")]
    clocks = [c.to_dict() for c in g.world.clocks]
    _reset_chapter_mechanics(g)
    assert (
        g.resources.meters["health"],
        g.resources.meters["spirit"],
        g.resources.meters["supply"],
        g.resources.meters["momentum"],
    ) == (2, 3, 1, 7)
    assert [c.to_dict() for c in g.world.clocks] == clocks


def test_a_created_game_moves_into_its_next_chapter(load_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.game.chapters import start_new_chapter
    from tests._creation import OPENING_TEXT, OpeningProvider, create_game
    from tests.elvira.elvira_bot.invariants import assert_game_state

    game = create_game(
        "starforged",
        location="Drift Station",
        npcs=[("Kira Vance", "A pilot with a burned hand.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="Keep the station running",
    )
    game.npcs[0].agenda = "keep her ship"
    provider = OpeningProvider(
        [("Kira", "A pilot.", "friendly"), ("Dace Orrin", "A dockhand.", "neutral")], "Ring Dock"
    )

    narration = start_new_chapter(provider, game)

    assert narration == OPENING_TEXT
    assert game.campaign.chapter_number == 2
    assert game.narrative.scene_count == 1
    assert game.world.current_location == "Ring Dock"
    assert game.narrative.story_blueprint is not None
    assert sorted(n.name for n in game.npcs) == ["Dace Orrin", "Kira Vance"]
    assert [t.id for t in game.progress_tracks] == ["vow_background"]
    assert assert_game_state(game, turn=1) == []


def test_a_game_that_is_over_cannot_start_a_chapter(load_engine: None) -> None:
    import pytest

    from straightjacket.engine.game.chapters import start_new_chapter
    from tests._mocks import MockProvider

    g = _populated_game(None)
    g.end_reason = "death"
    with pytest.raises(RuntimeError, match="succession"):
        start_new_chapter(MockProvider(), g)


def test_reset_chapter_mechanics_clears_world_state(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.world.chaos_factor == gm().chaos.start
    assert g.world.time_of_day == gm().opening.time_of_day
    assert g.world.location_history == []


def test_reset_chapter_mechanics_clears_narrative(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    g.last_turn_snapshot = g.snapshot()
    _reset_chapter_mechanics(g)
    assert g.narrative.scene_count == 1
    assert g.narrative.session_log == []
    assert g.narrative.narration_history == []
    assert g.narrative.story_blueprint is None
    assert g.last_turn_snapshot is None


def test_reset_chapter_mechanics_clears_flags(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert g.campaign.epilogue_dismissed is False


def test_reset_chapter_mechanics_keeps_what_carries_over(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import _reset_chapter_mechanics

    g = _populated_game(None)
    _reset_chapter_mechanics(g)
    assert [t.id for t in g.progress_tracks] == ["v1"]
    assert [t.id for t in g.threats] == ["t1"]
    assert g.impacts == ["wounded"]
    assert g.assets == ["asset_a"]
    assert [t.id for t in g.narrative.threads] == ["th1"]


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
    from straightjacket.engine.game.chapters import _prepare_npcs_for_new_chapter

    g = make_game_state(player_name="X", setting_id="starforged")
    cap = gm().chapter.open_threads_max
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


def test_apply_blueprint_with_voicing_materializes(load_engine: None) -> None:
    import random

    from straightjacket.engine.crafters.blueprint import assemble_blueprint_seed_from_ac
    from straightjacket.engine.game.chapters import _apply_blueprint

    g = make_game_state(player_name="X", setting_id="starforged")
    rng = random.Random(7)
    seed = assemble_blueprint_seed_from_ac(rng, g)
    voicing = {
        "central_conflict": "Find the relic",
        "antagonist_force": "The cult",
        "thematic_thread": "trust",
        "acts": [
            {"title": f"Act {i + 1}", "goal": "g", "mood": "tense", "transition_trigger": "t"}
            for i in range(len(seed.acts))
        ],
        "revelations": [{"content": f"reveal {i}"} for i in range(3)],
        "possible_endings": [{"type": "earned", "description": "win"} for _ in range(3)],
    }
    _apply_blueprint(g, seed, voicing)
    assert g.narrative.story_blueprint is not None
    assert g.narrative.story_blueprint.central_conflict == "Find the relic"


def test_apply_blueprint_with_none_clears(load_engine: None) -> None:
    import random

    from straightjacket.engine.crafters.blueprint import assemble_blueprint_seed_from_ac
    from straightjacket.engine.game.chapters import _apply_blueprint
    from tests._helpers import make_blueprint

    g = make_game_state(player_name="X", setting_id="starforged")
    g.narrative.story_blueprint = make_blueprint(central_conflict="old")
    rng = random.Random(7)
    seed = assemble_blueprint_seed_from_ac(rng, g)
    _apply_blueprint(g, seed, None)
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

    g = make_game_state(player_name="X", setting_id="starforged")
    g.campaign.chapter_number = 1
    g.narrative.scene_count = 5
    g.narrative.story_blueprint = None
    g.world.current_location = "Tavern"

    summary = _close_previous_chapter(g)

    assert summary.title == "Chapter 1"
    assert g.campaign.chapter_number == 2
    assert g.world.current_location == "Tavern"
    assert len(g.campaign.campaign_history) == 1


def _ending_game() -> GameState:
    from tests._helpers import make_blueprint

    g = make_game_state(player_name="Aria", setting_id="starforged")
    g.narrative.story_blueprint = make_blueprint(story_complete=True)
    return g


def test_generate_epilogue_returns_narration(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("The journey ended quietly.")
    g = _ending_game()
    g.world.current_location = "Tavern"
    narration = generate_epilogue(provider, g)
    assert "ended quietly" in narration


def test_generate_epilogue_strips_epilogue_header(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("# Epilogue\n\nThe story ends here.")
    g = _ending_game()
    narration = generate_epilogue(provider, g)
    assert "Epilogue" not in narration.split("\n")[0]


def test_generate_epilogue_raises_on_empty_narration(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("")
    g = _ending_game()
    with pytest.raises(AIUnavailableError, match="empty narration"):
        generate_epilogue(provider, g)


def test_generate_epilogue_raises_when_cleanup_leaves_nothing(load_engine: None, stub_all: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("```json\n{}\n```")
    g = _ending_game()
    with pytest.raises(AIUnavailableError, match="empty narration after cleanup"):
        generate_epilogue(provider, g)
