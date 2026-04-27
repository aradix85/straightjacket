import pytest

from straightjacket.engine import prompt_loader


@pytest.fixture(autouse=True)
def _isolate_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_loader, "_prompts", None)


def _install_prompts(monkeypatch: pytest.MonkeyPatch, prompts: dict[str, str]) -> None:
    monkeypatch.setattr(prompt_loader, "_prompts", dict(prompts))


def test_get_prompt_resolves_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"narrator_system": "BASE"})
    assert prompt_loader.get_prompt("narrator_system") == "BASE"


def test_get_prompt_unknown_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {})
    with pytest.raises(KeyError, match="Unknown prompt"):
        prompt_loader.get_prompt("does_not_exist")


def test_get_prompt_template_variables_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"task_action": "Write {n} paragraphs."})
    out = prompt_loader.get_prompt("task_action", n="3")
    assert out == "Write 3 paragraphs."
