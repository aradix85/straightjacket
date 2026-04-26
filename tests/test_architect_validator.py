import json

from tests._mocks import MockProvider


def test_validate_architect_fixes_violations(stub_all: None) -> None:
    from straightjacket.engine.ai.architect_validator import validate_architect
    from tests.conftest import make_genre_constraints

    provider = MockProvider(
        json.dumps(
            {
                "pass": False,
                "violations": ["magic detected"],
                "fixed_conflict": "Political conspiracy",
                "fixed_antagonist": "Corrupt senator",
            }
        )
    )
    bp = {"central_conflict": "Magic war", "antagonist_force": "Evil wizard"}
    gc = make_genre_constraints(forbidden_terms=["magic"])
    result = validate_architect(
        provider,
        bp,
        "realistic",
        "serious",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Political conspiracy"
    assert result["antagonist_force"] == "Corrupt senator"


def test_validate_architect_fail_open_on_api_error(stub_all: None) -> None:
    from straightjacket.engine.ai.architect_validator import validate_architect
    from tests.conftest import make_genre_constraints

    provider = MockProvider(fail=True)
    bp = {"central_conflict": "Original", "antagonist_force": "Original"}
    gc = make_genre_constraints(forbidden_terms=["x"])
    result = validate_architect(
        provider,
        bp,
        "genre",
        "tone",
        genre_constraints=gc,
    )
    assert result["central_conflict"] == "Original"
