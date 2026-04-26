def test_extract_json_clean_object() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_whitespace() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    assert extract_json('  \n  {"a": 1}  \n  ') == {"a": 1}


def test_extract_json_in_code_fence() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    text = 'Some text\n```json\n{"key": "value"}\n```\nmore text'
    assert extract_json(text) == {"key": "value"}


def test_extract_json_in_bare_fence() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    text = 'preamble\n```\n{"key": 42}\n```'
    assert extract_json(text) == {"key": 42}


def test_extract_json_embedded_in_text() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    text = 'Here is the result: {"answer": "yes"} and that is all.'
    assert extract_json(text) == {"answer": "yes"}


def test_extract_json_returns_none_on_no_json() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    assert extract_json("just plain text with no braces") is None


def test_extract_json_returns_none_on_invalid_json() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    assert extract_json("{not valid json}") is None


def test_extract_json_returns_none_on_unmatched_brace() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    assert extract_json("{ no closing") is None


def test_extract_json_falls_through_when_object_not_at_start_invalid() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    text = "preamble {invalid} suffix"
    assert extract_json(text) is None


def test_extract_json_picks_outermost_braces() -> None:
    from straightjacket.engine.ai.json_utils import extract_json

    text = 'preamble {"key": {"nested": 1}} suffix'
    result = extract_json(text)
    assert result == {"key": {"nested": 1}}
