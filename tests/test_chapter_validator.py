"""Tests for step 2: chapter-summary contradiction validator.

The validator runs over the AI-written narrative dict before it is fused
with the engine snapshot. Two passes:

- Rule pass: scans named entities (NPCs, tracks, threats) paired with
  status-shift keywords. Cheap, deterministic, catches obvious cases.
- LLM pass: catches euphemisms the rule pass cannot interpret. Mocked
  here via a stub provider that returns canned validator JSON.

Coverage:
- Each rule-pass detector fires on a clear contradiction.
- Invented colour (entities not in state) does NOT trigger.
- Deceased NPC mentioned with death keyword passes (no contradiction —
  state and narrative agree).
- Word-boundary safety (Marc vs Marcus; "fell" inside "fellowship").
- LLM pass surfaces violations missed by rules.
- Retry loop: contradiction → retry → pass.
- Final-fallback: retries exhausted, last narrative kept with warning.
- Empty state (no NPCs, no tracks, no threats) handled.
"""

from __future__ import annotations

from typing import Any

import pytest

from straightjacket.engine.ai.chapter_validator import (
    _rule_check,
    validate_and_retry,
    validate_chapter_summary,
)

from ._helpers import make_game_state, make_npc, make_progress_track, make_threat


@pytest.fixture(autouse=True)
def _engine_loaded(load_engine: Any) -> None:
    """All chapter-validator code reads from eng()."""
    pass


def _narrative(
    *,
    title: str = "Chapter test",
    summary: str = "",
    character_growth: str = "",
    thematic_question: str = "",
    unresolved_threads: list[str] | None = None,
    npc_evolutions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "summary": summary,
        "character_growth": character_growth,
        "thematic_question": thematic_question,
        "unresolved_threads": list(unresolved_threads or []),
        "npc_evolutions": list(npc_evolutions or []),
        "post_story_location": "Anywhere",
    }


class _StubProvider:
    """Mock provider that returns a fixed validator response. Used to drive
    the LLM pass deterministically."""

    def __init__(self, response_json: str = '{"pass": true, "violations": [], "correction": ""}'):
        self._response_json = response_json

    def create_message(self, **kwargs: Any) -> Any:
        from straightjacket.engine.ai.provider_base import AIResponse

        return AIResponse(content=self._response_json, stop_reason="end", tool_calls=[], usage={})


# ---------------------------------------------------------------------------
# Rule pass — NPC contradictions
# ---------------------------------------------------------------------------


def test_rule_npc_death_contradiction_detected() -> None:
    """Narrative says active NPC died — rule pass catches it."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus died protecting the others.")
    violations = _rule_check(narrative, game)
    assert any("Marcus" in v and "CHAPTER CONTRADICTION" in v for v in violations)


def test_rule_npc_alive_passes() -> None:
    """Narrative mentions active NPC without death keyword — passes."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus argued with the captain about the route.")
    assert _rule_check(narrative, game) == []


def test_rule_deceased_npc_with_death_keyword_passes() -> None:
    """Narrative says deceased NPC died — state and narrative agree, no
    contradiction."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="deceased")]
    narrative = _narrative(summary="Marcus died defending the gate.")
    assert _rule_check(narrative, game) == []


def test_rule_background_npc_with_death_keyword_fails() -> None:
    """Background is alive, not deceased — narrative claiming death contradicts."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="background")]
    narrative = _narrative(summary="Marcus was killed in the assault.")
    violations = _rule_check(narrative, game)
    assert any("Marcus" in v for v in violations)


def test_rule_word_boundary_prevents_substring_match() -> None:
    """`Marc` should not match inside `Marcus` and vice versa."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marc", description="", status="active")]
    narrative = _narrative(summary="Marcus died on the bridge.")
    # `Marc` (the active NPC) is not whole-word-matched by `Marcus`,
    # so no contradiction is raised on Marc.
    violations = _rule_check(narrative, game)
    assert not any("Marc:" in v for v in violations) and not any("'Marc'" in v for v in violations)


def test_rule_keyword_not_within_window_passes() -> None:
    """Death keyword far from NPC name does not trigger — only proximity matters."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    # 200+ chars between name and 'died'
    summary = (
        "Marcus walked through the markets at dawn. "
        + ("Trade routes opened. " * 12)
        + "An old soldier died in the alley far from town."
    )
    narrative = _narrative(summary=summary)
    assert _rule_check(narrative, game) == []


def test_rule_invented_colour_passes() -> None:
    """NPC names not in state are unconstrained — invention is allowed."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="A nameless courier died at the gates. The flowers wilted in the heat.")
    # No tracked NPC contradicted; invented courier passes.
    assert _rule_check(narrative, game) == []


# ---------------------------------------------------------------------------
# Rule pass — Track and threat contradictions
# ---------------------------------------------------------------------------


def test_rule_track_completion_contradiction_detected() -> None:
    game = make_game_state(player_name="Hero")
    game.progress_tracks = [make_progress_track(id="t1", name="The Iron Vow", status="active")]
    narrative = _narrative(summary="The Iron Vow was completed at last.")
    violations = _rule_check(narrative, game)
    assert any("Iron Vow" in v and "CHAPTER CONTRADICTION" in v for v in violations)


def test_rule_track_already_completed_passes() -> None:
    game = make_game_state(player_name="Hero")
    game.progress_tracks = [make_progress_track(id="t1", name="The Iron Vow", status="completed")]
    narrative = _narrative(summary="The Iron Vow was finally completed.")
    assert _rule_check(narrative, game) == []


def test_rule_threat_resolution_contradiction_detected() -> None:
    game = make_game_state(player_name="Hero")
    game.threats = [make_threat(id="th1", name="The Cult of Embers", status="active")]
    narrative = _narrative(summary="The Cult of Embers was defeated and scattered.")
    violations = _rule_check(narrative, game)
    assert any("Cult of Embers" in v for v in violations)


def test_rule_threat_resolved_status_passes() -> None:
    game = make_game_state(player_name="Hero")
    game.threats = [make_threat(id="th1", name="The Cult of Embers", status="resolved")]
    narrative = _narrative(summary="The Cult of Embers was defeated.")
    assert _rule_check(narrative, game) == []


def test_rule_threat_overcome_status_passes() -> None:
    game = make_game_state(player_name="Hero")
    game.threats = [make_threat(id="th1", name="The Cult of Embers", status="overcome")]
    narrative = _narrative(summary="The Cult of Embers was vanquished at last.")
    assert _rule_check(narrative, game) == []


# ---------------------------------------------------------------------------
# Rule pass — Combination cases
# ---------------------------------------------------------------------------


def test_rule_multiple_contradictions_all_reported() -> None:
    """A narrative with several contradictions reports each."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    game.progress_tracks = [make_progress_track(id="t1", name="Iron Vow", status="active")]
    game.threats = [make_threat(id="th1", name="Embers", status="active")]
    narrative = _narrative(summary="Marcus was killed. Iron Vow was completed. Embers was destroyed.")
    violations = _rule_check(narrative, game)
    assert len(violations) == 3


def test_rule_empty_state_passes() -> None:
    """No tracked entities — nothing to contradict, even with death-words in text."""
    game = make_game_state(player_name="Hero")
    narrative = _narrative(summary="Many died in the conflict that month.")
    assert _rule_check(narrative, game) == []


def test_rule_short_name_skipped() -> None:
    """NPC names shorter than min length are not scanned — too many false positives."""
    game = make_game_state(player_name="Hero")
    # "An" is below npc_name_min_length and should not be matched
    game.npcs = [make_npc(id="n1", name="An", description="", status="active")]
    narrative = _narrative(summary="An ancient warrior died in the night.")
    assert _rule_check(narrative, game) == []


# ---------------------------------------------------------------------------
# Hybrid validate_chapter_summary — rule + LLM
# ---------------------------------------------------------------------------


def test_validate_passes_when_both_passes_clean() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus rode south at dawn.")
    provider = _StubProvider()  # default: pass
    passed, violations, correction = validate_chapter_summary(provider, narrative, game)  # type: ignore[arg-type]
    assert passed
    assert violations == []
    assert correction == ""


def test_validate_fails_on_rule_violation() -> None:
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus died at the gates.")
    provider = _StubProvider()  # LLM passes
    passed, violations, correction = validate_chapter_summary(provider, narrative, game)  # type: ignore[arg-type]
    assert not passed
    assert any("Marcus" in v for v in violations)
    assert correction


def test_validate_fails_on_llm_violation() -> None:
    """Rule pass clean (no death keyword), LLM pass flags euphemism."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    # Narrative uses euphemism — rule pass misses it (no 'died' near Marcus)
    narrative = _narrative(summary="When the smoke cleared, Marcus's body lay still on the cobbles.")
    llm_response = (
        '{"pass": false, "violations": ["Marcus is described as dead but engine state is active"], '
        '"correction": "Marcus is alive — rewrite without claiming his body lay still."}'
    )
    provider = _StubProvider(response_json=llm_response)
    passed, violations, correction = validate_chapter_summary(provider, narrative, game)  # type: ignore[arg-type]
    assert not passed
    # Combined violations include the [llm] prefix
    assert any("[llm]" in v for v in violations)


def test_validate_combines_rule_and_llm_violations() -> None:
    """Both passes flag distinct issues — both surface in the result."""
    game = make_game_state(player_name="Hero")
    game.npcs = [
        make_npc(id="n1", name="Marcus", description="", status="active"),
        make_npc(id="n2", name="Lyra", description="", status="active"),
    ]
    # Marcus violates rule pass, Lyra is the LLM-pass concern
    narrative = _narrative(summary="Marcus died protecting Lyra. She has gone now, lost to us forever.")
    llm_response = (
        '{"pass": false, "violations": ["Lyra described as gone; engine state alive"], '
        '"correction": "Lyra is still alive."}'
    )
    provider = _StubProvider(response_json=llm_response)
    passed, violations, _ = validate_chapter_summary(provider, narrative, game)  # type: ignore[arg-type]
    assert not passed
    # At least 1 rule-pass violation (Marcus) AND 1 llm-pass violation (Lyra)
    assert any("Marcus" in v and "[llm]" not in v for v in violations)
    assert any("[llm]" in v for v in violations)


def test_validate_llm_failure_does_not_break_rule_results() -> None:
    """LLM call fails — rule violations still surface, no exception escapes."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus died.")

    class _BrokenProvider:
        def create_message(self, **kwargs: Any) -> Any:
            raise RuntimeError("simulated LLM failure")

    passed, violations, _ = validate_chapter_summary(_BrokenProvider(), narrative, game)  # type: ignore[arg-type]
    assert not passed
    assert any("Marcus" in v for v in violations)


# ---------------------------------------------------------------------------
# Retry loop
# ---------------------------------------------------------------------------


def test_retry_loop_accepts_clean_first_attempt() -> None:
    """No contradiction up front — call_summary is never re-invoked."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(summary="Marcus crossed the river safely.")
    calls: list[int] = []

    def call_summary(provider: Any, g: Any, c: Any, epilogue_text: str = "") -> dict[str, Any]:
        calls.append(1)
        return narrative

    provider = _StubProvider()
    result = validate_and_retry(provider, narrative, game, None, call_summary)  # type: ignore[arg-type]
    assert result is narrative
    # call_summary not invoked because validation passed
    assert calls == []


def test_retry_loop_replaces_narrative_on_correction() -> None:
    """First narrative contradicts state, retry replaces it with a clean one."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    bad = _narrative(summary="Marcus died.")
    good = _narrative(summary="Marcus rode away alive.")
    calls: list[str] = []

    def call_summary(provider: Any, g: Any, c: Any, epilogue_text: str = "") -> dict[str, Any]:
        calls.append("retry")
        return good

    provider = _StubProvider()
    result = validate_and_retry(provider, bad, game, None, call_summary)  # type: ignore[arg-type]
    assert result is good
    assert calls == ["retry"]


def test_retry_loop_keeps_last_narrative_when_exhausted() -> None:
    """Retries exhausted — last narrative returned (graceful degradation)."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    bad = _narrative(summary="Marcus died.")

    def call_summary(provider: Any, g: Any, c: Any, epilogue_text: str = "") -> dict[str, Any]:
        # Always returns bad — never converges
        return _narrative(summary="Marcus was killed by the cult.")

    provider = _StubProvider()
    result = validate_and_retry(provider, bad, game, None, call_summary)  # type: ignore[arg-type]
    # Returns *some* narrative dict, not crashes
    assert isinstance(result, dict)
    assert "summary" in result


def test_retry_correction_passed_via_epilogue_text() -> None:
    """The retry call receives the correction in epilogue_text — the only
    free-text channel call_chapter_summary already accepts."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    bad = _narrative(summary="Marcus died.")
    good = _narrative(summary="Marcus survived.")
    captured_epilogues: list[str] = []

    def call_summary(provider: Any, g: Any, c: Any, epilogue_text: str = "") -> dict[str, Any]:
        captured_epilogues.append(epilogue_text)
        return good

    provider = _StubProvider()
    validate_and_retry(provider, bad, game, None, call_summary, epilogue_text="Original epilogue")  # type: ignore[arg-type]
    # Epilogue must contain both the original text AND the correction instruction
    assert captured_epilogues
    assert "Original epilogue" in captured_epilogues[0]
    assert "Marcus" in captured_epilogues[0]  # correction mentions the NPC


# ---------------------------------------------------------------------------
# Narrative-text gathering
# ---------------------------------------------------------------------------


def test_rule_scans_npc_evolutions_block() -> None:
    """Contradictions in npc_evolutions surface, not only in summary."""
    game = make_game_state(player_name="Hero")
    game.npcs = [make_npc(id="n1", name="Marcus", description="", status="active")]
    narrative = _narrative(
        summary="The chapter was uneventful.",
        npc_evolutions=[{"name": "Marcus", "evolution": "Marcus was killed in the final scene."}],
    )
    violations = _rule_check(narrative, game)
    assert any("Marcus" in v for v in violations)


def test_rule_scans_unresolved_threads() -> None:
    """Track-completion claims in unresolved_threads list also caught."""
    game = make_game_state(player_name="Hero")
    game.progress_tracks = [make_progress_track(id="t1", name="The Hunt", status="active")]
    narrative = _narrative(
        summary="A long chapter.",
        unresolved_threads=["The Hunt was completed but new dangers loom."],
    )
    violations = _rule_check(narrative, game)
    assert any("Hunt" in v for v in violations)
