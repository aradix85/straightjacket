from collections.abc import Callable

from straightjacket.engine.ai.provider_base import AICallSpec, AIResponse


class _Recorder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: list[AICallSpec] = []

    def create_message(self, spec: AICallSpec) -> AIResponse:
        self.seen.append(spec)
        return AIResponse(content=self.name, usage={"input_tokens": 1, "output_tokens": 1})

    def stream_message(self, spec: AICallSpec, on_text: Callable[[str], None]) -> AIResponse:
        self.seen.append(spec)
        on_text(self.name)
        return AIResponse(content=self.name, usage={"input_tokens": 1, "output_tokens": 1})


def _spec(role: str) -> AICallSpec:
    return AICallSpec(
        model="engine-model", system="s", messages=[], max_tokens=10, extra_body={"engine": True}, log_role=role
    )


def test_only_narration_goes_to_the_chosen_narrator() -> None:
    from tests.elvira.elvira_bot.narrator_swap import NarratorSwap

    engine, narrator = _Recorder("engine"), _Recorder("narrator")
    swap = NarratorSwap(engine, narrator, "chosen-model", {"reasoning_effort": "low"})
    assert swap.create_message(_spec("brain")).content == "engine"
    assert swap.create_message(_spec("narrator")).content == "narrator"
    streamed: list[str] = []
    assert swap.stream_message(_spec("narrator"), streamed.append).content == "narrator"
    assert swap.stream_message(_spec("director"), streamed.append).content == "engine"
    assert streamed == ["narrator", "engine"]
    assert [s.model for s in narrator.seen] == ["chosen-model", "chosen-model"]
    assert all(s.extra_body == {"reasoning_effort": "low"} for s in narrator.seen)
    assert [s.model for s in engine.seen] == ["engine-model", "engine-model"]
    assert all(s.extra_body == {"engine": True} for s in engine.seen)


def test_every_role_moves_to_the_chosen_model() -> None:
    from tests.elvira.elvira_bot.narrator_swap import ALL_ROLES, ModelSwap

    engine, candidate = _Recorder("engine"), _Recorder("candidate")
    swap = ModelSwap(engine, candidate, "candidate-model", {"reasoning_effort": "low"}, ALL_ROLES)
    for role in ("brain", "narrator", "director", "narrator_metadata"):
        assert swap.create_message(_spec(role)).content == "candidate"
    assert engine.seen == []
    assert {s.model for s in candidate.seen} == {"candidate-model"}
