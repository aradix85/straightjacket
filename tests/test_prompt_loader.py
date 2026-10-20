from pathlib import Path

import pytest

from straightjacket.engine import prompt_loader
from straightjacket.engine.config_loader import cfg


@pytest.fixture
def prompts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    prompts_file = tmp_path / cfg().ai.prompts_dir / "test.yaml"
    prompts_file.parent.mkdir(parents=True)
    monkeypatch.setattr(prompt_loader, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prompt_loader, "_prompts", None)
    return prompts_file


def test_a_prompt_comes_back_filled_with_its_variables(prompts: Path) -> None:
    prompts.write_text('narrator_system: "BASE"\ntask_action: "Write {n} paragraphs."\n', encoding="utf-8")
    assert prompt_loader.get_prompt("narrator_system") == "BASE"
    assert prompt_loader.get_prompt("task_action", n="3") == "Write 3 paragraphs."


def test_an_unknown_prompt_raises(prompts: Path) -> None:
    prompts.write_text('narrator_system: "BASE"\n', encoding="utf-8")
    with pytest.raises(KeyError, match="does_not_exist"):
        prompt_loader.get_prompt("does_not_exist")


def test_a_prompt_raises_for_a_variable_it_was_not_given(prompts: Path) -> None:
    prompts.write_text('task_action: "Write {n} paragraphs in {lang}."\n', encoding="utf-8")
    with pytest.raises(KeyError, match="lang"):
        prompt_loader.get_prompt("task_action", n="3")


def test_a_prompt_that_is_not_text_stops_loading(prompts: Path) -> None:
    prompts.write_text('a: "text"\nb: [1]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="'b'"):
        prompt_loader.get_prompt("a")


def test_a_prompt_prefix_stops_at_the_named_placeholder(prompts: Path) -> None:
    prompts.write_text('sys: "Rules for {lang}.\\n{state}\\nEnd."\nplain: "Rules."\n', encoding="utf-8")
    assert prompt_loader.get_prompt_prefix("sys", "state", lang="English") == "Rules for English.\n"
    with pytest.raises(KeyError, match="no placeholder"):
        prompt_loader.get_prompt_prefix("plain", "state")
