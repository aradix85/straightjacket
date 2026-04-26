"""Tests for the prompt loader's (role, model_family) resolution.

Covers the role-aware lookup added on top of the bare-name lookup:
- Variant `{name}_{family}` wins when present.
- Bare `{name}` is used when variant absent.
- Both absent raises KeyError naming both keys tried.
- Bare-name path (no role) preserved for sub-blocks.
"""

import pytest

from straightjacket.engine import prompt_loader


@pytest.fixture(autouse=True)
def _isolate_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test installs its own prompt set; reset between tests."""
    monkeypatch.setattr(prompt_loader, "_prompts", None)


def _install_prompts(monkeypatch: pytest.MonkeyPatch, prompts: dict[str, str]) -> None:
    """Inject a fixed prompts dict, bypassing yaml load."""
    monkeypatch.setattr(prompt_loader, "_prompts", dict(prompts))


def _stub_family(monkeypatch: pytest.MonkeyPatch, family: str) -> None:
    """Stub model_family_for_role inside prompt_loader to a fixed family."""
    monkeypatch.setattr(prompt_loader, "model_family_for_role", lambda role: family)


def test_get_prompt_no_role_resolves_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"narrator_system": "BASE"})
    assert prompt_loader.get_prompt("narrator_system") == "BASE"


def test_get_prompt_no_role_unknown_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {})
    with pytest.raises(KeyError, match="Unknown prompt"):
        prompt_loader.get_prompt("does_not_exist")


def test_get_prompt_with_role_prefers_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"narrator_system": "BASE", "narrator_system_glm": "GLM_VARIANT"})
    _stub_family(monkeypatch, "glm")
    assert prompt_loader.get_prompt("narrator_system", role="narrator") == "GLM_VARIANT"


def test_get_prompt_with_role_falls_back_to_bare(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the family-specific variant is absent, the bare name still serves."""
    _install_prompts(monkeypatch, {"narrator_system": "BASE"})
    _stub_family(monkeypatch, "glm")
    assert prompt_loader.get_prompt("narrator_system", role="narrator") == "BASE"


def test_get_prompt_with_role_both_absent_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"unrelated": "x"})
    _stub_family(monkeypatch, "glm")
    with pytest.raises(KeyError, match="narrator_system_glm.*narrator_system"):
        prompt_loader.get_prompt("narrator_system", role="narrator")


def test_get_prompt_with_role_template_variables_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_prompts(monkeypatch, {"task_action": "Write {n} paragraphs."})
    _stub_family(monkeypatch, "glm")
    out = prompt_loader.get_prompt("task_action", role="narrator", n="3")
    assert out == "Write 3 paragraphs."


def test_get_prompt_with_role_variant_takes_its_own_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variant has its own template; bare-name template is ignored when variant present."""
    _install_prompts(
        monkeypatch,
        {"task_action": "BASE: {n} paragraphs.", "task_action_glm": "GLM: {n} paragraphs."},
    )
    _stub_family(monkeypatch, "glm")
    out = prompt_loader.get_prompt("task_action", role="narrator", n="2")
    assert out == "GLM: 2 paragraphs."


def test_get_prompt_role_resolves_per_role_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two different roles with two different families pick different variants."""
    _install_prompts(
        monkeypatch,
        {
            "validator_system": "BASE",
            "validator_system_gpt_oss": "GPTOSS",
        },
    )
    # Map narrator -> glm, validator -> gpt_oss
    monkeypatch.setattr(
        prompt_loader,
        "model_family_for_role",
        lambda role: {"narrator": "glm", "validator": "gpt_oss"}[role],
    )
    # narrator has no variant, falls back
    assert prompt_loader.get_prompt("validator_system", role="narrator") == "BASE"
    # validator has the gpt_oss variant
    assert prompt_loader.get_prompt("validator_system", role="validator") == "GPTOSS"
