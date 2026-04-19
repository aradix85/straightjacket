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

## What goes where

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module ownership table. The short version: if you want to change game rules, edit YAML, not Python. If you want to change AI behavior, edit prompts.yaml. If you need to touch Python, the architecture doc tells you which file owns what.

## Config-driven design

Game mechanics, emotion scoring, move types, damage tables, disposition shifts — all in YAML. The Python code reads config at runtime. Before adding a constant to Python, check if it belongs in the engine config (one yaml per subsystem under `engine/`) or emotions.yaml instead.

## Testing

Three layers of testing, complementary:

The **unit/integration test suite** (`python -m pytest tests/ -v`) runs without an API key. It uses mock providers that return canned responses. Tests verify the engine's internal logic: consequences, NPC processing, serialization, correction flow, prompt assembly, WebSocket handlers. Every PR must pass this suite.

**Elvira** (`tests/elvira/elvira.py`) is a headless AI-driven test player that plays the game with real API calls. It checks state invariants after every turn, validates narration quality (leaked mechanics, spatial consistency), stress-tests the correction pipeline, and logs everything to JSON. Two modes:

- Direct mode: `python tests/elvira/elvira.py --auto --turns 5` — drives the engine directly, bypasses the UI. Fastest way to test engine changes.
- WebSocket mode: `python tests/elvira/elvira.py --ws --auto --turns 5` — plays through the full server stack. Tests the complete pipeline: WebSocket protocol, handlers, engine, serializers.

If your change affects the turn pipeline, NPC processing, or prompt assembly, run Elvira. The unit tests catch logic bugs; Elvira catches constraint violations, narrator drift, and integration failures that only surface with real model output.

**Model eval** (`tests/model_eval/eval.py`) evaluates whether a model can handle a specific AI role. Tests each role in isolation with fixed inputs and expected outputs. Use before switching a cluster's model or overriding a role. Add `--role brain --model gpt-oss-120b` to test one role on one model. Test cases are in `tests/model_eval/cases.yaml` — add cases when you encounter a role-specific failure pattern.

Elvira configuration is in `tests/elvira/elvira_config.yaml`. Session logs go to `tests/elvira/elvira_session.json`. Add `--turns N` to control session length.

## Accessibility

This project is built by a blind developer. Screen reader accessibility is not optional. If you add UI elements: semantic HTML, ARIA live regions, heading structure, native form controls. No div-buttons, no spatial-only references.
