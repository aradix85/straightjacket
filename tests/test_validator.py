import json

from tests._helpers import make_game_state
from tests._mocks import MockProvider, MockResponse, make_test_game


def test_validate_narration_returns_violations(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = MockProvider(
        json.dumps({"pass": False, "violations": ["Silver lining on MISS"], "correction": "Make it worse."})
    )
    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = validate_narration(
        provider,
        "Bad narration.",
        ctx,
    )
    assert result["pass"] is False
    assert len(result["violations"]) == 1


def test_validate_narration_fail_open_on_api_error(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = MockProvider(fail=True)
    ctx = ValidationContext.build(make_game_state(), result_type="MISS")
    result = validate_narration(
        provider,
        "Text.",
        ctx,
    )
    assert result["pass"] is True


def test_validate_narration_catches_genre_violation_rule_based(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration
    from tests.conftest import make_genre_constraints

    provider = MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    gc = make_genre_constraints(forbidden_terms=["magic"])
    ctx = ValidationContext.build(make_game_state(), result_type="MISS", genre_constraints=gc)
    result = validate_narration(
        provider,
        "She cast a magic spell.",
        ctx,
    )
    assert result["pass"] is False
    assert any("magic" in v for v in result["violations"])


def test_validate_and_retry_actually_retries(stub_all: None) -> None:
    from straightjacket.engine.ai.validator import validate_and_retry

    call_count = [0]

    class RetryProvider:
        def create_message(
            self,
            model: str,
            system: str,
            messages: list,
            max_tokens: int,
            json_schema: dict | None = None,
            tools: list | None = None,
            temperature: float | None = None,
            top_p: float | None = None,
            top_k: int | None = None,
            extra_body: dict | None = None,
        ):
            call_count[0] += 1
            if json_schema and "pass" in json_schema.get("properties", {}):
                if call_count[0] <= 2:
                    return MockResponse(json.dumps({"pass": False, "violations": ["bad"], "correction": "fix it"}))
                return MockResponse(json.dumps({"pass": True, "violations": [], "correction": ""}))
            return MockResponse("Rewritten narration.")

    game = make_test_game()
    _, report = validate_and_retry(RetryProvider(), "Bad narration.", "prompt", "MISS", game, max_retries=2)
    assert report["retries"] >= 1
    assert len(report["checks"]) >= 2


def test_revelation_check_returns_false_when_not_confirmed(stub_all: None) -> None:
    from straightjacket.engine.ai.brain import call_revelation_check
    from straightjacket.engine.models_story import Revelation

    provider = MockProvider(json.dumps({"revelation_confirmed": False, "reasoning": "Absent."}))
    rev = Revelation(id="rev_1", content="The shadow is sentient", dramatic_weight="high")
    assert (
        call_revelation_check(
            provider,
            "The door opened.",
            rev,
        )
        is False
    )


def test_revelation_check_defaults_true_on_api_error(stub_all: None) -> None:
    from straightjacket.engine.ai.brain import call_revelation_check
    from straightjacket.engine.models_story import Revelation

    provider = MockProvider(fail=True)
    assert (
        call_revelation_check(
            provider,
            "Text.",
            Revelation(id="r", content="X"),
        )
        is True
    )


def test_consequence_compliance_block_skipped_on_strong_hit(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    ctx = ValidationContext.build(
        make_game_state(),
        result_type="STRONG_HIT",
        consequence_sentences=["Player finds an opening. The advantage shifts."],
    )
    validate_narration(provider, "Some narration.", ctx)
    sent_system = provider.calls[-1]["system"]
    assert "CONSEQUENCE COMPLIANCE" not in sent_system, (
        "CONSEQUENCE COMPLIANCE block must NOT be injected on STRONG_HIT — "
        "STRONG_HIT is clean success and demanding specific consequence phrasing produces false positives."
    )


def test_consequence_compliance_block_present_on_weak_hit(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    ctx = ValidationContext.build(
        make_game_state(),
        result_type="WEAK_HIT",
        consequence_sentences=["A specific cost is paid: equipment damaged."],
    )
    validate_narration(provider, "Some narration.", ctx)
    sent_system = provider.calls[-1]["system"]
    assert (
        "CONSEQUENCE COMPLIANCE" in sent_system
    ), "WEAK_HIT must keep the CONSEQUENCE COMPLIANCE block — costs/losses need to land in prose."


def test_consequence_compliance_block_present_on_miss(stub_all: None) -> None:
    from straightjacket.engine.ai.rule_validator import ValidationContext
    from straightjacket.engine.ai.validator import validate_narration

    provider = MockProvider(json.dumps({"pass": True, "violations": [], "correction": ""}))
    ctx = ValidationContext.build(
        make_game_state(),
        result_type="MISS",
        consequence_sentences=["Pay the price: lose 1 supply."],
    )
    validate_narration(provider, "Some narration.", ctx)
    sent_system = provider.calls[-1]["system"]
    assert "CONSEQUENCE COMPLIANCE" in sent_system
