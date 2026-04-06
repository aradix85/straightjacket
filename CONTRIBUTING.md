# Contributing

## Quick version

1. Fork, branch, make your change
2. `python -m pytest tests/ -v` — all 205 tests must pass
3. `ruff check src/` — must be clean
4. `mypy src/straightjacket/ --config-file pyproject.toml` — must be clean
5. PR with a clear description of what and why

## Code standards

Python 3.11+. Dataclasses with type hints. f-strings. pathlib. snake_case. No mutable defaults. Imports sorted, top of file. Max line length 120 (ruff handles this).

Read `pyproject.toml` for the full ruff/mypy config. The linter rules are the spec — if ruff passes, you're fine.

## What goes where

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module ownership table. The short version: if you want to change game rules, edit YAML, not Python. If you want to change AI behavior, edit prompts.yaml. If you need to touch Python, the architecture doc tells you which file owns what.

## Config-driven design

Game mechanics, emotion scoring, move types, damage tables, disposition shifts — all in YAML. The Python code reads config at runtime. Before adding a constant to Python, check if it belongs in engine.yaml or emotions.yaml instead.

## Testing

One test per flow, not per assertion. A test should be capable of breaking when real code changes. No tests for Python builtins, trivial roundtrips, or config value assertions.

If your change affects the turn pipeline, run Elvira: `python elvira/elvira.py --auto --turns 5` (needs an API key).

## Accessibility

This project is built by a blind developer. Screen reader accessibility is not optional. If you add UI elements: ARIA labels, keyboard navigation, no spatial-only references.
