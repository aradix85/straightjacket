# Contributing

How to change Straightjacket: the workflow, the rules every change keeps, the code standards, and the tests. ARCHITECTURE.md explains how the code is organised.

## Workflow

1. `ruff check --fix src/ tests/` and `ruff format src/ tests/`: must be clean.
2. `python -m pytest tests/ -q --cov`: every test passes, and total coverage stays at or above `fail_under` in `pyproject.toml` (`[tool.coverage.report]`). When the total passes the next whole percent, raise `fail_under` to it; never lower it.
3. `mypy src/ --config-file pyproject.toml`: must be clean.
4. Read the whole diff back before the commit, after every substep, and fix what it finds: no new default or parameter for tests, no broad except, no guard against a state that cannot occur, no dead branch or symbol, nothing that copies what already exists, nothing illogical or unclear, every caller and every document the change touches updated, and for every fix a test that fails without it. A green suite does not replace this reading, since tests written beside the code share its blind spots.
5. A change to the turn pipeline, AI calls, prompts, or configuration first gets a short Elvira run (8 to 20 turns, `docs/elvira.md`), and every engine warning in its report is a finding.
6. One CHANGELOG entry per finished piece of work, not one per measurement, and only after its checks have been read: what changed, why, what was measured, and the quality gate, in a few sentences. The version in `pyproject.toml` matches the newest entry.

An outside contributor forks, branches, and opens a pull request that says what changed and why. The maintainer's sessions commit each finished release to main and push it.

## Rules for a change

**Scope includes what the work surfaces.** A bug or rule violation in a file you touch is fixed in the same change: silent fallbacks, hardcoded domain strings, broad excepts outside the carve-out, dataclass field defaults, inline imports outside the whitelist in `tests/test_project_rules.py`, comments or docstrings, documentation the change makes wrong, and test hygiene (random.seed without teardown, leaked module state). Stop and ask only when a fix needs an architectural decision you cannot take, or pulls in an unrelated subsystem. A TODO is not a fix, and neither is "noted for later".

**Tests are not the spec.** Code leads; tests check that it meets the intended behaviour, the project rules, and the architecture. When a correct change breaks a test, read the test first. It tested the behaviour the change replaces (rewrite it), an assumption that never held, such as the same hardcoded value as production (remove or replace it), or something now defined elsewhere (update its setup). Only rarely does it show that production is wrong. Never change code just to turn a test green, never skip or xfail, never loosen a tolerance, never reintroduce a silent fallback. More than ten tests red from one change means the scope is wider than thought: stop and reassess. A rewritten test goes in the same commit as the code it follows.

**Update every caller in the same commit.** When a function signature, dataclass field, or yaml key changes, fix its callers at once, and delete legacy code rather than retire it. A new public `def` or `class`, or a new top-level key in the yaml of `engine/`, `gamemaster/`, `crafters/`, `ruleset/`, or `prompts/`, gets its consumer in the same commit; the orphan scans reject definitions without callers and top-level keys without readers, apart from their carve-outs for Starlette route handlers, dataclasses bound only through a parent attribute, and `AICallSpec` sub-fields. A symbol is removed only when both sides are dead: no reader in code and none in config. The scans do not see nested yaml keys or `strings/*.yaml`, so a change that stops reading one deletes it by hand.

**Record every departure from a source.** A change that departs from a source rulebook, or from an architectural recommendation of the design document, adds an entry to `docs/divergences.md` in the same commit, with what the source says, what the engine does, why, and its status: Permanent (with the reason or measurement behind it), Until step N (that step's commit removes the entry), or Open (the roadmap lists the decision). A change that brings the engine in line removes the entry. A difference in detail from the design document, a theoretical concept (ORIGINS.md), needs no entry.

**Documentation states the current state.** The md files describe what the code does now and why, not how it got there: a reason is written out, not referred to by a CHANGELOG version, and history stays in the CHANGELOG and in git. Each fact lives in one file; another file refers to it.

## Project rules

These rules hold across the codebase and are enforced by `tests/test_project_rules.py`. They exist because every shortcut that Python's defaults and exception swallowing make tempting eventually hides a real bug.

**No `#` comments and no docstrings in Python or yaml.** Code explains itself through names, types, and tests; context, motivation, and architecture live in the md files (the repository root and `docs/`). The rule covers `src/`, `tests/`, and the scripts `run.py` and `data/data.py`; the other Python scans cover `src/` and `tests/`. Three narrow exceptions allow one short trailing comment at the callsite: an external-boundary default, the AI-call carve-out, and an inline import that breaks a cycle or loads lazily.

**Domain config keys raise on a miss, and dataclass fields have no defaults.** Config is read by direct subscript (`config["key"]`): no `dict.get` with a literal fallback, no `x or "fallback"`. No dataclass field has a default, whether it binds to config, holds game state, or carries a result between modules, so a caller that forgets a field fails at once instead of carrying a silent empty value. A project-rule scan enforces this for the config binding; the rest is checked by the audit (AUDIT.md, pass 2d). Three exceptions: empty collections the language requires (`field(default_factory=list)`), parsing of variable external structures, and the AI-call carve-out. An external structure is a Datasworn field absent from at least one of the four shipped rulesets (verifiable by grep) or optional in its schema, a WebSocket field optional in the protocol, or an AI-call field in a documented retry-fallback dict, not the happy-path response. A field required by its spec does not qualify, even at an external boundary. When in doubt, treat it as required.

**No parameters for tests.** A function has no parameter that production never sets and no default that every production call overrides, the user's standing choice for a lean codebase: such an option is dead structure, and a forgotten argument should fail. A default stays only where production calls the function both with and without the argument. Tests reach other values by patching the module they exercise (`random`, the retry's sleep), not through parameters of their own.

**Yaml content boundary.** Game content, what the world holds and what happens in it, comes from a source that can be named: a Datasworn, Adventure Crafter, or Mythic table, a mechanical computation, or a value present elsewhere in the codebase. Content without such a source comes from an oracle roll, stays absent until decided, or, as the last resort, comes from an AI call with setting context in the prompt (ARCHITECTURE.md, order of preference). Yaml never invents game content by hand: no mood words, descriptive phrases, or facts about the world without a source. What yaml does hold besides sourced values and numbers is the engine's own text: the instructions, labels, and templates through which the engine tells a player, the narrator, or another AI what it decided, such as the consequence sentences or the text of a filled clock, kept in yaml so that they change without touching Python. The boundary covers every yaml in the repository, setting yaml included. Its one exception for hand-written game content is a setting's `vocabulary` block: the design document assigns vocabulary control to the setting as a constraint on the narrator's word choice, and it has no table source; entries are added only when a measured drift calls for them.

**Readable strings live in yaml.** Text that a player, the narrator, or an AI reads is not hardcoded in Python: the yaml of `engine/` and the layers' folders (`gamemaster/`, `crafters/`, `ruleset/`), `prompts/*.yaml`, `strings/*.yaml`, and `emotions/*.yaml` are its homes. That covers the markup of a prompt as much as its prose (tags, attribute names, and labels the AI reads), and the patterns that recognise words in the AI's answers. A constant in Python is a last resort with a written reason.

**Config over code.** Whatever can be configuration is configuration, the user's standing choice: Python holds control flow and the structure that a yaml key would only rename. The rule constants of the source systems (dice sizes, the score cap, the ticks per box), the thresholds and groupings of the engine's own rules, and named groups of enum values live in the yaml of the layer they belong to (`gamemaster/`, `crafters/`, `ruleset/`) or in `engine/`, read where they are used rather than written at the callsite.

**What belongs together lives together.** Also the user's standing choice: one concern has one home, its code in one module and its configuration in one yaml file, instead of a piece in every file that touches it. A helper that several modules need lives in the module of its concern, never copied and never imported sideways from a neighbour that happens to define it.

**Lean, not defensive.** Also the user's standing choice: the code stays lean, KISS, YAGNI, and DRY. Code that is ugly, illogical, or broken is fixed when a change or an audit meets it; nothing adds window dressing, structure for a need no step has, or guards against states that cannot occur.

**Errors propagate.** No broad `except Exception: pass`, no `contextlib.suppress` over domain logic. The one exception is the AI-call carve-out: AI calls fail transiently (rate limits, network errors, provider outages), the retry wrapper handles what can be retried, and what remains is caught at the AI call site and logged at warning level or higher. What each caught failure does to the turn is described in `docs/ai.md`. The carve-out never covers config loading, yaml parsing, file persistence, input validation, or domain rules; those raise. The one place it reaches further is the retry wrapper, whose catch covers the provider's call as a whole, the request the router and the adapters build inside it included (`docs/ai.md`, Provider adapters). The files it covers are listed in `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`, the authoritative list, audits included.

**No backwards compatibility.** Saves break when the code requires it: no migration layer, no defaults for old fields, no ignoring unknown fields. This is by design for an alpha project with no production users; if it changes, it changes deliberately. `serialization.py` enforces it at load: a field default makes a fresh object, never an old save loadable.

**Import layers.** Dependencies point downward, as described in ARCHITECTURE.md.

## Code standards

Python 3.11+, dataclasses with type hints, f-strings, pathlib, snake_case, no mutable defaults, imports sorted at the top of the file, lines of at most 120 characters. `pyproject.toml` holds the full ruff and mypy configuration; the linter rules are the spec. mypy runs in strict mode: every function is typed, generics state their parameters, re-exports are explicit through `__all__`, and a value that arrives as `Any` from yaml or JSON gets its type where it enters typed code.

UI changes keep the page accessible: semantic HTML, ARIA live regions, heading structure, native form controls; no div-buttons and no spatial-only references.

## Testing

```bash
python -m pytest tests/ -q --cov                         # unit and integration suite, with the coverage floor
```

**The test suite** runs without an API key, on mock providers with canned responses. It covers the engine's logic: consequences, NPC processing, serialization, the correction flow, prompt assembly, the WebSocket handlers. A test that plays a turn, a correction, a momentum burn, or a chapter transition builds its game through the real character creation with `create_game` in `tests/_creation.py`, because hand-built states have hidden real faults; hand-built states (`tests/_helpers.py`) serve unit tests of single functions. `tests/test_rules_conformance.py` pins the rules checked against the source rulebooks (`docs/divergences.md`).

**Project rules.** `tests/test_project_rules.py` is one test that runs all AST and regex scans. Besides the rules above they cover orphan public symbols, orphan top-level keys in the yaml of `engine/` and the layers' folders, and orphan keys in `prompts/*.yaml`, stale carve-out and whitelist entries, skip and xfail, `ruff format --check`, the import layers, AI calls that route by their own role, and documentation drift: every path named in the md files exists, every package appears in the code map of ARCHITECTURE.md, every `file.py → symbol` reference resolves, and the newest CHANGELOG entry matches the `pyproject.toml` version; every entry in `docs/divergences.md` carries a status, and a status that names a roadmap step names one that exists. Of the roadmap only the step headings are read, and of the CHANGELOG only the version headers. Run it before starting work to see the current state.

**Elvira**, the headless test player that plays the real game on the configured models, is described in `docs/elvira.md`, with the commands to run her.
