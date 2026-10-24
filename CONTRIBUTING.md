# Contributing

How to change Straightjacket: the workflow, the rules every change keeps, the code standards, and the tests. ARCHITECTURE.md explains how the code is organised.

## Workflow

1. `ruff check --fix src/ tests/` and `ruff format src/ tests/`: must be clean.
2. `python -m pytest tests/ -q --cov`: every test passes, and total coverage stays at or above `fail_under` in `pyproject.toml` (`[tool.coverage.report]`). When the total stays past the next whole percent in every run, raise `fail_under` to it, since the random paths a run takes move the total by a few hundredths; never lower it.
3. `mypy src/ --config-file pyproject.toml`: must be clean.
4. **Read the whole diff back** before the commit, after every substep, and fix what it finds. A green suite does not replace this reading, since tests written beside the code share its blind spots. Look for:
   - no new default or parameter for tests, no broad except, no guard against a state that cannot occur, no dead branch or symbol, nothing that copies what already exists, nothing illogical or unclear;
   - every caller and every document the change touches updated, and for every fix a test that fails without it.

   The reading also sweeps outward from the diff, where the writer's blind spots lie (the user's choice, after a check found what the writer's reading missed): every other piece of text that enters a prompt the change touches; every sender of a message as well as every caller of a function (a WebSocket message, Elvira's two modes); and every name, string, or behaviour the change alters, searched across the md files of the root and `docs/` by its words as well as its symbol. Then a release that changes the game is checked by eyes that did not write it (AGENTS.md, Checking a release).
5. **An Elvira run** follows a change to the turn pipeline, AI calls, prompts, or configuration: a short run of 8 to 20 turns (`docs/elvira.md`), in which every engine warning of her report is a finding. The run plays where the API keys are, on the maintainer's laptop, so it follows the push to main rather than preceding it (the user's choice). The release's CHANGELOG entry says that the run follows; what the run finds is fixed in a following release, whose entry also reports the run.
6. **One CHANGELOG entry** per finished piece of work, not one per measurement, and only after its checks, apart from that Elvira run, have been read: what changed, why, what was measured, and the quality gate, in a few sentences. The version in `pyproject.toml` matches the newest entry.

An outside contributor forks, branches, and opens a pull request that says what changed and why. The maintainer's sessions commit each finished release to main and push it. They hand off to sub-agents, by AGENTS.md, which every sub-agent is given, the reading, searching, and checking whose conclusion is all they need, but not the reading of code they will change themselves.

## Rules for a change

**Scope includes what the work surfaces.** A bug or rule violation in a file you touch is fixed in the same change: silent fallbacks, hardcoded domain strings, broad excepts outside the carve-out, dataclass field defaults, inline imports outside the whitelist in `tests/test_project_rules.py`, comments or docstrings, documentation the change makes wrong, and test hygiene (random.seed without teardown, leaked module state). Stop and ask only when a fix needs an architectural decision you cannot take, or pulls in an unrelated subsystem. A TODO is not a fix, and neither is "noted for later".

**Tests are not the spec.** Code leads; tests check that it meets the intended behaviour, the project rules, and the architecture. When a correct change breaks a test, read the test first. It tested one of these:

- the behaviour the change replaces: rewrite it;
- an assumption that never held, such as the same hardcoded value as production: remove or replace it;
- something now defined elsewhere: update its setup.

Only rarely does it show that production is wrong. Never change code just to turn a test green, never skip or xfail, never loosen a tolerance, never reintroduce a silent fallback. More than ten tests red from one change means the scope is wider than thought: stop and reassess. A rewritten test goes in the same commit as the code it follows.

**Update every caller in the same commit.** When a function signature, dataclass field, or yaml key changes, fix its callers at once, and delete legacy code rather than retire it.

- A new public `def` or `class`, or a new top-level key in the yaml of `engine/`, `gamemaster/`, `crafters/`, `ruleset/`, or `prompts/`, gets its consumer in the same commit. The orphan scans reject definitions without a use outside their own definition and top-level keys without a reader in `src/`, apart from the orphan-symbol carve-out in `tests/test_project_rules.py`, which names what only a script outside `src/` or a later roadmap step calls.
- A symbol is removed only when both sides are dead: no reader in code and none in config.
- The scans do not see nested yaml keys, `strings/*.yaml`, `emotions/*.yaml`, the settings yaml, or `config.yaml`, so a change that stops reading one deletes it by hand.

**Record every departure from a source.** A change that departs from a source rulebook, or from an architectural recommendation of the design document, adds an entry to `docs/divergences.md` in the same commit: what the source says, what the engine does, why, and its status.

- Statuses: Permanent (with the reason or measurement behind it), Until step N (that step's commit removes the entry), or Open (the roadmap lists the decision). A change that brings the engine in line removes the entry.
- A difference in detail from the design document, a theoretical concept (ORIGINS.md), needs no entry.
- A new rule that decides something in the fiction and has no source gets an entry too, with its reason (AUDIT.md, principle 6).
- A rule that came from EdgeTales leaves only in the change that replaces it or routes its work to a system the engine already has, unless it never worked.

**Documentation states the current state.** The md files describe what the code does now and why, not how it got there: a reason is written out, not referred to by a CHANGELOG version, and history stays in the CHANGELOG and in git. Each fact lives in one file; another file refers to it. The documents are kept short, since every session reads them anew (the user's choice): a section holds what a session needs, in short paragraphs and lists, and repeats nothing another file or the code already says.

## Project rules

These rules hold across the codebase. `tests/test_project_rules.py` enforces what a scan can see, and reading the diff (Workflow, step 4) the rest. They exist because every shortcut that Python's defaults and exception swallowing make tempting eventually hides a real bug.

**No `#` comments and no docstrings in Python or yaml.** Code explains itself through names, types, and tests; context, motivation, and architecture live in the md files (the repository root and `docs/`). The rule covers `src/`, `tests/`, and the scripts `run.py` and `data/data.py`. Most other scans read `src/` only; the scans for broad excepts, provider imports, and model names read `tests/` as well. Three narrow exceptions allow one short trailing comment at the callsite: an external-boundary default, the AI-call carve-out, and an inline import that breaks a cycle or loads lazily.

**Domain config keys raise on a miss, and dataclass fields have no defaults.** Config is read by direct subscript (`config["key"]`): no `dict.get` with a literal fallback, no `x or "fallback"`. No dataclass field has a default, whether it binds to config, holds game state, or carries a result between modules, so a caller that forgets a field fails at once instead of carrying a silent empty value. A project-rule scan enforces this for every dataclass, with the external structures it names as its carve-out. A field the config binding fills from yaml takes not even an empty collection, since the binding would fill a missing key with it.

Three exceptions:

- empty collections the language requires (`field(default_factory=list)`);
- parsing of variable external structures;
- the partial blocks of a setting yaml, whose omitted fields inherit from the parent (`docs/settings.md`, Inheritance).

An external structure is a Datasworn field absent from at least one of the four shipped rulesets (verifiable by grep) or optional in its schema, a WebSocket field optional in the protocol, or an AI-call field in a documented retry-fallback dict, not the happy-path response. A field required by its spec does not qualify, even at an external boundary. When in doubt, treat it as required.

**No parameters for tests.** A function has no parameter that production never sets and no default that every production call overrides; this is the user's standing choice for a lean codebase. Such an option is dead structure, and a forgotten argument should fail. A default stays only where production calls the function both with and without the argument. Tests reach other values by patching the module they exercise (`random`, the retry's sleep), not through parameters of their own.

**Yaml content boundary.** Game content, what the world holds and what happens in it, comes from a source that can be named: a Datasworn, Adventure Crafter, or Mythic table, a mechanical computation, or a value present elsewhere in the codebase. Content without such a source comes from an oracle roll, stays absent until decided, or, as the last resort, comes from an AI call with setting context in the prompt (ARCHITECTURE.md, order of preference).

- Yaml never invents game content by hand: no mood words, descriptive phrases, or facts about the world without a source.
- What yaml does hold besides sourced values and numbers is the engine's own text: the instructions, labels, and templates through which the engine tells a player, the narrator, or another AI what it decided, such as the consequence sentences or the text of a filled clock, kept in yaml so that they change without touching Python.
- The boundary covers every yaml in the repository, setting yaml included. Its one exception for hand-written game content is a setting's `vocabulary` block: the design document assigns vocabulary control to the setting as a constraint on the narrator's word choice, and it has no table source. Entries are added only when a measured drift calls for them.

**Readable strings live in yaml.** Text that a player, the narrator, or an AI reads is not hardcoded in Python. Its homes are the yaml of `engine/` and the layers' folders (`gamemaster/`, `crafters/`, `ruleset/`), `prompts/*.yaml`, `strings/*.yaml`, and `emotions/*.yaml`. That covers the markup of a prompt as much as its prose (tags, attribute names, and labels the AI reads), and the patterns that recognise words in the AI's answers. A constant in Python is a last resort with a written reason.

**Config over code.** Whatever can be configuration is configuration, the user's standing choice: Python holds control flow and the structure that a yaml key would only rename. The rule constants of the source systems (dice sizes, the score cap, the ticks per box), the thresholds and groupings of the engine's own rules, and named groups of enum values live in the yaml of the layer they belong to (`gamemaster/`, `crafters/`, `ruleset/`) or in `engine/`, read where they are used rather than written at the callsite.

**What belongs together lives together.** Also the user's standing choice: one concern has one home, its code in one module and its configuration in one yaml file, instead of a piece in every file that touches it. A helper that several modules need lives in the module of its concern, never copied and never imported sideways from a neighbour that happens to define it.

**Lean, not defensive.** Also the user's standing choice: the code stays lean, KISS, YAGNI, and DRY. Code that is ugly, illogical, or broken is fixed when a change or an audit meets it; nothing adds window dressing, structure for a need no step has, or guards against states that cannot occur.

**Errors propagate.** No broad `except Exception: pass`, no `contextlib.suppress` over domain logic.

- **The AI-call carve-out** is the one exception. AI calls fail transiently (rate limits, network errors, provider outages); the retry wrapper handles what can be retried, and what remains is caught at the AI call site and logged at warning level or higher. What each caught failure does to the turn is in `docs/ai.md` (When an AI call fails).
- The carve-out never covers config loading, yaml parsing, file persistence, input validation, or domain rules inside the engine; those raise.
- It reaches further in two places. The retry wrapper's catch covers the provider's call as a whole, the request the router and the adapters build inside it included (`docs/ai.md`, Provider adapters). The web layer's handlers catch any fault of the engine call they make, roll the game back, log it at error level, and tell the player that nothing changed, while `web/server.py` → `_dispatch_one_message` does the same for any other fault of a handler.
- The files it covers are listed in `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`, the authoritative list, audits included; Elvira's and the tests' own are in `_AI_CALL_CARVE_OUT_TESTS`.

**No backwards compatibility.** Saves break when the code requires it: no migration layer, no defaults for old fields, no ignoring unknown fields. This is by design for an alpha project with no production users; if it changes, it changes deliberately. `serialization.py` enforces it at load: a field default makes a fresh object, never an old save loadable.

**Import layers.** Dependencies point downward, as described in ARCHITECTURE.md.

## Code standards

Python 3.11+, dataclasses with type hints, f-strings, pathlib, snake_case, no mutable defaults, imports sorted at the top of the file, lines of at most 120 characters wherever the formatter can break them. `pyproject.toml` holds the full ruff and mypy configuration; the linter rules are the spec. mypy runs in strict mode: every function is typed, generics state their parameters, re-exports are explicit through `__all__`, and a value that arrives as `Any` from yaml or JSON gets its type where it enters typed code.

UI changes keep the page accessible: semantic HTML, ARIA live regions, heading structure, native form controls; no div-buttons and no spatial-only references.

## Testing

```bash
python -m pytest tests/ -q --cov                         # unit and integration suite, with the coverage floor
```

**The test suite** runs without an API key, on mock providers with canned responses. It covers the engine's logic: consequences, NPC processing, serialization, the correction flow, prompt assembly, the WebSocket handlers.

- A test that plays a turn, a correction, a momentum burn, or a chapter transition builds its game through the real character creation with `create_game` in `tests/_creation.py`, because hand-built states have hidden real faults. Hand-built states (`tests/_helpers.py`) serve unit tests of single functions.
- `tests/test_rules_conformance.py` pins the rules checked against the source rulebooks (`docs/divergences.md`).

**Project rules.** `tests/test_project_rules.py` is one test that runs all AST and regex scans; run it before starting work to see the current state. Besides the rules above it covers:

- orphans: public symbols, top-level keys in the yaml of `engine/` and the layers' folders, and keys in `prompts/*.yaml`; carve-out and whitelist entries that no longer carve anything out;
- skip and xfail; `ruff format --check`; `# noqa`, `# type: ignore`, and `# pragma: no cover`;
- the import layers; imports of `game`, `tools`, and `correction` through their `__init__.py`; a provider SDK imported outside its adapter;
- AI calls that route by their own role; a model name written in code;
- a function's cyclomatic complexity of at most 20;
- `.setdefault`, a fallback to `get_raw`, `x or []`, and an optional collection parameter defaulting to `None`;
- a dataclass in the models without `SerializableMixin`; a versioned file name such as `_v2`;
- documentation drift:
  - in the md files of the root and `docs/`, roadmap.md and the CHANGELOG apart, every path named is the end of a file's path in the repository, so it may start at any folder that holds it, and every `file.py → symbol` reference names a function, class, or assignment in that file;
  - every package appears in the code map of ARCHITECTURE.md;
  - every entry in `docs/divergences.md` carries a status, and a status that names a roadmap step names one that exists; of the roadmap only the step headings are read;
  - the CHANGELOG's versions descend, its newest matching the `pyproject.toml` version, with a version header after every `---`; of the CHANGELOG only the version headers are read.

**Elvira**, the headless test player that plays the real game on the configured models, is described in `docs/elvira.md`, with the commands to run her.
