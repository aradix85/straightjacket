import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.models import GameState
from tests._creation import OPENING_TEXT, OpeningProvider, create_game
from tests._helpers import make_clock, make_game_state, make_memory, make_npc, make_threat
from tests._mocks import MockProvider


def _game() -> GameState:
    return create_game(
        "starforged",
        location="Drift Station",
        npcs=[("Kira Vance", "A pilot with a burned hand.", "friendly")],
        stats=(2, 2, 1, 1, 3),
        player_name="Aria",
        background_vow="Keep the station running",
    )


def _next_chapter(game: GameState, provider: OpeningProvider | None = None) -> str:
    from straightjacket.engine.game.chapters import start_new_chapter

    return start_new_chapter(provider or OpeningProvider([], "Ring Dock"), game)


def test_a_new_chapter_keeps_the_character_and_the_clocks(load_engine: None) -> None:
    game = _game()
    meters = {"health": 2, "spirit": 3, "supply": 1, "momentum": 7}
    game.resources.meters.update(meters)
    game.world.clocks = [make_clock(name="The flood rises")]
    clocks = [c.to_dict() for c in game.world.clocks]
    _next_chapter(game)
    assert {name: game.resources.meters[name] for name in meters} == meters
    assert [c.to_dict() for c in game.world.clocks][: len(clocks)] == clocks


def test_a_new_chapter_keeps_what_carries_over(load_engine: None) -> None:
    game = _game()
    game.threats = [make_threat(id="t1", name="Old threat")]
    game.impacts = ["wounded"]
    before = (
        [t.id for t in game.progress_tracks],
        [t.id for t in game.narrative.threads],
        list(game.assets),
    )
    _next_chapter(game)
    after = ([t.id for t in game.progress_tracks], [t.id for t in game.narrative.threads], list(game.assets))
    assert after == before
    assert [t.id for t in game.threats][:1] == ["t1"]
    assert game.impacts == ["wounded"]


def test_a_new_chapter_restarts_what_belongs_to_one_chapter(load_engine: None) -> None:
    from tests._helpers import make_blueprint

    game = _game()
    game.world.chaos_factor = 7
    game.world.time_of_day = "evening"
    game.world.location_history = ["Old dock"]
    game.narrative.scene_count = 9
    game.narrative.story_blueprint = make_blueprint(central_conflict="old")
    game.campaign.epilogue_dismissed = True
    game.last_turn_snapshot = game.snapshot()

    assert _next_chapter(game) == OPENING_TEXT

    assert [s.title for s in game.campaign.campaign_history] == ["Chapter 1"]
    assert game.campaign.chapter_number == 2
    assert (game.world.chaos_factor, game.world.time_of_day) == (gm().chaos.start, gm().opening.time_of_day)
    assert (game.world.location_history, game.world.current_location) == (["Drift Station"], "Ring Dock")
    assert game.narrative.scene_count == 1
    assert [e.result for e in game.narrative.session_log] == ["opening"]
    assert [e.narration for e in game.narrative.narration_history] == [OPENING_TEXT]
    assert game.narrative.story_blueprint is not None
    assert game.narrative.story_blueprint.central_conflict == "A buried record threatens the settlement"
    assert game.campaign.epilogue_dismissed is False
    assert game.last_turn_snapshot is None


def test_a_new_chapter_drops_only_the_old_adventures_keyed_scenes(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.keyed_scenes import add_keyed_scene

    game = _game()
    game.narrative.keyed_scenes = []
    for source in ("ac:Old Plot Point", "clock:The flood rises:2", "random_event:pc_negative:npc_1"):
        add_keyed_scene(
            game.narrative, trigger_type="scene_count", trigger_value="99", priority=1, narrative_hint="", source=source
        )

    _next_chapter(game)

    sources = {ks.source for ks in game.narrative.keyed_scenes}
    assert "ac:Old Plot Point" not in sources
    assert {"clock:The flood rises:2", "random_event:pc_negative:npc_1"} <= sources


def test_a_chapter_whose_blueprint_cannot_be_voiced_has_none(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse

    class _NoVoicing(OpeningProvider):
        def create_message(self, spec: AICallSpec) -> AIResponse:
            if spec.json_schema is not None and "central_conflict" in spec.json_schema["properties"]:
                raise ConnectionError("voicing is down")
            return super().create_message(spec)

    game = _game()
    _next_chapter(game, _NoVoicing([], "Ring Dock"))
    assert game.narrative.story_blueprint is None


def test_at_a_chapter_boundary_an_npc_without_a_part_in_the_story_steps_back(load_engine: None) -> None:
    game = _game()
    cap = gm().chapter.open_threads_max
    major = make_npc(id="npc_7", name="Major", status="active", agenda="serious goal")
    major.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=5) for i in range(cap + 5)]
    game.npcs += [
        major,
        make_npc(id="npc_8", name="Filler", status="active", agenda="", memory=[]),
        make_npc(id="npc_9", name="Dead", status="deceased"),
    ]
    _next_chapter(game)
    status = {n.name: n.status for n in game.npcs}
    assert (status["Major"], status["Filler"], status["Dead"]) == ("active", "background", "deceased")
    assert len(next(n for n in game.npcs if n.name == "Major").memory) <= cap


def test_a_created_game_moves_into_its_next_chapter(load_engine: None) -> None:
    from straightjacket.engine.ruleset.legacy import mark_legacy
    from straightjacket.engine.ruleset.progress import filled_boxes
    from tests.elvira.elvira_bot.invariants import assert_game_state

    game = _game()
    game.npcs[0].agenda = "keep her ship"
    mark_legacy(game, "quests", "epic")
    mark_legacy(game, "bonds", "formidable")
    game.campaign.xp_spent = 2
    experience = (game.campaign.xp, game.campaign.xp_spent)
    provider = OpeningProvider(
        [("Kira", "A pilot.", "friendly"), ("Dace Orrin", "A dockhand.", "neutral")], "Ring Dock"
    )

    narration = _next_chapter(game, provider)

    assert narration == OPENING_TEXT
    assert game.world.current_location == "Ring Dock"
    assert sorted(n.name for n in game.npcs) == ["Dace Orrin", "Kira Vance"]
    assert [t.id for t in game.progress_tracks] == ["vow_background"]
    assert (game.campaign.xp, game.campaign.xp_spent) == experience
    assert {name: filled_boxes(track) for name, track in game.campaign.legacy.items()} == {
        "quests": 3,
        "bonds": 1,
        "discoveries": 0,
    }
    assert assert_game_state(game, turn=1) == []


def test_a_chapter_opening_registers_its_people_and_place_beside_a_lore_figure(load_engine: None) -> None:
    game = _game()
    game.npcs.append(make_npc(id="npc_2", name="The Founder", status="lore"))
    _next_chapter(game, OpeningProvider([("Dace Orrin", "A dockhand.", "neutral")], "Ring Dock"))
    assert game.world.current_location == "Ring Dock"
    assert sorted(n.name for n in game.npcs) == ["Dace Orrin", "Kira Vance", "The Founder"]


def test_a_game_that_is_over_cannot_start_a_chapter(load_engine: None) -> None:
    game = _game()
    game.end_reason = "death"
    with pytest.raises(RuntimeError, match="succession"):
        _next_chapter(game)


def _ending_game() -> GameState:
    from tests._helpers import make_blueprint

    g = make_game_state(player_name="Aria", setting_id="starforged")
    g.narrative.story_blueprint = make_blueprint(story_complete=True)
    return g


def test_generate_epilogue_returns_narration(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("The journey ended quietly.")
    g = _ending_game()
    g.world.current_location = "Tavern"
    narration = generate_epilogue(provider, g)
    assert "ended quietly" in narration


def test_generate_epilogue_strips_epilogue_header(load_engine: None) -> None:
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("# Epilogue\n\nThe story ends here.")
    g = _ending_game()
    narration = generate_epilogue(provider, g)
    assert "Epilogue" not in narration.split("\n")[0]


def test_generate_epilogue_raises_on_empty_narration(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("")
    g = _ending_game()
    with pytest.raises(AIUnavailableError, match="empty narration"):
        generate_epilogue(provider, g)


def test_generate_epilogue_raises_when_cleanup_leaves_nothing(load_engine: None) -> None:
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from straightjacket.engine.game.chapters import generate_epilogue

    provider = MockProvider("```json\n{}\n```")
    g = _ending_game()
    with pytest.raises(AIUnavailableError, match="empty narration after cleanup"):
        generate_epilogue(provider, g)
