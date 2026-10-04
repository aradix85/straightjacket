# Contributing

How to change Straightjacket: the workflow, the rules every change keeps, the code standards, and the tests. ARCHITECTURE.md explains how the code is organised.

## Workflow

1. `ruff check --fix src/ tests/` and `ruff format src/ tests/`: must be clean.
2. `python -m pytest tests/ -q --cov`: every test passes, and total coverage stays at or above `fail_under` in `pyproject.toml` (`[tool.coverage.report]`). When the total passes the next whole percent, raise `fail_under` to it; never lower it.
3. `mypy src/ --config-file pyproject.toml`: must be clean.
4. A change to the turn pipeline, AI calls, prompts, or configuration first gets a short Elvira run (8 to 20 turns, `docs/elvira.md`), and every engine warning in its report is a finding.
5. One CHANGELOG entry per finished piece of work, not one per measurement, and only after its checks have been read: what changed, why, what was measured, and the quality gate, in a few sentences. The version in `pyproject.toml` matches the newest entry.

An outside contributor forks, branches, and opens a pull request that says what changed and why. The maintainer's sessions commit each finished release to main and push it.

## Rules for a change

**Scope includes what the work surfaces.** A bug or rule violation in a file you touch is fixed in the same change: silent fallbacks, hardcoded domain strings, broad excepts outside the carve-out, dataclass defaults on config fields, inline imports outside the whitelist in `tests/test_project_rules.py`, comments or docstrings, documentation the change makes wrong, and test hygiene (random.seed without teardown, leaked module state). Stop and ask only when a fix needs an architectural decision you cannot take, or pulls in an unrelated subsystem. A TODO is not a fix, and neither is "noted for later".

**Tests are not the spec.** Code leads; tests check that it meets the intended behaviour, the project rules, and the architecture. When a correct change breaks a test, read the test first. It tested the behaviour the change replaces (rewrite it), an assumption that never held, such as the same hardcoded value as production (remove or replace it), or something now defined elsewhere (update its setup). Only rarely does it show that production is wrong. Never change code just to turn a test green, never skip or xfail, never loosen a tolerance, never reintroduce a silent fallback. More than ten tests red from one change means the scope is wider than thought: stop and reassess. A rewritten test goes in the same commit as the code it follows.

**Update every caller in the same commit.** When a function signature, dataclass field, or yaml key changes, fix its callers at once, and delete legacy code rather than retire it. A new public `def` or `class`, or a new top-level key in `engine/*.yaml` or `prompts/*.yaml`, gets its consumer in the same commit; the orphan scans reject definitions without callers and keys without readers, apart from their carve-outs for Starlette route handlers, dataclasses bound only through a parent attribute, and `AICallSpec` sub-fields. A symbol is removed only when both sides are dead: no reader in code and none in config.

**Record every departure from a source.** A change that departs from a source rulebook, or from an architectural recommendation of the design document, adds an entry to `docs/divergences.md` in the same commit, with what the source says, what the engine does, why, and its status: Permanent (with the reason or measurement behind it), Until step N (that step's commit removes the entry), or Open (the roadmap lists the decision). A change that brings the engine in line removes the entry. The design document is a theoretical concept and this project its practical implementation, so a difference in detail from the document needs no entry.

**Documentation states the current state.** The md files describe what the code does now and why, not how it got there: a reason is written out, not referred to by a CHANGELOG version, and history stays in the CHANGELOG and in git. Each fact lives in one file; another file refers to it.

## Project rules

These rules hold across the codebase and are enforced by `tests/test_project_rules.py`. They exist because every shortcut that Python's defaults and exception swallowing make tempting eventually hides a real bug.

**No `#` comments and no docstrings in Python or yaml.** Code explains itself through names, types, and tests; context, motivation, and architecture live in the md files (the repository root and `docs/`). Three narrow exceptions allow one short trailing comment at the callsite: an external-boundary default, the AI-call carve-out, and an inline import that breaks a cycle or loads lazily.

**Domain config keys raise on a miss.** Config is read by direct subscript (`config["key"]`): no `dict.get` with a literal fallback, no `x or "fallback"`, no dataclass default on a field that binds to a config value. Three exceptions: empty collections the language requires (`field(default_factory=list)`), parsing of variable external structures, and the AI-call carve-out. An external structure is a Datasworn field absent from at least one of the four shipped rulesets (verifiable by grep) or optional in its schema, a WebSocket field optional in the protocol, or an AI-call field in a documented retry-fallback dict, not the happy-path response. A field required by its spec does not qualify, even at an external boundary. When in doubt, treat it as required.

**Yaml content boundary.** Yaml holds values whose source can be named: a Datasworn, Adventure Crafter, or Mythic table, a mechanical computation, or a value present elsewhere in the codebase. Values without a nameable source come from an AI call (with setting context in the prompt), from an oracle roll, or stay absent until decided. Prose-shaped values (mood words, descriptive phrases, narrative templates) do not belong in yaml. The boundary covers every yaml in the repository, setting yaml included. Its one exception is a setting's `vocabulary` block: the design document assigns vocabulary control to the setting as a constraint on the narrator's word choice, and it has no table source; entries are added only when a measured drift calls for them.

**Readable strings live in yaml.** Text that a player, the narrator, or an AI reads is not hardcoded in Python: `engine/*.yaml`, `prompts/*.yaml`, `strings/*.yaml`, and `emotions/*.yaml` are its homes. A constant in Python is a last resort with a written reason.

**Errors propagate.** No broad `except Exception: pass`, no `contextlib.suppress` over domain logic. The one exception is the AI-call carve-out: AI calls fail transiently (rate limits, network errors, provider outages), the retry wrapper handles what can be retried, and what remains is caught at the AI call site, or at a tool-boundary function that returns a structured error to its AI caller, and logged at warning level or higher. What each caught failure does to the turn is described in `docs/ai.md`. The carve-out never covers config loading, yaml parsing, file persistence, input validation, or domain rules; those raise. The files it covers are listed in `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`, the authoritative list, audits included.

**No backwards compatibility.** Saves break when the code requires it: no migration layer, no defaults for old fields, no ignoring unknown fields. This is by design for an alpha project with no production users; if it changes, it changes deliberately. `serialization.py` enforces it at load: a field default makes a fresh object, never an old save loadable.

**Import layers.** Dependencies point downward, as described in ARCHITECTURE.md.

## Code standards

Python 3.11+, dataclasses with type hints, f-strings, pathlib, snake_case, no mutable defaults, imports sorted at the top of the file, lines of at most 120 characters. `pyproject.toml` holds the full ruff and mypy configuration; the linter rules are the spec. mypy runs in strict mode: every function is typed, generics state their parameters, re-exports are explicit through `__all__`, and a value that arrives as `Any` from yaml or JSON gets its type where it enters typed code.

UI changes keep the page accessible: semantic HTML, ARIA live regions, heading structure, native form controls; no div-buttons and no spatial-only references.

## Testing

```bash
python -m pytest tests/ -q --cov                         # unit and integration suite, with the coverage floor
```

**The test suite** runs without an API key, on mock providers with canned responses. It covers the engine's logic: consequences, NPC processing, serialization, the correction flow, prompt assembly, the WebSocket handlers. `tests/test_rules_conformance.py` pins the rules checked against the source rulebooks (`docs/divergences.md`).

**Project rules.** `tests/test_project_rules.py` is one test that runs all AST and regex scans. Besides the rules above they cover orphan public symbols and orphan keys in `engine/*.yaml` and `prompts/*.yaml`, stale carve-out and whitelist entries, skip and xfail, `ruff format --check`, the import layers, AI calls that route by their own role, and documentation drift: every path named in the md files exists, every package appears in the code map of ARCHITECTURE.md, every `file.py → symbol` reference resolves, and the newest CHANGELOG entry matches the `pyproject.toml` version; every entry in `docs/divergences.md` carries a status, and a status that names a roadmap step names one that exists. Of the roadmap only the step headings are read, and of the CHANGELOG only the version headers. Run it before starting work to see the current state.

**Elvira**, the headless test player that plays the real game on the configured models, is described in `docs/elvira.md`, with the commands to run her.
