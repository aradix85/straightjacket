#!/usr/bin/env python3
"""Tests for rule-based validator checks."""

from straightjacket.engine.ai.rule_validator import (
    check_genre_fidelity,
    check_npc_monologue,
    check_output_format,
    check_player_agency,
    check_result_integrity,
    run_rule_checks,
)
from tests._helpers import make_game_state


# ── PLAYER AGENCY ────────────────────────────────────────────


def test_agency_catches_you_feel_emotion() -> None:
    v = check_player_agency("You feel uneasy about the door.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_allows_you_feel_physical() -> None:
    v = check_player_agency("You feel the cold metal beneath your fingers.")
    assert len(v) == 0


def test_agency_catches_you_realize() -> None:
    v = check_player_agency("You realize the map was wrong all along.")
    assert any("realize" in x for x in v)


def test_agency_catches_you_remember() -> None:
    v = check_player_agency("You remember the old man's warning.")
    assert any("remember" in x for x in v)


def test_agency_catches_surge_of_dread() -> None:
    v = check_player_agency("A surge of dread washes over you.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_catches_something_in_you() -> None:
    v = check_player_agency("Something inside you shifts.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_clean_narration_passes() -> None:
    v = check_player_agency("The door hangs open. Cold air spills from the gap. Mud tracks lead inside, still wet.")
    assert len(v) == 0


# ── RESULT INTEGRITY ─────────────────────────────────────────


def test_miss_catches_at_least() -> None:
    v = check_result_integrity("The blade misses, but at least the door is still open.", "MISS")
    assert any("silver lining" in x for x in v)


def test_miss_catches_managed_to() -> None:
    v = check_result_integrity("You stumble but managed to keep your footing.", "MISS")
    assert any("silver lining" in x for x in v)


def test_miss_catches_annihilation() -> None:
    v = check_result_integrity("Your vision fades to nothing. Everything ends.", "MISS")
    assert any("annihilation" in x for x in v)


def test_miss_clean_failure_passes() -> None:
    v = check_result_integrity(
        "The rope snaps. You hit the water hard, the current dragging you under.",
        "MISS",
    )
    assert len(v) == 0


def test_strong_hit_not_checked_for_silver_lining() -> None:
    v = check_result_integrity("At least the door opened easily.", "STRONG_HIT")
    assert len(v) == 0  # Silver lining check only on MISS


# ── GENRE FIDELITY ───────────────────────────────────────────


def test_genre_catches_forbidden_term() -> None:
    from tests.conftest import make_genre_constraints

    gc = make_genre_constraints(forbidden_terms=["magic", "spell"])
    v = check_genre_fidelity("She whispered a spell under her breath.", gc)
    assert any("spell" in x for x in v)


def test_genre_passes_clean() -> None:
    from tests.conftest import make_genre_constraints

    gc = make_genre_constraints(forbidden_terms=["magic"])
    v = check_genre_fidelity("She drew the knife from its sheath.", gc)
    assert len(v) == 0


def test_genre_no_constraints_passes() -> None:
    v = check_genre_fidelity("Magic filled the air.", None)
    assert len(v) == 0


# ── OUTPUT FORMAT ────────────────────────────────────────────


def test_format_catches_narrator_prefix() -> None:
    v = check_output_format("Narrator: The room was dark.")
    assert any("role label" in x for x in v)


def test_format_catches_bracketed_annotation() -> None:
    v = check_output_format("The door opened. [CLOCK CREATED: Threat]")
    assert any("bracketed" in x for x in v)


def test_format_catches_code_block() -> None:
    v = check_output_format("```json\n{}\n```")
    assert any("code block" in x for x in v)


def test_format_clean_passes() -> None:
    v = check_output_format("\u201cGet back,\u201d she hissed, pulling the door shut.")
    assert len(v) == 0


# ── NPC MONOLOGUE ────────────────────────────────────────────


def test_monologue_catches_extended_speech() -> None:
    narration = (
        "\u201cFirst thing,\u201d she said. "
        "\u201cSecond thing.\u201d "
        "\u201cThird thing.\u201d "
        "\u201cFourth thing.\u201d "
        "\u201cFifth thing.\u201d"
    )
    v = check_npc_monologue(narration)
    assert any("monologue" in x for x in v)


def test_monologue_allows_dialog_exchange() -> None:
    narration = (
        "\u201cWhere is he?\u201d you ask, leaning against the bar. "
        "The bartender polishes a glass, eyes on the door. "
        "\u201cHaven\u2019t seen him since last week,\u201d he says. "
        "You push the coin across the counter. "
        "\u201cTry harder.\u201d"
    )
    v = check_npc_monologue(narration)
    assert len(v) == 0


# ── INTEGRATION ──────────────────────────────────────────────


def test_run_rule_checks_combines_violations() -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext

    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = run_rule_checks(
        narration="You feel a surge of dread. At least the torch still burns.",
        ctx=ctx,
    )
    assert not result["pass"]
    assert len(result["violations"]) >= 2


def test_run_rule_checks_clean_passes() -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext

    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = run_rule_checks(
        narration=(
            "The rope snaps. The current takes you, cold and fast. Your shoulder hits a rock and the pack tears free."
        ),
        ctx=ctx,
    )
    assert result["pass"]


# ── PROMPT STRIPPING ─────────────────────────────────────────


def test_strip_prompt_removes_secrets_on_pacing(load_engine: None) -> None:
    from straightjacket.engine.ai.validator import _strip_prompt_for_retry
    from straightjacket.engine.prompt_loader import get_prompt

    label = get_prompt("secrets_label")
    prompt = (
        '<target_npc name="Kira" disposition="friendly">\n'
        "agenda:Find the lost artifact\n"
        "instinct:deflects with humor\n"
        "recent: Saw the player arrive(curious)\n"
        f'secrets({label}):["she is the spy"]\n'
        "</target_npc>"
    )
    result = _strip_prompt_for_retry(prompt, ["RESOLUTION PACING: NPC volunteered too much"])
    assert "she is the spy" not in result
    assert "Kira" in result  # Name preserved
    assert "deflects with humor" in result  # Instinct preserved


def test_strip_prompt_unchanged_for_agency_violation(load_engine: None) -> None:
    from straightjacket.engine.ai.validator import _strip_prompt_for_retry
    from straightjacket.engine.prompt_loader import get_prompt

    label = get_prompt("secrets_label")
    prompt = f'<target_npc>secrets({label}):["secret"]</target_npc>'
    result = _strip_prompt_for_retry(prompt, ["PLAYER AGENCY: narrator decided feelings"])
    assert "secret" in result  # Not stripped for non-pacing violations


# ── CONSEQUENCE KEYWORD CHECKS ───────────────────────────────


def test_consequence_keyword_found() -> None:
    from straightjacket.engine.ai.rule_validator import check_consequence_keywords

    narration = "The blade finds the gap. Ash staggers, blood running down."
    sentences = ["The blade finds the gap in your guard."]
    violations = check_consequence_keywords(narration, sentences)
    assert violations == []


def test_consequence_keyword_missing() -> None:
    from straightjacket.engine.ai.rule_validator import check_consequence_keywords

    narration = "The sun shines brightly over the meadow."
    sentences = ["The blade finds the gap in your guard."]
    violations = check_consequence_keywords(narration, sentences)
    assert len(violations) == 1
    assert "CONSEQUENCE MISSING" in violations[0]


def test_consequence_empty_sentences_passes() -> None:
    from straightjacket.engine.ai.rule_validator import check_consequence_keywords

    violations = check_consequence_keywords("anything", [])
    assert violations == []


def test_consequence_in_run_rule_checks() -> None:
    """Consequence checking moved to LLM validator — rule checker passes these through."""
    from straightjacket.engine.ai.rule_validator import ValidationContext, run_rule_checks

    narration = "The sun shines. Nothing happened."
    ctx = ValidationContext.build(
        make_game_state(), result_type="MISS", consequence_sentences=["The blade finds the gap in your guard."]
    )
    result = run_rule_checks(narration, ctx)
    # Rule checker no longer checks consequences — LLM validator handles semantic matching
    assert result["pass"]
