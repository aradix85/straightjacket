from straightjacket.engine.models import GameState
from straightjacket.engine.models_story import ChapterSummary, NpcEvolution, PossibleEnding, StoryBlueprint
from tests._helpers import make_game_state, make_npc


def _opening_game() -> GameState:
    g = make_game_state(
        player_name="Aria",
        pronouns="she/her",
        paths=["explorer", "ace"],
        background_vow="find the lost archive",
        setting_id="starforged",
    )
    g.world.current_location = "Driftworks Station"
    g.world.current_scene_context = "The lights flicker in the corridor."
    g.world.time_of_day = "evening"
    g.narrative.scene_count = 1
    return g


def test_build_new_game_prompt_renders_with_full_state(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_game_prompt

    g = _opening_game()
    out = build_new_game_prompt(g)
    assert '<scene type="opening">' in out
    assert "Aria" in out
    assert "she/her" in out
    assert "explorer, ace" in out
    assert "find the lost archive" in out
    assert "Driftworks Station" in out


def test_build_new_game_prompt_omits_optional_tags(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_game_prompt

    g = make_game_state(player_name="Solo", setting_id="starforged")
    g.world.current_location = "Tavern"
    g.world.current_scene_context = "Quiet."
    out = build_new_game_prompt(g)
    assert "<pronouns>" not in out
    assert "<paths>" not in out
    assert "<vow>" not in out


def test_build_new_game_prompt_includes_crisis_block_when_active(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_game_prompt

    g = _opening_game()
    g.crisis_mode = True
    out = build_new_game_prompt(g)
    g2 = _opening_game()
    g2.crisis_mode = False
    out2 = build_new_game_prompt(g2)
    assert len(out) > len(out2)


def test_build_new_game_prompt_escapes_xml_in_player_name(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_game_prompt

    g = _opening_game()
    g.player_name = "Aria <hack> & Co"
    out = build_new_game_prompt(g)
    assert 'name="Aria &lt;hack&gt; &amp; Co"' in out


def test_build_epilogue_prompt_renders(load_engine: None) -> None:
    from straightjacket.engine.models import SceneLogEntry
    from straightjacket.engine.prompt_boundary import build_epilogue_prompt

    g = _opening_game()
    g.narrative.story_blueprint = StoryBlueprint(
        central_conflict="The archive holds a lethal truth",
        possible_endings=[
            PossibleEnding(type="triumph", description="Reveal the truth"),
            PossibleEnding(type="tragedy", description="Suppress the truth"),
        ],
    )
    g.npcs = [make_npc(id="npc_1", name="Kira", disposition="friendly", description="Smuggler")]
    g.narrative.session_log.append(
        SceneLogEntry(scene=1, summary="Met Kira", scene_type="expected", result="STRONG_HIT")
    )
    out = build_epilogue_prompt(g)
    assert '<scene type="epilogue">' in out
    assert "lethal truth" in out
    assert "triumph" in out
    assert "Kira" in out


def test_build_epilogue_prompt_without_blueprint(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_epilogue_prompt

    g = _opening_game()
    g.narrative.story_blueprint = None
    out = build_epilogue_prompt(g)
    assert '<scene type="epilogue">' in out
    assert "open" in out


def test_build_new_chapter_prompt_renders_with_active_npcs(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_chapter_prompt

    g = _opening_game()
    g.campaign.chapter_number = 2
    g.npcs = [
        make_npc(id="npc_1", name="Kira", disposition="friendly", description="Smuggler", aliases=["K"]),
    ]
    out = build_new_chapter_prompt(g)
    assert 'chapter="2"' in out
    assert "Kira" in out
    assert 'aliases="K"' in out


def test_build_new_chapter_prompt_includes_background_npcs(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_chapter_prompt

    g = _opening_game()
    g.npcs = [
        make_npc(id="npc_1", name="Active", disposition="friendly", description="A"),
        make_npc(id="npc_2", name="Background", disposition="neutral", description="B", status="background"),
    ]
    out = build_new_chapter_prompt(g)
    assert "<background_npcs>" in out
    assert "Background" in out


def test_build_new_chapter_prompt_includes_npc_evolutions(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_chapter_prompt

    g = _opening_game()
    g.campaign.campaign_history = [
        ChapterSummary(
            chapter=1,
            title="Chapter 1",
            summary="Things happened",
            unresolved_threads=[],
            character_growth="grew",
            npc_evolutions=[NpcEvolution(name="Kira", projection="Becomes wary")],
            thematic_question="?",
            post_story_location="Station",
            scenes=5,
            progress_tracks=[],
            threats=[],
            impacts=[],
            assets=[],
            threads=[],
            characters_list=[],
            plotlines_list=[],
        )
    ]
    out = build_new_chapter_prompt(g)
    assert "<npc_evolutions" in out
    assert "Kira" in out
    assert "Becomes wary" in out


def test_build_new_chapter_prompt_no_evolutions_when_empty(load_engine: None) -> None:
    from straightjacket.engine.prompt_boundary import build_new_chapter_prompt

    g = _opening_game()
    g.campaign.campaign_history = []
    out = build_new_chapter_prompt(g)
    scene_section, _, _ = out.partition("<task>")
    assert "<npc_evolutions" not in scene_section
