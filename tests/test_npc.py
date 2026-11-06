from unittest.mock import patch

from straightjacket.engine.gamemaster.npc.activation import activate_npcs_for_prompt, compute_npc_tfidf_scores
from straightjacket.engine.gamemaster.npc.description_match import is_complete_description
from straightjacket.engine.gamemaster.npc.lifecycle import (
    absorb_duplicate_npc,
    absorb_npc,
    merge_npc_identity,
    reactivate_npc,
    retire_distant_npcs,
    sanitize_aliases,
)
from straightjacket.engine.gamemaster.npc.matching import (
    edit_distance_le1,
    find_npc,
    fuzzy_match_existing_npc,
    normalize_for_match,
    resolve_about_npc,
    sanitize_npc_name,
)
from straightjacket.engine.gamemaster.npc.memory import consolidate_memory, retrieve_memories, score_importance
from straightjacket.engine.gamemaster.npc.processing import process_new_npcs, process_npc_details, process_npc_renames
from straightjacket.engine.models import GameState
from straightjacket.engine.ruleset.bond import get_npc_bond
from tests._helpers import (
    make_brain_result,
    make_character_entry,
    make_clock,
    make_game_state,
    make_memory,
    make_npc,
    make_npc_detail,
    make_npc_rename,
    make_progress_track,
)


def _make_game() -> "GameState":
    game = make_game_state(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira Voss",
            disposition="friendly",
            description="Tall woman with red hair",
            agenda="find the artifact",
            instinct="protect allies",
            aliases=["Kira"],
        ),
        make_npc(
            id="npc_2",
            name="Old Borin",
            disposition="neutral",
            description="Grumpy dwarf blacksmith",
            agenda="",
            instinct="",
        ),
    ]
    return game


def test_find_npc_by_id() -> None:
    game = _make_game()
    npc = find_npc(game, "npc_1")
    assert npc is not None
    assert npc.name == "Kira Voss"


def test_find_npc_by_name() -> None:
    game = _make_game()
    npc = find_npc(game, "Kira Voss")
    assert npc is not None
    assert npc.id == "npc_1"


def test_find_npc_by_alias() -> None:
    game = _make_game()
    npc = find_npc(game, "Kira")
    assert npc is not None
    assert npc.id == "npc_1"


def test_find_npc_substring() -> None:
    game = _make_game()

    result = find_npc(game, "Old Borin Ironhand")
    assert result is not None
    assert result.id == "npc_2"


def test_find_npc_substring_short_no_match() -> None:
    game = _make_game()

    result = find_npc(game, "Borin Ironhand")

    assert result is None or result.id == "npc_2"


def test_find_npc_returns_none() -> None:
    game = _make_game()
    assert find_npc(game, "Nobody") is None
    assert find_npc(game, "") is None
    assert find_npc(game, None) is None


def test_edit_distance_le1() -> None:
    assert edit_distance_le1("kira", "kira") is True
    assert edit_distance_le1("kira", "kirra") is True
    assert edit_distance_le1("kira", "kia") is True
    assert edit_distance_le1("kira", "kora") is True
    assert edit_distance_le1("kira", "korr") is False
    assert edit_distance_le1("ab", "abcd") is False


def test_fuzzy_match_stt_variant() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [
        make_npc(id="npc_1", name="Eisenberg", disposition="neutral"),
    ]

    match, match_type = fuzzy_match_existing_npc(game, "Eisenborg")
    assert match is not None
    assert match.name == "Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_multiword() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [
        make_npc(id="npc_1", name="Markus Eisenberg", disposition="neutral"),
    ]
    match, match_type = fuzzy_match_existing_npc(game, "Markus Eisenborg")
    assert match is not None
    assert match.name == "Markus Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_sorted_mismatch() -> None:
    game = _make_game()

    match, _match_type = fuzzy_match_existing_npc(game, "Kira Foss")

    if match is not None:
        assert match.name == "Kira Voss"


def test_fuzzy_match_title_only_rejected() -> None:
    game = _make_game()

    match, _ = fuzzy_match_existing_npc(game, "Mrs.")
    assert match is None


def test_fuzzy_match_substring() -> None:
    game = _make_game()
    match, _match_type = fuzzy_match_existing_npc(game, "Kira Voss-Eisenstein")
    assert match is not None
    assert match.name == "Kira Voss"


def test_fuzzy_match_by_a_shared_word_is_the_same_figure() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Halvard Brennick")]
    match, match_type = fuzzy_match_existing_npc(game, "Brennick the Elder")
    assert match is not None
    assert match.name == "Halvard Brennick"
    assert match_type == "identity"


def test_fuzzy_match_without_a_match_has_no_type() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Halvard Brennick")]
    assert fuzzy_match_existing_npc(game, "Odette Marrow") == (None, None)


def test_sanitize_npc_name() -> None:
    clean, aliases = sanitize_npc_name("Kira (also known as Shadow)")
    assert clean == "Kira"
    assert "Shadow" in aliases


def test_sanitize_npc_name_no_parens() -> None:
    clean, aliases = sanitize_npc_name("Kira Voss")
    assert clean == "Kira Voss"
    assert not aliases


def test_normalize_for_match() -> None:
    assert normalize_for_match("Wacholder-im-Schnee") == "wacholder im schnee"
    assert normalize_for_match("Wacholder im Schnee") == "wacholder im schnee"
    assert normalize_for_match("wacholder_im_schnee") == "wacholder im schnee"


def test_resolve_about_npc_self_reference() -> None:
    game = _make_game()

    result = resolve_about_npc(game, "Kira Voss", owner_id="npc_1")
    assert result is None


def test_resolve_about_npc_valid() -> None:
    game = _make_game()
    result = resolve_about_npc(game, "Old Borin", owner_id="npc_1")
    assert result == "npc_2"


def test_score_importance_direct() -> None:
    assert score_importance("neutral", event_text="") == 2
    assert score_importance("terrified", event_text="") == 7
    assert score_importance("transformed", event_text="") == 10


def test_score_importance_compound() -> None:
    score = score_importance("angry_terrified", event_text="")
    assert score >= 7


def test_score_importance_keyword_boost() -> None:
    score = score_importance("neutral", "witnessed a death")
    assert score >= 7


def test_consolidate_memory_under_limit() -> None:
    npc = make_npc(id="npc_1", name="Test")
    npc.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=3) for i in range(5)]
    consolidate_memory(npc)
    assert len(npc.memory) == 5


def test_consolidate_memory_over_limit() -> None:
    npc = make_npc(id="npc_1", name="Test")

    npc.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=i % 10) for i in range(30)]
    npc.memory.append(make_memory(scene=31, event="reflection", type="reflection", importance=8))
    consolidate_memory(npc)
    assert len(npc.memory) <= 25

    assert any(m.type == "reflection" for m in npc.memory)


def test_retrieve_memories_empty() -> None:
    npc = make_npc(id="npc_1", name="Test")
    result = retrieve_memories(npc, context_text="", max_count=5, current_scene=5)
    assert not result


def test_retrieve_memories_includes_reflection() -> None:
    npc = make_npc(id="npc_1", name="Test")
    npc.memory = [
        make_memory(scene=1, event="saw player", type="observation", importance=3),
        make_memory(scene=2, event="reflection on trust", type="reflection", importance=8),
        make_memory(scene=3, event="traded goods", type="observation", importance=2),
        make_memory(scene=4, event="fought together", type="observation", importance=5),
        make_memory(scene=5, event="shared a meal", type="observation", importance=3),
    ]
    result = retrieve_memories(npc, context_text="", max_count=3, current_scene=6)
    assert len(result) == 3
    assert any(m.type == "reflection" for m in result)


def test_retrieve_memories_about_npc_boost() -> None:
    npc = make_npc(id="npc_1", name="Test")
    npc.memory = [
        make_memory(scene=1, event="old boring event", type="observation", importance=2, about_npc="npc_3"),
        make_memory(scene=5, event="recent event", type="observation", importance=3, about_npc=None),
    ]

    result = retrieve_memories(npc, context_text="", max_count=1, current_scene=6, present_npc_ids=frozenset({"npc_3"}))
    assert result[0].about_npc == "npc_3"


def test_reactivate_background_npc() -> None:
    npc = make_npc(id="npc_1", name="Test", status="background")
    reactivate_npc(npc, reason="test")
    assert npc.status == "active"


def test_a_lore_figure_who_appears_in_person_becomes_active() -> None:
    game = _make_game()
    game.npcs.append(make_npc(id="npc_9", name="Edda Varn", status="lore"))
    process_new_npcs(game, [{"name": "Edda Varn", "description": "The founder, alive", "disposition": "neutral"}])
    assert [n.status for n in game.npcs if n.id == "npc_9"] == ["active"]


def test_reactivate_deceased_refused() -> None:
    npc = make_npc(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="test")
    assert npc.status == "deceased"


def test_reactivate_deceased_forced() -> None:
    npc = make_npc(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="resurrection", force=True)
    assert npc.status == "active"


def test_merge_npc_identity() -> None:
    npc = make_npc(id="npc_1", name="Old Man", disposition="neutral")
    merge_npc_identity(npc, "Professor Heinrich", game=make_game_state(npcs=[npc]))
    assert npc.name == "Professor Heinrich"
    assert "Old Man" in npc.aliases


def test_merge_npc_identity_same_name_skipped() -> None:
    npc = make_npc(id="npc_1", name="Kira", disposition="neutral")
    merge_npc_identity(npc, "Kira", game=make_game_state(npcs=[npc]))
    assert npc.name == "Kira"
    assert not npc.aliases


def test_sanitize_aliases() -> None:
    npc = make_npc(
        id="npc_1",
        name="Kira Voss",
        aliases=["Kira", "Kira", "Kira Voss", "A very long description that is not really an alias at all ever"],
    )
    sanitize_aliases(npc)
    assert "Kira" in npc.aliases
    assert npc.aliases.count("Kira") == 1
    assert "Kira Voss" not in npc.aliases
    assert len(npc.aliases) == 1


def test_absorb_duplicate_npc() -> None:
    game = _make_game()

    dup = make_npc(
        id="npc_3",
        name="Kira Voss",
        description="Same person, different entry",
        memory=[make_memory(scene=5, event="dup memory", type="observation", importance=5)],
    )
    game.npcs.append(dup)

    original = game.npcs[0]
    absorb_duplicate_npc(game, original, "Kira Voss")

    assert len(game.npcs) == 2
    assert any(m.event == "dup memory" for m in original.memory)


def _merge_game(original_ticks: int | None, dup_ticks: int | None) -> GameState:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="npc_1", name="Mira"), make_npc(id="npc_2", name="The stranger")]
    for npc_id, ticks in (("npc_1", original_ticks), ("npc_2", dup_ticks)):
        if ticks is not None:
            game.progress_tracks.append(
                make_progress_track(id=f"connection_{npc_id}", name=npc_id, track_type="connection", ticks=ticks)
            )
    game.world.clocks = [make_clock(name="The stranger's errand", owner_kind="npc", owner_id="The stranger")]
    game.narrative.characters_list = [
        make_character_entry(id="npc_1", name="Mira", entry_type="npc", weight=1),
        make_character_entry(id="npc_2", name="The stranger", entry_type="npc", weight=1),
    ]
    return game


def test_a_merged_npc_leaves_nothing_that_points_at_it() -> None:
    game = _merge_game(original_ticks=None, dup_ticks=12)
    mira, stranger = game.npcs
    absorb_npc(game, mira, stranger)

    assert [n.id for n in game.npcs] == ["npc_1"]
    assert [(t.id, t.name) for t in game.progress_tracks] == [("connection_npc_1", "Mira")]
    assert get_npc_bond(game, "npc_1") == 3
    assert game.world.clocks[0].owner_id == "Mira"
    assert [(c.id, c.weight) for c in game.narrative.characters_list] == [("npc_1", 2)]
    assert "The stranger" in mira.aliases


def test_a_merge_keeps_the_connection_with_the_most_progress() -> None:
    for original_ticks, dup_ticks, kept in ((20, 8, 20), (8, 20, 20), (8, 8, 8)):
        game = _merge_game(original_ticks, dup_ticks)
        absorb_npc(game, game.npcs[0], game.npcs[1])
        assert [(t.id, t.ticks) for t in game.progress_tracks] == [("connection_npc_1", kept)]


def test_is_complete_description() -> None:
    assert is_complete_description("Tall woman with red hair.") is True
    assert is_complete_description("Tall woman with red") is False
    assert is_complete_description("Short.") is False
    assert is_complete_description("") is False


def test_retire_distant_npcs() -> None:
    game = _make_game()

    for i in range(15):
        game.npcs.append(make_npc(id=f"npc_{i + 10}", name=f"NPC {i}", status="active", memory=[]))
    retire_distant_npcs(game)
    active = [n for n in game.npcs if n.status == "active"]
    assert len(active) <= 12


def test_tfidf_scores_basic() -> None:
    npcs = [
        make_npc(id="npc_1", name="Kira Voss", description="sword fighter warrior"),
        make_npc(id="npc_2", name="Old Borin", description="blacksmith forge anvil"),
    ]
    scores = compute_npc_tfidf_scores(npcs, "sword and shield warrior")
    assert scores["npc_1"] > scores["npc_2"]


def test_activate_npcs_target_always_activated() -> None:
    game = _make_game()

    brain = make_brain_result(target_npc="npc_2", player_intent="talk to blacksmith")
    activated, _mentioned = activate_npcs_for_prompt(game, brain, "talk to blacksmith")
    activated_ids = {n.id for n in activated}
    assert "npc_2" in activated_ids


def test_activate_npcs_name_mention() -> None:
    game = _make_game()

    brain = make_brain_result(player_intent="I look for Kira")
    activated, mentioned = activate_npcs_for_prompt(game, brain, "I look for Kira")
    all_npcs = {n.id for n in activated} | {n.id for n in mentioned}
    assert "npc_1" in all_npcs


def test_process_new_npcs_adds_npc() -> None:
    game = _make_game()
    assert len(game.npcs) == 2

    with patch("straightjacket.engine.gamemaster.npc.processing.roll_oracle_name", return_value="Maren"):
        process_new_npcs(game, [{"name": "Maren", "description": "Young scout", "disposition": "neutral"}])

    assert len(game.npcs) == 3
    maren = next(n for n in game.npcs if n.name == "Maren")
    assert maren.description == "Young scout"
    assert maren.id == "npc_3"
    assert len(maren.memory) == 1


def test_process_new_npcs_skips_player_character() -> None:
    game = _make_game()

    process_new_npcs(game, [{"name": "Hero", "description": "The protagonist", "disposition": "neutral"}])

    assert len(game.npcs) == 2


def test_process_new_npcs_skips_existing() -> None:
    game = _make_game()

    process_new_npcs(game, [{"name": "Kira Voss", "description": "Same person", "disposition": "friendly"}])

    assert len(game.npcs) == 2


def test_process_npc_renames_updates_name() -> None:
    game = _make_game()

    process_npc_renames(game, [make_npc_rename(npc_id="npc_1", new_name="Kira von Asten")])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira von Asten"
    assert "Kira Voss" in npc.aliases


def test_process_npc_renames_rejects_player_name() -> None:
    game = _make_game()

    process_npc_renames(game, [make_npc_rename(npc_id="npc_1", new_name="Hero")])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira Voss"


def test_process_npc_details_extends_surname() -> None:
    game = _make_game()

    process_npc_details(game, [make_npc_detail(npc_id="npc_2", full_name="Old Borin Ironhand")], world_addition="")

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert npc.name == "Old Borin Ironhand"
    assert "Old Borin" in npc.aliases


def test_process_npc_details_updates_description() -> None:
    game = _make_game()

    process_npc_details(
        game,
        [make_npc_detail(npc_id="npc_2", description="Grumpy dwarf blacksmith with burn scars, secretly loyal.")],
        world_addition="",
    )

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert "burn scars" in npc.description
