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


# ── PLAYER AGENCY ────────────────────────────────────────────

def test_agency_catches_you_feel_emotion():
    v = check_player_agency("You feel uneasy about the door.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_allows_you_feel_physical():
    v = check_player_agency("You feel the cold metal beneath your fingers.")
    assert len(v) == 0


def test_agency_catches_you_realize():
    v = check_player_agency("You realize the map was wrong all along.")
    assert any("realize" in x for x in v)


def test_agency_catches_you_remember():
    v = check_player_agency("You remember the old man's warning.")
    assert any("remember" in x for x in v)


def test_agency_catches_surge_of_dread():
    v = check_player_agency("A surge of dread washes over you.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_catches_something_in_you():
    v = check_player_agency("Something inside you shifts.")
    assert any("PLAYER AGENCY" in x for x in v)


def test_agency_clean_narration_passes():
    v = check_player_agency(
        "The door hangs open. Cold air spills from the gap. "
        "Mud tracks lead inside, still wet."
    )
    assert len(v) == 0


# ── RESULT INTEGRITY ─────────────────────────────────────────

def test_miss_catches_at_least():
    v = check_result_integrity("The blade misses, but at least the door is still open.", "MISS")
    assert any("silver lining" in x for x in v)


def test_miss_catches_managed_to():
    v = check_result_integrity("You stumble but managed to keep your footing.", "MISS")
    assert any("silver lining" in x for x in v)


def test_miss_catches_annihilation():
    v = check_result_integrity("Your vision fades to nothing. Everything ends.", "MISS")
    assert any("annihilation" in x for x in v)


def test_miss_clean_failure_passes():
    v = check_result_integrity(
        "The rope snaps. You hit the water hard, the current dragging you under.",
        "MISS",
    )
    assert len(v) == 0


def test_strong_hit_not_checked_for_silver_lining():
    v = check_result_integrity("At least the door opened easily.", "STRONG_HIT")
    assert len(v) == 0  # Silver lining check only on MISS


# ── GENRE FIDELITY ───────────────────────────────────────────

def test_genre_catches_forbidden_term():
    gc = {"forbidden_terms": ["magic", "spell"]}
    v = check_genre_fidelity("She whispered a spell under her breath.", gc)
    assert any("spell" in x for x in v)


def test_genre_passes_clean():
    gc = {"forbidden_terms": ["magic"]}
    v = check_genre_fidelity("She drew the knife from its sheath.", gc)
    assert len(v) == 0


def test_genre_no_constraints_passes():
    v = check_genre_fidelity("Magic filled the air.", None)
    assert len(v) == 0


# ── OUTPUT FORMAT ────────────────────────────────────────────

def test_format_catches_narrator_prefix():
    v = check_output_format("Narrator: The room was dark.")
    assert any("role label" in x for x in v)


def test_format_catches_bracketed_annotation():
    v = check_output_format("The door opened. [CLOCK CREATED: Threat]")
    assert any("bracketed" in x for x in v)


def test_format_catches_code_block():
    v = check_output_format("```json\n{}\n```")
    assert any("code block" in x for x in v)


def test_format_clean_passes():
    v = check_output_format("\u201cGet back,\u201d she hissed, pulling the door shut.")
    assert len(v) == 0


# ── NPC MONOLOGUE ────────────────────────────────────────────

def test_monologue_catches_extended_speech():
    narration = (
        '\u201cFirst thing,\u201d she said. '
        '\u201cSecond thing.\u201d '
        '\u201cThird thing.\u201d '
        '\u201cFourth thing.\u201d '
        '\u201cFifth thing.\u201d'
    )
    v = check_npc_monologue(narration)
    assert any("monologue" in x for x in v)


def test_monologue_allows_dialog_exchange():
    narration = (
        '\u201cWhere is he?\u201d you ask, leaning against the bar. '
        'The bartender polishes a glass, eyes on the door. '
        '\u201cHaven\u2019t seen him since last week,\u201d he says. '
        'You push the coin across the counter. '
        '\u201cTry harder.\u201d'
    )
    v = check_npc_monologue(narration)
    assert len(v) == 0


# ── INTEGRATION ──────────────────────────────────────────────

def test_run_rule_checks_combines_violations():
    result = run_rule_checks(
        narration="You feel a surge of dread. At least the torch still burns.",
        result_type="MISS",
    )
    assert not result["pass"]
    assert len(result["violations"]) >= 2


def test_run_rule_checks_clean_passes():
    result = run_rule_checks(
        narration=(
            "The rope snaps. The current takes you, cold and fast. "
            "Your shoulder hits a rock and the pack tears free."
        ),
        result_type="MISS",
    )
    assert result["pass"]


# ── PROMPT STRIPPING ─────────────────────────────────────────

def test_strip_prompt_removes_secrets_on_pacing_violation():
    from straightjacket.engine.ai.validator import _strip_prompt_for_retry
    prompt = (
        '<target_npc name="Kira" disposition="friendly">\n'
        'agenda:Find the lost artifact\n'
        'instinct:deflects with humor\n'
        'recent: Saw the player arrive(curious)\n'
        'secrets(weave subtly,never reveal):["she is the spy"]\n'
        '</target_npc>'
    )
    result = _strip_prompt_for_retry(prompt, ["RESOLUTION PACING: NPC volunteered too much"])
    assert "she is the spy" not in result
    assert "Kira" in result  # Name preserved
    assert "deflects with humor" in result  # Instinct preserved


def test_strip_prompt_unchanged_for_agency_violation():
    from straightjacket.engine.ai.validator import _strip_prompt_for_retry
    prompt = '<target_npc>secrets(weave subtly,never reveal):["secret"]</target_npc>'
    result = _strip_prompt_for_retry(prompt, ["PLAYER AGENCY: narrator decided feelings"])
    assert "secret" in result  # Not stripped for non-pacing violations
