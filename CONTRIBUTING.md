# Contributing

## Quick version

1. Fork, branch, make your change
2. `ruff check --fix src/ tests/` and `ruff format src/` — must be clean
3. `python -m pytest tests/ -q` — all tests must pass
4. `mypy src/ --config-file pyproject.toml` — must be clean
5. PR with a clear description of what and why

## Code standards

Python 3.11+. Dataclasses with type hints. f-strings. pathlib. snake_case. No mutable defaults. Imports sorted, top of file. Max line length 120 (ruff handles this).

Read `pyproject.toml` for the full ruff/mypy config. The linter rules are the spec — if ruff passes, you're fine.

## Project rules

These rules apply across the codebase. They are enforced mechanically by `tests/test_project_rules.py` and consciously upheld in review. They exist because every shortcut Python's defaulting and exception-swallowing make tempting eventually hides a real bug.

**Domain config keys raise on miss.** Engine config is read by direct subscript (`config["key"]`). No `dict.get` with a literal fallback. No `x or "fallback"`. No dataclass defaults on fields that bind to a config value. If a key is missing, the engine should fail loudly, not silently substitute a value the rest of the code wasn't designed for.

Three exceptions survive: language-mandated empty collections (`field(default_factory=list)`), parsing of variable external structures (Datasworn JSON, AI-returned JSON, WebSocket client input), and the AI-call carve-out below. Each non-language case carries a one-line policy comment at the callsite.

**User-, narrator-, and AI-readable strings live in config or prompt files.** Not hardcoded in Python. `engine/*.yaml`, `prompts/*.yaml`, `strings/*.yaml`, and `emotions/*.yaml` are the homes. Adding a constant to Python should be a last resort with a written reason.

**Errors propagate.** No broad `except Exception: pass`, no `contextlib.suppress` over domain logic. The carve-out is AI-call sites and tool-boundary functions returning structured error dicts to an AI caller — those carry a one-line policy comment pointing back to `provider_base.py`'s module docstring, and the broad catch is logged at warning level.

**No backwards compatibility.** Saves break when the code requires it. No migration layers, no default-on-old-fields, no ignore-unknown-fields. This is by design for an alpha project with no production users; if it changes, it changes deliberately, not silently.

**Update every caller in the same commit.** When a function signature, dataclass field, or yaml key changes, fix the callers immediately. Delete legacy code rather than retire it. Two-sided removal: a symbol is removed only when both code-side and config-side are dead — no readers, no writers beyond the definition.

When you touch a file that already has violations, fix them in the same commit. The project-rule tests measure residual debt; their failures aren't blocking, but they aren't ignorable either.

## What goes where

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module ownership table. The short version: if you want to change game rules, edit YAML, not Python. If you want to change AI behavior, edit prompts.yaml. If you need to touch Python, the architecture doc tells you which file owns what.

Three places carry model-specific content, all addressed by a `(role, model_family)` lookup with a universal fallback. The system is config-driven: adding a new model family is a yaml-only edit.

- **Prompts.** `prompts/{file}.yaml`. A bare key (`narrator_system`) is the universal variant; `narrator_system_glm` overrides for narrator runs on a GLM-family model. The loader prefers the family-specific key, falls back to bare when absent.
- **Validator regex.** `engine/validator.yaml`. Each pattern set has a required `*_universal` list and a required `*_overlays` dict (may be empty). Family wordlists go under the dict keyed by family suffix.
- **Atmospheric drift wordlists.** `data/settings/{setting}.yaml` under `genre_constraints`. Same shape: `atmospheric_drift_universal` + `atmospheric_drift_overlays`.

When adding a new model: register it in `config.yaml` under both `ai.clusters.<cluster>.model` and `ai.model_family`. Unmapped models raise — no silent fallback. To ship a model-specific variant, add the variant under the relevant overlays dict; no Python edit needed.

## Config-driven design

Game mechanics, emotion scoring, move types, damage tables, disposition shifts — all in YAML. The Python code reads config at runtime. Before adding a constant to Python, check if it belongs in the engine config (one yaml per subsystem under `engine/`) or emotions.yaml instead.

## Testing

Four layers of testing, complementary:

The **unit/integration test suite** (`python -m pytest tests/ -v`) runs without an API key. It uses mock providers that return canned responses. Tests verify the engine's internal logic: consequences, NPC processing, serialization, correction flow, prompt assembly, WebSocket handlers. Every PR must pass this suite.

**Project rules** (`tests/test_project_rules.py`) are eleven AST/regex scans that enforce the rules described in the Project rules section above. Failures are deterministic measurements — the tests fail on residual debt without blocking feature work. When you touch a file that already has violations, fix them in the same commit.

**Elvira** (`tests/elvira/elvira.py`) is a headless AI-driven test player that plays the game with real API calls. It checks state invariants after every turn (including NPC-DB sync and combat-track sync), validates narration quality (leaked mechanics, spatial consistency), stress-tests the correction pipeline, runs post-run drift checks (validator balance, blueprint drift), and logs everything to a single `elvira_session.json`. Two modes:

- Direct mode: `python tests/elvira/elvira.py --auto --turns 5` — drives the engine directly, bypasses the UI. Fastest way to test engine changes.
- WebSocket mode: `python tests/elvira/elvira.py --ws --auto --turns 5` — plays through the full server stack. Tests the complete pipeline: WebSocket protocol, handlers, engine, serializers.

If your change affects the turn pipeline, NPC processing, or prompt assembly, run Elvira. The unit tests catch logic bugs; Elvira catches constraint violations, narrator drift, and integration failures that only surface with real model output.

**Model eval** (`tests/model_eval/eval.py`) evaluates whether a model can handle a specific AI role. Tests each role in isolation with fixed inputs and expected outputs. Use before switching a cluster's model or overriding a role. Add `--role brain --model gpt-oss-120b` to test one role on one model. Test cases are in `tests/model_eval/cases.yaml` — add cases when you encounter a role-specific failure pattern.

Elvira configuration is in `tests/elvira/elvira_config.yaml`. Session logs go to `tests/elvira/elvira_session.json`. Add `--turns N` to control session length.

## Accessibility

This project is built by a blind developer. Screen reader accessibility is not optional. If you add UI elements: semantic HTML, ARIA live regions, heading structure, native form controls. No div-buttons, no spatial-only references.
