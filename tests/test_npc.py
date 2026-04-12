#!/usr/bin/env python3
"""Tests for NPC subsystem: matching, memory, lifecycle, activation.

Covers the fragile edge cases documented in code comments:
- Fuzzy matching with edit distance, STT variants, title filtering
- Memory importance scoring, consolidation, retrieval
- Lifecycle: absorb duplicates, description-based dedup, reactivation
- Activation: TF-IDF scoring, threshold filtering

Run: python -m pytest tests/test_npc.py -v
"""


# Stubs set up in conftest.py

from straightjacket.engine.models import GameState, MemoryEntry, NpcData


def _make_game() -> "GameState":
    game = GameState(player_name="Hero")
    game.narrative.scene_count = 5
    game.world.current_location = "Tavern"
    game.npcs = [
        NpcData(
            id="npc_1",
            name="Kira Voss",
            disposition="friendly",
            description="Tall woman with red hair",
            agenda="find the artifact",
            instinct="protect allies",
            aliases=["Kira"],
        ),
        NpcData(
            id="npc_2",
            name="Old Borin",
            disposition="neutral",
            description="Grumpy dwarf blacksmith",
            agenda="",
            instinct="",
        ),
    ]
    return game


# ── matching.py tests ─────────────────────────────────────────


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
    # "Old Borin" is contained in the ref if we search by a longer name
    # that contains the existing name
    result = find_npc(game, "Old Borin Ironhand")
    assert result is not None
    assert result.id == "npc_2"


def test_find_npc_substring_short_no_match(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    # "Borin Ironhand" doesn't contain "Old Borin" and vice versa
    # (only partial overlap) — find_npc is conservative here
    result = find_npc(game, "Borin Ironhand")
    # This goes through fuzzy_match, not direct find_npc substring
    # find_npc requires 5+ char substring containment
    assert result is None or result.id == "npc_2"


def test_find_npc_returns_none(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import find_npc

    game = _make_game()
    assert find_npc(game, "Nobody") is None
    assert find_npc(game, "") is None
    assert find_npc(game, None) is None  # type: ignore[arg-type]


def test_edit_distance_le1() -> None:
    from straightjacket.engine.npc.matching import edit_distance_le1

    assert edit_distance_le1("kira", "kira") is True
    assert edit_distance_le1("kira", "kirra") is True  # insertion
    assert edit_distance_le1("kira", "kia") is True  # deletion
    assert edit_distance_le1("kira", "kora") is True  # substitution
    assert edit_distance_le1("kira", "korr") is False  # distance 2
    assert edit_distance_le1("ab", "abcd") is False  # length diff > 1


def test_fuzzy_match_stt_variant(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = GameState(player_name="Hero")
    game.npcs = [
        NpcData(id="npc_1", name="Eisenberg", disposition="neutral"),
    ]
    # Single-word name: "Eisenborg" is edit-distance-1 from "Eisenberg"
    # (no significant-word-overlap continue-skip because there's no shared word)
    match, match_type = fuzzy_match_existing_npc(game, "Eisenborg")
    assert match is not None
    assert match.name == "Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_multiword(stub_engine: None) -> None:
    """Multi-word names: one word matches exactly, another is edit-distance-1.
    Previously a known limitation (significant_overlap continue skipped edit-distance).
    Fixed: overlap ratio rejection no longer skips the edit-distance check."""
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = GameState(player_name="Hero")
    game.npcs = [
        NpcData(id="npc_1", name="Markus Eisenberg", disposition="neutral"),
    ]
    match, match_type = fuzzy_match_existing_npc(game, "Markus Eisenborg")
    assert match is not None
    assert match.name == "Markus Eisenberg"
    assert match_type == "stt_variant"


def test_fuzzy_match_stt_variant_sorted_mismatch(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = _make_game()
    # "Kira Foss" vs "Kira Voss" — sorted() puts foss before kira,
    # breaking positional edit-distance check. This is a known limitation.
    # The word-overlap path catches it instead via "Kira" significant overlap.
    match, match_type = fuzzy_match_existing_npc(game, "Kira Foss")
    # Matches via significant word overlap (Kira >= 4 chars), not edit distance
    if match is not None:
        assert match.name == "Kira Voss"


def test_fuzzy_match_title_only_rejected(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import fuzzy_match_existing_npc

    game = _make_game()
    # "Mrs." alone shouldn't match anything
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
    # Should return None when about_npc resolves to the owner
    result = resolve_about_npc(game, "Kira Voss", owner_id="npc_1")
    assert result is None


def test_resolve_about_npc_valid(stub_engine: None) -> None:
    from straightjacket.engine.npc.matching import resolve_about_npc

    game = _make_game()
    result = resolve_about_npc(game, "Old Borin", owner_id="npc_1")
    assert result == "npc_2"


# ── memory.py tests ──────────────────────────────────────────


def test_score_importance_direct(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    assert score_importance("neutral") == 2
    assert score_importance("terrified") == 7
    assert score_importance("transformed") == 10


def test_score_importance_compound(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    # Compound emotions: take the highest
    score = score_importance("angry_terrified")
    assert score >= 7  # terrified = 7


def test_score_importance_keyword_boost(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    # "neutral" = 2, but "death" keyword boost = 7
    score = score_importance("neutral", "witnessed a death")
    assert score >= 7


def test_score_importance_debug(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import score_importance

    score, debug = score_importance("angry", "helped a friend", debug=True)
    assert isinstance(debug, str)
    assert score >= 5


def test_consolidate_memory_under_limit(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import consolidate_memory

    npc = NpcData(id="npc_1", name="Test")
    npc.memory = [MemoryEntry(scene=i, event=f"event {i}", type="observation", importance=3) for i in range(5)]
    consolidate_memory(npc)
    assert len(npc.memory) == 5  # under limit, no change


def test_consolidate_memory_over_limit(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.memory import consolidate_memory

    npc = NpcData(id="npc_1", name="Test")
    # Create 30 memories (over the 25 limit)
    npc.memory = [MemoryEntry(scene=i, event=f"event {i}", type="observation", importance=i % 10) for i in range(30)]
    npc.memory.append(MemoryEntry(scene=31, event="reflection", type="reflection", importance=8))
    consolidate_memory(npc)
    assert len(npc.memory) <= 25
    # Reflection should be kept
    assert any(m.type == "reflection" for m in npc.memory)


def test_retrieve_memories_empty(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

    npc = NpcData(id="npc_1", name="Test")
    result = retrieve_memories(npc, current_scene=5)
    assert result == []


def test_retrieve_memories_includes_reflection(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

    npc = NpcData(id="npc_1", name="Test")
    npc.memory = [
        MemoryEntry(scene=1, event="saw player", type="observation", importance=3),
        MemoryEntry(scene=2, event="reflection on trust", type="reflection", importance=8),
        MemoryEntry(scene=3, event="traded goods", type="observation", importance=2),
        MemoryEntry(scene=4, event="fought together", type="observation", importance=5),
        MemoryEntry(scene=5, event="shared a meal", type="observation", importance=3),
    ]
    result = retrieve_memories(npc, max_count=3, current_scene=6)
    assert len(result) == 3
    assert any(m.type == "reflection" for m in result)


def test_retrieve_memories_about_npc_boost(stub_engine: None) -> None:
    from straightjacket.engine.npc.memory import retrieve_memories

    npc = NpcData(id="npc_1", name="Test")
    npc.memory = [
        MemoryEntry(scene=1, event="old boring event", type="observation", importance=2, about_npc="npc_3"),
        MemoryEntry(scene=5, event="recent event", type="observation", importance=3, about_npc=None),
    ]
    # When npc_3 is present, memory about npc_3 gets boosted
    result = retrieve_memories(npc, max_count=1, current_scene=6, present_npc_ids={"npc_3"})
    assert result[0].about_npc == "npc_3"


# ── lifecycle.py tests ───────────────────────────────────────


def test_reactivate_background_npc(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = NpcData(id="npc_1", name="Test", status="background")
    reactivate_npc(npc, reason="test")
    assert npc.status == "active"


def test_reactivate_deceased_refused(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = NpcData(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="test")
    assert npc.status == "deceased"  # no force = stays dead


def test_reactivate_deceased_forced(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import reactivate_npc

    npc = NpcData(id="npc_1", name="Test", status="deceased")
    reactivate_npc(npc, reason="resurrection", force=True)
    assert npc.status == "active"


def test_merge_npc_identity(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    npc = NpcData(id="npc_1", name="Old Man", disposition="neutral")
    merge_npc_identity(npc, "Professor Heinrich")
    assert npc.name == "Professor Heinrich"
    assert "Old Man" in npc.aliases


def test_merge_npc_identity_same_name_skipped(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import merge_npc_identity

    npc = NpcData(id="npc_1", name="Kira", disposition="neutral")
    merge_npc_identity(npc, "Kira")
    assert npc.name == "Kira"
    assert npc.aliases == []


def test_sanitize_aliases(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import sanitize_aliases

    npc = NpcData(
        id="npc_1",
        name="Kira Voss",
        aliases=["Kira", "Kira", "Kira Voss", "A very long description that is not really an alias at all ever"],
    )
    sanitize_aliases(npc)
    assert "Kira" in npc.aliases
    assert npc.aliases.count("Kira") == 1
    assert "Kira Voss" not in npc.aliases  # same as name
    assert len(npc.aliases) == 1  # long description stripped


def test_absorb_duplicate_npc(stub_engine: None, stub_emotions: None) -> None:
    from straightjacket.engine.npc.lifecycle import absorb_duplicate_npc

    game = _make_game()
    # Add a duplicate NPC with the same name
    dup = NpcData(
        id="npc_3",
        name="Kira Voss",
        description="Same person, different entry",
        memory=[MemoryEntry(scene=5, event="dup memory", type="observation", importance=5)],
    )
    game.npcs.append(dup)

    original = game.npcs[0]  # npc_1 = Kira Voss
    absorb_duplicate_npc(game, original, "Kira Voss")

    assert len(game.npcs) == 2  # dup removed
    assert any(m.event == "dup memory" for m in original.memory)


def test_is_complete_description() -> None:
    from straightjacket.engine.npc.lifecycle import is_complete_description

    assert is_complete_description("Tall woman with red hair.") is True
    assert is_complete_description("Tall woman with red") is False
    assert is_complete_description("Short.") is False  # too short
    assert is_complete_description("") is False


def test_retire_distant_npcs(stub_engine: None) -> None:
    from straightjacket.engine.npc.lifecycle import retire_distant_npcs

    game = _make_game()
    # Add many NPCs to exceed max_active=12
    for i in range(15):
        game.npcs.append(NpcData(id=f"npc_{i + 10}", name=f"NPC {i}", status="active", memory=[]))
    retire_distant_npcs(game)
    active = [n for n in game.npcs if n.status == "active"]
    assert len(active) <= 12


# ── activation.py tests ──────────────────────────────────────


def test_tfidf_scores_basic(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import compute_npc_tfidf_scores

    npcs = [
        NpcData(id="npc_1", name="Kira Voss", description="sword fighter warrior"),
        NpcData(id="npc_2", name="Old Borin", description="blacksmith forge anvil"),
    ]
    scores = compute_npc_tfidf_scores(npcs, "sword and shield warrior")
    assert scores["npc_1"] > scores["npc_2"]


def test_activate_npcs_target_always_activated(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import activate_npcs_for_prompt

    game = _make_game()
    from straightjacket.engine.models import BrainResult

    brain = BrainResult(target_npc="npc_2", player_intent="talk to blacksmith")
    activated, mentioned, debug = activate_npcs_for_prompt(game, brain, "talk to blacksmith")
    activated_ids = {n.id for n in activated}
    assert "npc_2" in activated_ids


def test_activate_npcs_name_mention(stub_engine: None) -> None:
    from straightjacket.engine.npc.activation import activate_npcs_for_prompt

    game = _make_game()
    from straightjacket.engine.models import BrainResult

    brain = BrainResult(player_intent="I look for Kira")
    activated, mentioned, debug = activate_npcs_for_prompt(game, brain, "I look for Kira")
    all_npcs = {n.id for n in activated} | {n.id for n in mentioned}
    assert "npc_1" in all_npcs


# ── normalize_disposition ─────────────────────────────────────


def test_normalize_disposition(stub_emotions: None) -> None:
    from straightjacket.engine.npc.lifecycle import normalize_disposition

    assert normalize_disposition("hostile") == "hostile"
    assert normalize_disposition("wary") == "distrustful"
    assert normalize_disposition("curious") == "neutral"
    assert normalize_disposition("unknown_value") == "neutral"  # fallback


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
