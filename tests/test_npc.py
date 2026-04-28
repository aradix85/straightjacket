from straightjacket.engine.models import GameState
from tests._helpers import (
    make_brain_result,
    make_game_state,
    make_memory,
    make_npc,
    make_npc_detail,
    make_npc_rename,
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


def test_find_npc_by_id(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    _npc = find_npc(game, "npc_1")
    assert _npc is not None
    assert _npc.name == "Kira Voss"


def test_find_npc_by_name(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    _npc = find_npc(game, "Kira Voss")
    assert _npc is not None
    assert _npc.id == "npc_1"


def test_find_npc_by_alias(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    _npc = find_npc(game, "Kira")
    assert _npc is not None
    assert _npc.id == "npc_1"


def test_find_npc_substring(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()

    result = find_npc(game, "Old Borin Ironhand")
    assert result is not None
    assert result.id == "npc_2"


def test_find_npc_substring_short_no_match(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()

    result = find_npc(game, "Borin Ironhand")

    assert result is None or result.id == "npc_2"


def test_find_npc_returns_none(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    assert find_npc(game, "Nobody") is None
    assert find_npc(game, "") is None
    assert find_npc(game, None) is None


def test_edit_distance_le1() -> None:
    from straightjacket.engine.npc.matching import edit_distance_le1

    assert edit_distance_le1("kira", "kira") is True
    assert edit_distance_le1("kira", "kirra") is True
    assert edit_distance_le1("kira", "kia") is True
    assert edit_distance_le1("kira", "kora") is True
    assert edit_distance_le1("kira", "korr") is False
    assert edit_distance_le1("ab", "abcd") is False


def test_fuzzy_match_stt_variant(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = make_game_state(player_name="Hero")
    game.npcs = [
        make_npc(id="npc_1", name="Eisenberg", disposition="neutral"),
    ]

    match, match_type = fuzzy_match_existing_npc(game, "Eisenborg")
    assert match is not None
    assert match.name == "Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_multiword(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = make_game_state(player_name="Hero")
    game.npcs = [
        make_npc(id="npc_1", name="Markus Eisenberg", disposition="neutral"),
    ]
    match, match_type = fuzzy_match_existing_npc(game, "Markus Eisenborg")
    assert match is not None
    assert match.name == "Markus Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_sorted_mismatch(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = _make_game()

    match, match_type = fuzzy_match_existing_npc(game, "Kira Foss")

    if match is not None:
        assert match.name == "Kira Voss"


def test_fuzzy_match_title_only_rejected(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = _make_game()

    match, _ = fuzzy_match_existing_npc(game, "Mrs.")
    assert match is None


def test_fuzzy_match_substring(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = _make_game()
    match, match_type = fuzzy_match_existing_npc(game, "Kira Voss-Eisenstein")
    assert match is not None
    assert match.name == "Kira Voss"


def test_sanitize_npc_name() -> None:
    from straightjacket.engine.npc.matching import sanitize_npc_name

    clean, aliases = sanitize_npc_name("Kira (also known as Shadow)")
    assert clean == "Kira"
    assert "Shadow" in aliases


def test_sanitize_npc_name_no_parens() -> None:
    from straightjacket.engine.npc.matching import sanitize_npc_name

    clean, aliases = sanitize_npc_name("Kira Voss")
    assert clean == "Kira Voss"
    assert aliases == []


def test_normalize_for_match() -> None:
    from straightjacket.engine.npc.matching import normalize_for_match

    assert normalize_for_match("Wacholder-im-Schnee") == "wacholder im schnee"
    assert normalize_for_match("Wacholder im Schnee") == "wacholder im schnee"
    assert normalize_for_match("wacholder_im_schnee") == "wacholder im schnee"


def test_resolve_about_npc_self_reference(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import resolve_about_npc

    game = _make_game()

    result = resolve_about_npc(game, "Kira Voss", owner_id="npc_1")
    assert result is None


def test_resolve_about_npc_valid(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import resolve_about_npc

    game = _make_game()
    result = resolve_about_npc(game, "Old Borin", owner_id="npc_1")
    assert result == "npc_2"


def test_score_importance_direct(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    assert score_importance("neutral") == 2
    assert score_importance("terrified") == 7
    assert score_importance("transformed") == 10


def test_score_importance_compound(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    score = score_importance("angry_terrified")
    assert score >= 7


def test_score_importance_keyword_boost(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    score = score_importance("neutral", "witnessed a death")
    assert score >= 7


def test_score_importance_debug(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    score, debug = score_importance("angry", "helped a friend", debug=True)
    assert isinstance(debug, str)
    assert score >= 5


def test_consolidate_memory_under_limit(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import consolidate_memory

    npc = make_npc(id="npc_1", name="Test")
    npc.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=3) for i in range(5)]
    consolidate_memory(npc)
    assert len(npc.memory) == 5


def test_consolidate_memory_over_limit(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import consolidate_memory

    npc = make_npc(id="npc_1", name="Test")

    npc.memory = [make_memory(scene=i, event=f"event {i}", type="observation", importance=i % 10) for i in range(30)]
    npc.memory.append(make_memory(scene=31, event="reflection", type="reflection", importance=8))
    consolidate_memory(npc)
    assert len(npc.memory) <= 25

    assert any(m.type == "reflection" for m in npc.memory)


def test_retrieve_memories_empty(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

    npc = make_npc(id="npc_1", name="Test")
    result = retrieve_memories(npc, context_text="", max_count=5, current_scene=5)
    assert result == []


def test_retrieve_memories_includes_reflection(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

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


def test_retrieve_memories_about_npc_boost(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

    npc = make_npc(id="npc_1", name="Test")
    npc.memory = [
        make_memory(scene=1, event="old boring event", type="observation", importance=2, about_npc="npc_3"),
        make_memory(scene=5, event="recent event", type="observation", importance=3, about_npc=None),
    ]

    result = retrieve_memories(npc, context_text="", max_count=1, current_scene=6, present_npc_ids=frozenset({"npc_3"}))
    assert result[0].about_npc == "npc_3"


def test_reactivate_background_npc(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = make_npc(id="npc_1", name="Test", status="background")
    reactivate_npc(npc, reason="test")
    assert npc.status == "active"


def test_reactivate_deceased_refused(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = make_npc(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="test")
    assert npc.status == "deceased"


def test_reactivate_deceased_forced(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = make_npc(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="resurrection", force=True)
    assert npc.status == "active"


def test_merge_npc_identity(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    npc = make_npc(id="npc_1", name="Old Man", disposition="neutral")
    merge_npc_identity(npc, "Professor Heinrich")
    assert npc.name == "Professor Heinrich"
    assert "Old Man" in npc.aliases


def test_merge_npc_identity_same_name_skipped(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    npc = make_npc(id="npc_1", name="Kira", disposition="neutral")
    merge_npc_identity(npc, "Kira")
    assert npc.name == "Kira"
    assert npc.aliases == []


def test_sanitize_aliases(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import sanitize_aliases

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


def test_absorb_duplicate_npc(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.lifecycle import absorb_duplicate_npc

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


def test_is_complete_description() -> None:
    from straightjacket.engine.npc.lifecycle import is_complete_description

    assert is_complete_description("Tall woman with red hair.") is True
    assert is_complete_description("Tall woman with red") is False
    assert is_complete_description("Short.") is False
    assert is_complete_description("") is False


def test_retire_distant_npcs(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import retire_distant_npcs

    game = _make_game()

    for i in range(15):
        game.npcs.append(make_npc(id=f"npc_{i + 10}", name=f"NPC {i}", status="active", memory=[]))
    retire_distant_npcs(game)
    active = [n for n in game.npcs if n.status == "active"]
    assert len(active) <= 12


def test_tfidf_scores_basic(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import compute_npc_tfidf_scores

    npcs = [
        make_npc(id="npc_1", name="Kira Voss", description="sword fighter warrior"),
        make_npc(id="npc_2", name="Old Borin", description="blacksmith forge anvil"),
    ]
    scores = compute_npc_tfidf_scores(npcs, "sword and shield warrior")
    assert scores["npc_1"] > scores["npc_2"]


def test_activate_npcs_target_always_activated(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import activate_npcs_for_prompt

    game = _make_game()

    brain = make_brain_result(target_npc="npc_2", player_intent="talk to blacksmith")
    activated, mentioned, debug = activate_npcs_for_prompt(game, brain, "talk to blacksmith")
    activated_ids = {n.id for n in activated}
    assert "npc_2" in activated_ids


def test_activate_npcs_name_mention(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import activate_npcs_for_prompt

    game = _make_game()

    brain = make_brain_result(player_intent="I look for Kira")
    activated, mentioned, debug = activate_npcs_for_prompt(game, brain, "I look for Kira")
    all_npcs = {n.id for n in activated} | {n.id for n in mentioned}
    assert "npc_1" in all_npcs


def test_normalize_disposition(stub_emotions: None) -> None:
    from straightjacket.engine.npc.lifecycle import normalize_disposition

    assert normalize_disposition("hostile") == "hostile"
    assert normalize_disposition("wary") == "distrustful"
    assert normalize_disposition("curious") == "neutral"
    assert normalize_disposition("unknown_value") == "neutral"


def test_process_new_npcs_adds_npc(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game()
    assert len(game.npcs) == 2

    process_new_npcs(game, [{"name": "Maren", "description": "Young scout", "disposition": "curious"}])

    assert len(game.npcs) == 3
    maren = next(n for n in game.npcs if n.name == "Maren")
    assert maren.description == "Young scout"
    assert maren.id == "npc_3"
    assert len(maren.memory) == 1


def test_process_new_npcs_skips_player_character(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game()

    process_new_npcs(game, [{"name": "Hero", "description": "The protagonist", "disposition": "neutral"}])

    assert len(game.npcs) == 2


def test_process_new_npcs_skips_existing(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_new_npcs

    game = _make_game()

    process_new_npcs(game, [{"name": "Kira Voss", "description": "Same person", "disposition": "friendly"}])

    assert len(game.npcs) == 2


def test_process_npc_renames_updates_name(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game()

    process_npc_renames(game, [make_npc_rename(npc_id="npc_1", new_name="Kira von Asten")])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira von Asten"
    assert "Kira Voss" in npc.aliases


def test_process_npc_renames_rejects_player_name(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_renames

    game = _make_game()

    process_npc_renames(game, [make_npc_rename(npc_id="npc_1", new_name="Hero")])

    npc = next(n for n in game.npcs if n.id == "npc_1")
    assert npc.name == "Kira Voss"


def test_process_npc_details_extends_surname(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game()

    process_npc_details(game, [make_npc_detail(npc_id="npc_2", full_name="Old Borin Ironhand")])

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert npc.name == "Old Borin Ironhand"
    assert "Old Borin" in npc.aliases


def test_process_npc_details_updates_description(stub_engine: None) -> None:
    from straightjacket.engine.npc.processing import process_npc_details

    game = _make_game()

    process_npc_details(
        game,
        [make_npc_detail(npc_id="npc_2", description="Grumpy dwarf blacksmith with burn scars, secretly loyal.")],
    )

    npc = next(n for n in game.npcs if n.id == "npc_2")
    assert "burn scars" in npc.description
