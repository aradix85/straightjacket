# AUDIT

How to audit this codebase against the five principles below. This document is enough to run an audit on its own, without following the roadmap's order of work: it says what to read first, how to work, what a session delivers, and, in Status at the bottom, what has been audited. Open items, the questions that wait for the user and the findings that belong to another principle or submodule, live in the roadmap's audit step (step 9h while it is open); when the roadmap has no audit step, they go to a section Open at the end of this document.

Earlier audits produced false reassurance: asked "is the codebase config-driven?", Claude answered "yes" while significant parts were still hardcoded. So an audit never gives a verdict. It works from an exhaustive hit-list, and zero hits and eighty hits are both valid answers; a selective look is not.

## Scope and order

1. Work in the local repository.
2. Read `ARCHITECTURE.md` and `CONTRIBUTING.md` in full: they define where things live and which exceptions to the project rules exist. Without them, violations and carve-outs get misclassified.
3. Read the section Sessions with the user in `roadmap.md`: how the maintainer is answered, what a measuring run costs and that its cost is named before it starts, and where the API keys live.
4. Read this document in full, then the open items, among them the findings earlier audits recorded for the principle or submodule at hand. Take the next open item from Status.

One audit session covers one principle, or for the interpretive principles (1, 3, 5) one submodule. The mechanical principles (2, 4) usually fit in one session. Do not combine principles or start the next one because time is left. Stopping halfway is a successful session: record the progress in Status, and anything to pick up next time as an open item.

A session fixes every clear violation it finds, in the same session and by CONTRIBUTING.md's rules for a change: callers and tests in the same commit, the quality gate green, a short Elvira run when the turn pipeline, prompts, or configuration changed, one CHANGELOG entry, and the release committed to main and pushed. Only what needs the user's decision, or belongs to another principle or submodule, becomes an open item. Deleting a file the user did not name waits for the user's consent.

The maintainer wants the code lean, KISS, YAGNI, and DRY (CONTRIBUTING.md, Lean, not defensive). So a session also fixes what it meets that is ugly, illogical, or broken, even where no principle names it, and no fix adds window dressing or defensive code: a fix leaves less structure behind, not more. Where a fix would add structure, such as a new protocol step or layer, the session weighs it against that wish, and the maintainer has left such calls to the session.

## Working method

**Hit-lists, never verdicts.** "Is principle X satisfied?" becomes "where does the codebase fail principle X?", answered with a list, even an empty one.

**Grep first, reason second.** Whatever can be a grep query is run as one before any reading; the result is the candidate list, and reasoning happens per hit. Every query is run with an exact pattern, and its result count goes into the CHANGELOG entry. Where a principle needs reasoning that no grep captures, say so and read file by file within one submodule.

**Read context before classifying.** Open each hit and read at least ten lines around it; never classify from the grep line alone.

**Carve-outs need a documented anchor.** A hit is a carve-out only if an explicit exception covers it: in CONTRIBUTING.md's Project rules (the AI-call carve-out and the default exceptions) or in ARCHITECTURE.md (a named pattern such as `get_raw` or the re-export hubs). A hit that looks legitimate without such an anchor is marked `needs human judgment`.

**Mark uncertainty, do not resolve it.** Unclear hits are marked `needs human judgment` with one sentence on why. Do not guess.

**No skipping by file name.** Exclusions are encoded in the grep query, never applied afterwards.

**Dynamic access defaults to `needs human judgment`.** Symbols reached through `getattr` with a variable name, runtime-built dict keys, fixture injection, schema generation, or serialization are invisible to grep; never declare them dead on grep alone.

**List before counting.** Every hit is listed and classified before any count or summary.

**Each violation belongs to one principle.** Several passes overlap (2d and 4a on dataclass defaults, 3c and 5e on single-use functions). A violation is listed once, under the principle whose pass found it first; a later principle references that entry. A violation that fails two principles names both and sits under the lower number.

## Output

1. The fixes, committed and pushed as one release.
2. That release's CHANGELOG entry: the principle and submodule, each query with its number of hits and of violations, and what was fixed.
3. This document's Status updated, and every open item recorded: a `needs human judgment` item with file, line, and one sentence on why, and a finding for another principle or submodule with file and line.
4. A short summary for the user, in their language: what was fixed, and every question that waits for them.

No report file is written; git, the CHANGELOG, and the open items carry the audit.

## The five principles

### Principle 1 — High modularity

One concern per file, and one file per concern, with `.py` and `.yaml` paired where a module has configurable behavior; smaller files preferred where a split does not force artificial abstractions. The rule "What belongs together lives together" in CONTRIBUTING.md is the second half: a concern spread over several files is as much a violation as two concerns in one. Audited per submodule under `src/straightjacket/engine/`: list every Python file with its line count and public functions.

**Step 1a — Mechanical flagging.** Flag every file over 400 lines. Line count is a lookup signal, not a verdict.

**Step 1b — Concern analysis.** For each flagged file, and each file with a nameable reason for suspicion (for example "this filename suggests two domains"), examine the public API and classify: violation (two or more distinct concerns that split without artificial coupling), legitimate (one large concern), or `needs human judgment`.

**Step 1c — Scattered concerns.** For each concern the submodule names (clocks, threats, tracks, NPC naming), grep its key symbols across `src/` and list every file that defines behaviour for it; a concern with more than one home is a violation unless the files are layers of it (a model, its rules, its prompt block).

Carve-outs: re-export hubs (`models.py`, `__init__.py` files), per "Subpackage public API via `__init__.py`" in ARCHITECTURE.md.

### Principle 2 — Config-driven

The rules "Domain config keys raise on a miss, and dataclass fields have no defaults", "Readable strings live in yaml", and "Config over code" in CONTRIBUTING.md. Anything a translator, designer, or rules editor would change without touching Python belongs in YAML.

**Pass 2a — User-facing strings.** Grep `src/straightjacket/` for literals that look like narration, error messages, UI labels, or AI prompts, and cross-reference `strings/*.yaml` and `prompts/*.yaml`. A user-, narrator-, or AI-readable string not loaded from YAML is a violation, the markup of a prompt and patterns for the AI's words included.

**Pass 2b — Numeric thresholds.** Grep numeric literals in `mechanics/`, `npc/`, `game/`, and `ai/`, cross-referenced with `engine/*.yaml`. A domain threshold, limit, or rule is a violation, the source systems' rule constants such as dice sizes included; a structural constant (loop bound, index) is not.

**Pass 2c — Mappings.** Grep dict and set literals in domain modules that hold domain keys (move names, dispositions, statuses). A mapping that should extend without Python changes is a violation, and so is a group of enum values written out at its callsites.

**Pass 2d — Dataclass defaults.** Grep `field(default=`, `field(default_factory=`, and `=` defaults on dataclass fields in `src/straightjacket/`. A violation unless it is one of the three exceptions under "Domain config keys raise on a miss, and dataclass fields have no defaults" in CONTRIBUTING.md; the optional fields of `AICallSpec` in `ai/provider_base.py` count as external-boundary parsing. `_check_no_dataclass_defaults_in_config_binding` covers the config binding mechanically; this pass covers every other dataclass.

Carve-outs: the `get_raw` pattern for yaml whose keys are domain data, the AI-call carve-out files in `_AI_CALL_CARVE_OUT_FILES`, the `theme_die_table` cross-validation.

### Principle 3 — No defensive programming, no boilerplate, no dead structure

"Errors propagate" in CONTRIBUTING.md, plus the structure that adds nothing: guards against impossible states, wrappers without logic, classes with one instance, options always set the same way, and abstractions used once are violations.

**Pass 3a — Broad except.** Grep `except Exception`, `except:`, `except BaseException`, cross-referenced with `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`, the authoritative carve-out list. A hit outside those files is a violation, and so is one inside them around a non-AI operation (config loading, yaml parsing, persistence, input validation, domain rules).

**Pass 3b — Defensive None checks (non-mechanical).** Per submodule, every `if x is None:` on a value whose type does not include `None`: violation, or legitimate because a documented protocol allows None.

**Pass 3c — Single-use abstractions.** Functions called exactly once where inlining would not hurt readability; classes with exactly one instance where a module function would do.

**Pass 3d — Wrappers without logic.** Functions whose body is a single `return foo(...)` with no parameter transformation, error handling, or caching.

**Pass 3e — Parameters for tests.** Every parameter with a default, checked against its production callers (CONTRIBUTING.md, No parameters for tests): a parameter production never sets, or a default every production call overrides, is a violation, and so is a branch or setter in production code that only tests reach. A default that production uses both ways stays.

Carve-outs: the AI-call carve-out for broad excepts; re-exports that make up the documented public API in `__init__.py` files.

### Principle 4 — No backwards compatibility

"No backwards compatibility" in CONTRIBUTING.md: every dataclass field is required apart from the exceptions under "Domain config keys raise on a miss, and dataclass fields have no defaults".

**Pass 4a — Dataclass field defaults.** References Pass 2d.

**Pass 4b — Migration patterns.** Grep `if .* in data`, `data.get(`, `try:.*KeyError`, `getattr(.*default`, and comments mentioning an old format, legacy fields, backwards compatibility, or migration. A hit that accommodates an old save format is a violation.

**Pass 4c — Permissive deserialization.** Grep `**kwargs` in `from_dict`, `__init__`, or `SerializableMixin` overrides, and `extra="ignore"` in any pydantic model, and parsers that pick known keys with `if "key" in data` without rejecting the rest. Each hit is a violation.

### Principle 5 — Clean codebase, no dead code, YAML-Python alignment

No dead Python symbols, no dead YAML keys; every YAML key has a Python consumer and every config access a YAML source. YAGNI, KISS, DRY.

**Pass 5a — Dead Python symbols.** For each public symbol in `src/straightjacket/`, grep `src/`, `tests/`, `engine/*.yaml`, `prompts/*.yaml`, and `data/`. Dead means no reader and no writer beyond the definition on every surface. Static tools (vulture, pylint) miss dict writes, getattr reads, fixtures, schema generation, and serialization; do not rely on them. Count production callers separately: a re-export plus tests is not a use in play.

**Pass 5b — Dead YAML keys.** For each key in `engine/`, `strings/`, `prompts/`, and `emotions/`, grep `src/` for the key; for each zero-hit key, check `get_raw` consumption and dataclass fields of the same name. Unambiguous orphans are violations.

**Pass 5c — Config dataclass fields without a YAML source.** For each subsystem dataclass in `engine_config_dataclasses.py`, locate each field's YAML key; fields never populated from config are violations.

**Pass 5d — YAML keys without a dataclass field.** The inverse of 5c, unless the block is read through `get_raw`.

**Pass 5e — Single-use functions and classes.** References Pass 3c.

Carve-outs: the orphan-symbol carve-outs in `tests/test_project_rules.py` (for example `CharacterTraits`). A symbol whose consumer is planned in a near-term roadmap step may be marked `needs human judgment`.

## Status

Submodules for principles 1, 3, and 5: `mechanics/`, `npc/`, `game/`, `ai/`, `datasworn/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level of `src/straightjacket/` (`i18n.py`). A finished submodule is listed under its principle with its date; a principle is done when every submodule is listed.

- Principle 1: no submodule audited; it runs per layer in roadmap step 9n, on the layout of the split into layers, since an audit before it would judge a layout about to change.
- Principle 2: audited 2026-10-17, all four passes; every violation is fixed except the dataclass defaults and the prompt markup (roadmap 9o.1 and 9o.2).
- Principle 3: `mechanics/`, `npc/`, and `game/` audited 2026-10-17 and `ai/`, `datasworn/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level 2026-10-18, every pass each, parameters included; principle 3 is done. The submodule `db/` was not audited but removed on 2026-10-18, since only the Director's tool read it. The open items are roadmap 9h.13 to 9h.18, 9h.25, 9h.28, 9j.7, 9j.8, 11.0, and steps 11c and 12.
- Principle 4: audited 2026-10-17, all three passes; every violation is fixed, and the dataclass defaults of pass 4a are roadmap 9o.1.
- Principle 5: `mechanics/` and `npc/` audited 2026-10-18, every pass, with the return values and the re-exports of each `__init__.py` read as symbols; the passes 5b to 5d covered the config sections each reads, the emotions yaml for `npc/`, and every config field that no code reads at all. Configuration whose consumer a roadmap step names stays and is listed there: the scene challenge (9k), the Meta handlers (9j.7), the companion and vehicle moves (19), and Delve's moves (26).
