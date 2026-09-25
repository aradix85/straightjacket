from __future__ import annotations

from typing import Any

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse, stream_with_retry
from straightjacket.engine.ai.sentence_stream import SentenceStream


def _collect(*chunks: str, finish: bool = True) -> tuple[list[str], SentenceStream]:
    sentences: list[str] = []
    stream = SentenceStream(sentences.append)
    for chunk in chunks:
        stream.feed(chunk)
    if finish:
        stream.finish()
    return sentences, stream


def test_emits_whole_sentences_in_order_across_chunks(load_engine: None) -> None:
    sentences, stream = _collect("The door ", "holds. Mira", " waits! Then", " the lamp dies.")
    assert sentences == ["The door holds.", "Mira waits!", "Then the lamp dies."]
    assert stream.complete


def test_the_last_sentence_waits_for_finish(load_engine: None) -> None:
    sentences, _ = _collect("Rain falls. It keeps falling", finish=False)
    assert sentences == ["Rain falls."]


def test_abbreviations_do_not_end_a_sentence(load_engine: None) -> None:
    sentences, _ = _collect("Dr. Venn arrives late. The hall is empty.")
    assert sentences == ["Dr. Venn arrives late.", "The hall is empty."]


def test_closing_quote_stays_with_its_sentence(load_engine: None) -> None:
    sentences, _ = _collect('She says, "Run." Then silence.')
    assert sentences == ['She says, "Run."', "Then silence."]


def test_a_paragraph_break_ends_a_sentence(load_engine: None) -> None:
    sentences, _ = _collect("The shutter bangs\n\nSomewhere, a dog barks.")
    assert sentences == ["The shutter bangs", "Somewhere, a dog barks."]


def test_a_hold_marker_stops_the_stream(load_engine: None) -> None:
    sentences, stream = _collect("Clean prose here. <game_data>{}</game_data>")
    assert sentences == ["Clean prose here."]
    assert stream.held
    assert not stream.complete


def test_a_failed_stream_is_not_complete_and_stops_emitting(load_engine: None) -> None:
    sentences: list[str] = []
    stream = SentenceStream(sentences.append)
    stream.feed("One. ")
    stream.fail()
    stream.feed("Two. ")
    stream.finish()
    assert sentences == ["One."]
    assert not stream.complete


class _Plain:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        return AIResponse(content="Whole reply arrives at once.")


class _Broken:
    def create_message(self, spec: AICallSpec) -> AIResponse:
        return AIResponse(content="Recovered without streaming.")

    def stream_message(self, spec: AICallSpec, on_text: Any) -> AIResponse:
        on_text("Half a sent")
        raise ConnectionError("stream dropped")


def _spec() -> AICallSpec:
    return AICallSpec(model="m", system="s", messages=[], max_tokens=8, log_role="narrator")


def test_stream_with_retry_feeds_a_non_streaming_provider_at_once(load_engine: None) -> None:
    sentences: list[str] = []
    stream = SentenceStream(sentences.append)
    response = stream_with_retry(_Plain(), _spec(), stream)
    assert response.content == "Whole reply arrives at once."
    assert sentences == ["Whole reply arrives at once."]
    assert stream.complete


def test_stream_with_retry_falls_back_and_marks_the_stream_incomplete(load_engine: None) -> None:
    stream = SentenceStream(lambda text: None)
    response = stream_with_retry(_Broken(), _spec(), stream)
    assert response.content == "Recovered without streaming."
    assert stream.failed
    assert not stream.complete


def test_a_literal_unicode_escape_split_across_chunks_streams_as_the_character(load_engine: None) -> None:
    from straightjacket.engine.ai.sentence_stream import SentenceStream

    sentences: list[str] = []
    stream = SentenceStream(sentences.append)
    for delta in ("The raider laughs. \\u20", "1cRun.\\u201d", " Then she is gone.", "\n"):
        stream.feed(delta)
    stream.finish()
    spoken = " ".join(sentences)
    assert "\\u" not in spoken
    assert "\u201cRun.\u201d" in spoken
