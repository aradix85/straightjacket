# AUDIT

How to audit this codebase against the six principles below. This document is enough to run an audit on its own, without following the roadmap's order of work: it says what to read first, how to work, what a session delivers, and, in Status at the bottom, what has been audited. Open items, the questions that wait for the user and the findings that belong to another principle or submodule, live in the roadmap step they belong to; those that belong to none go to the section Open at the end of this document.

Earlier audits produced false reassurance: asked "is the codebase config-driven?", Claude answered "yes" while significant parts were still hardcoded. So an audit never gives a verdict. It works from an exhaustive hit-list, and zero hits and eighty hits are both valid answers; a selective look is not.

## Scope and order

1. Work in the local repository.
2. Read `ARCHITECTURE.md` and `CONTRIBUTING.md` in full: they define where things live and which exceptions to the project rules exist. Without them, violations and carve-outs get misclassified.
3. Read the section Sessions with the user in `roadmap.md`: how the maintainer is answered, what a measuring run costs and that its cost is named before it starts, and where the API keys live.
4. Read this document in full, then the open items, among them the findings earlier audits recorded for the principle or submodule at hand. Take the next open item from Status.

One audit session covers one principle, or for the interpretive principles (1, 3, 5) one submodule; principle 6 reads origins across the layers, so one session covers it whole. The mechanical principles (2, 4) usually fit in one session. Do not combine principles or start the next one because time is left. Stopping halfway is a successful session: record the progress in Status, and anything to pick up next time as an open item.

A session fixes every clear violation it finds, in the same session and by CONTRIBUTING.md's rules for a change: callers and tests in the same commit, the quality gate green, a short Elvira run when the turn pipeline, prompts, or configuration changed, one CHANGELOG entry, and the release committed to main and pushed. Only what needs the user's decision, or belongs to another principle or submodule, becomes an open item. Deleting a file the user did not name waits for the user's consent.

A session also fixes what it meets that is ugly, illogical, or broken, even where no principle names it (CONTRIBUTING.md, Lean, not defensive): a fix leaves less structure behind, not more. Where a fix would add structure, such as a new protocol step or layer, the session weighs it against that, as the maintainer has left such calls to the session.

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

## The six principles

### Principle 1 — High modularity

One concern per file, and one file per concern, with `.py` and `.yaml` paired where a module has configurable behavior; smaller files preferred where a split does not force artificial abstractions. The rule "What belongs together lives together" in CONTRIBUTING.md is the second half: a concern spread over several files is as much a violation as two concerns in one. Audited per submodule under `src/straightjacket/`: list every Python file with its line count and public functions.

**Step 1a — Mechanical flagging.** Flag every file over 400 lines. Line count is a lookup signal, not a verdict.

**Step 1b — Concern analysis.** For each flagged file, and each file with a nameable reason for suspicion (for example "this filename suggests two domains"), examine the public API and classify: violation (two or more distinct concerns that split without artificial coupling), legitimate (one large concern), or `needs human judgment`.

**Step 1c — Scattered concerns.** For each concern the submodule names (clocks, threats, tracks, NPC naming), grep its key symbols across `src/` and list every file that defines behaviour for it; a concern with more than one home is a violation unless the files are layers of it (a model, its rules, its prompt block).

Carve-outs: re-export hubs (`models.py`, `__init__.py` files), per "Subpackage public API via `__init__.py`" in ARCHITECTURE.md.

### Principle 2 — Config-driven

The rules "Domain config keys raise on a miss, and dataclass fields have no defaults", "Readable strings live in yaml", and "Config over code" in CONTRIBUTING.md. Anything a translator, designer, or rules editor would change without touching Python belongs in YAML.

**Pass 2a — User-facing strings.** Grep `src/straightjacket/` for literals that look like narration, error messages, UI labels, or AI prompts, and cross-reference `strings/*.yaml` and `prompts/*.yaml`. A user-, narrator-, or AI-readable string not loaded from YAML is a violation, the markup of a prompt and patterns for the AI's words included.

**Pass 2b — Numeric thresholds.** Grep numeric literals in `gamemaster/`, `crafters/`, `ruleset/`, `game/`, and `ai/`, cross-referenced with the yaml of `engine/`, `gamemaster/`, `crafters/`, and `ruleset/`. A domain threshold, limit, or rule is a violation, the source systems' rule constants such as dice sizes included; a structural constant (loop bound, index) is not.

**Pass 2c — Mappings.** Grep dict and set literals in domain modules that hold domain keys (move names, dispositions, statuses). A mapping that should extend without Python changes is a violation, and so is a group of enum values written out at its callsites.

**Pass 2d — Dataclass defaults.** Grep `field(default=`, `field(default_factory=`, and `=` defaults on dataclass fields in `src/straightjacket/`. A violation unless it is one of the three exceptions under "Domain config keys raise on a miss, and dataclass fields have no defaults" in CONTRIBUTING.md; `AIResponse` in `ai/provider_base.py`, which the adapters fill from a provider's answer, counts as external-boundary parsing. `_check_no_dataclass_defaults` in `tests/test_project_rules.py` covers every dataclass mechanically, with its carve-out `_EXTERNAL_STRUCTURE_DATACLASSES`; this pass reads that carve-out against the exceptions.

Carve-outs: the `get_raw` pattern for yaml whose keys are domain data, and the AI-call carve-out files in `_AI_CALL_CARVE_OUT_FILES`.

### Principle 3 — No defensive programming, no boilerplate, no dead structure

"Errors propagate" in CONTRIBUTING.md, plus the structure that adds nothing: guards against impossible states, wrappers without logic, classes with one instance, options always set the same way, and abstractions used once are violations.

**Pass 3a — Broad except.** Grep `except Exception`, `except:`, `except BaseException`, cross-referenced with `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py`, the authoritative carve-out list. A hit outside those files is a violation, and so is one inside them around a non-AI operation (config loading, yaml parsing, persistence, input validation, domain rules), apart from the web layer's catch-all around an engine call that CONTRIBUTING.md allows (Errors propagate).

**Pass 3b — Defensive None checks (non-mechanical).** Per submodule, every `if x is None:` on a value whose type does not include `None`: violation, or legitimate because a documented protocol allows None.

**Pass 3c — Single-use abstractions.** Functions called exactly once where inlining would not hurt readability; classes with exactly one instance where a module function would do.

**Pass 3d — Wrappers without logic.** Functions whose body is a single `return foo(...)` with no parameter transformation, error handling, or caching.

**Pass 3e — Parameters for tests.** Every parameter with a default, checked against its production callers (CONTRIBUTING.md, No parameters for tests): a parameter production never sets, or a default every production call overrides, is a violation, and so is a branch or setter in production code that only tests reach. A default that production uses both ways stays.

Carve-outs: the AI-call carve-out for broad excepts; re-exports that make up the documented public API in `__init__.py` files.

### Principle 4 — No backwards compatibility

"No backwards compatibility" in CONTRIBUTING.md: every dataclass field is required apart from the exceptions under "Domain config keys raise on a miss, and dataclass fields have no defaults".

**Pass 4a — Dataclass field defaults.** References Pass 2d.

**Pass 4b — Migration patterns.** Grep `if .* in data`, `data.get(`, `try:.*KeyError`, `getattr(.*default`, and comments mentioning an old format, legacy fields, backwards compatibility, or migration. A hit that accommodates an old save format is a violation.

**Pass 4c — Permissive deserialization.** Grep `**kwargs` in `from_dict`, `__init__`, or `SerializableMixin` overrides, and parsers that pick known keys with `if "key" in data` without rejecting the rest. Each hit is a violation.

### Principle 5 — Clean codebase, no dead code, YAML-Python alignment

No dead Python symbols, no dead YAML keys; every YAML key has a Python consumer and every config access a YAML source. YAGNI, KISS, DRY.

**Pass 5a — Dead Python symbols.** For each public symbol in `src/straightjacket/`, grep `src/`, `tests/`, the yaml of `engine/`, `gamemaster/`, `crafters/`, and `ruleset/`, `prompts/*.yaml`, and `data/`. Dead means no reader and no writer beyond the definition on every surface. Static tools (vulture, pylint) miss dict writes, getattr reads, fixtures, schema generation, and serialization; do not rely on them. Count production callers separately: a re-export plus tests is not a use in play.

**Pass 5b — Dead YAML keys.** For each key in `engine/`, `gamemaster/`, `crafters/`, `ruleset/`, `strings/`, `prompts/`, and `emotions/`, grep `src/` for the key; for each zero-hit key, check `get_raw` consumption and dataclass fields of the same name. Unambiguous orphans are violations.

**Pass 5c — Config dataclass fields without a YAML source.** For each subsystem dataclass in `engine_config_dataclasses.py` and the layers' `config_types.py` and `crafters/config.py`, locate each field's YAML key; fields never populated from config are violations.

**Pass 5d — YAML keys without a dataclass field.** The inverse of 5c, unless the block is read through `get_raw`.

**Pass 5e — Single-use functions and classes.** References Pass 3c.

**A field without a reader.** The game should be bound to its rules as tightly as it can be, so before a field, a return value, or an answer asked of the AI goes because no code reads it, ask whether it carries something the rules or the story know that the game should act on or tell. If it does, the finding is a missing reader: the session gives it one, a prompt that shows it to the AI or code that acts on it, and an Elvira session shows how play takes it. Only constants, copies of what is held elsewhere, and what only tests read go.

Carve-outs: the orphan-symbol carve-out in `tests/test_project_rules.py` (for example `dispatch_meta`). A symbol whose consumer is planned in a near-term roadmap step may be marked `needs human judgment`.

### Principle 6 — Every rule has a source

Every rule and structure that decides facts, pacing, or behaviour in the fiction has an origin the engine can name: a source (Datasworn, Mythic 2e, the Adventure Crafter, the Location Crafter, Blades in the Dark, AIMS), or an engine rule whose entry in `docs/divergences.md` gives its reason. The design document is the theory the engine puts into practice and may depart from (ORIGINS.md): an idea from it gives a rule its aim, not its form or its values, so such a rule is an engine rule, and a rulebook that can give its form comes first. A rule with neither, such as one carried over from EdgeTales (ORIGINS.md), is a violation: the session names the roadmap step whose source replaces it or adds one, and where no source can, the rule stays as an engine rule with a register entry that gives its reason. A rule that does something never just goes: it is replaced, or its work is routed to a system the engine already has, in the same change; only a rule that never worked, or adds nothing, goes without one (the user's words). Technique that decides nothing in the fiction (search, matching, saving, streaming, parsing, prompt plumbing) is outside the principle whatever its origin. The aim is the user's (roadmap, Decisions, From EdgeTales to the sources).

**Pass 6a — Rules in yaml.** Every top-level section of `gamemaster/`, `crafters/`, `ruleset/`, `engine/`, and `emotions/`, and every key in it that holds a rule of its own: what it decides, read from its consumer; whether the repository's first commit (a3b263f, the code of the fork) held it, and whether EdgeTales did; which source defines it, with its data path, and whether the values follow it; and its register entry.

**Pass 6b — Rules in Python.** Per package, the rules a function holds without a yaml key, such as a threshold folded into a condition or a fixed order of steps: the same four questions.

**Pass 6c — What the AI decides.** Every rule of `prompts/*.yaml` that tells the AI what to decide or invent in the fiction, and every answer of an AI call the engine acts on: the same questions, and whether a source could let the engine decide it instead, by ARCHITECTURE.md's order of preference. Rules of prose craft decide no facts and stay outside.

Carve-outs: technique, and a departure the register records.

## Status

Submodules for principles 1, 3, and 5: `setting/`, `gamemaster/` with `gamemaster/npc/`, `crafters/`, `ruleset/`, `game/`, `ai/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level of `src/straightjacket/` (`i18n.py`). A finished submodule is listed under its principle with its date; a principle is done when every submodule is listed. The audits below name the submodules as they were when they ran; their code has since moved into the four layers' packages: that of `mechanics/` into `gamemaster/`, `crafters/`, and `ruleset/`, that of `npc/` into `gamemaster/npc/`, and that of `datasworn/` into `setting/` and `ruleset/datasworn.py`.

- Principle 1: the four layers audited 2026-10-19 (roadmap 9n), all three steps: `setting/`, `crafters/`, whose Adventure Crafter module became five, `gamemaster/` with `gamemaster/npc/`, whose concerns with a yaml of their own became modules of their own, and `ruleset/`, where `move_effects.py` and `outcome_result.py` stay whole since a split would import in a circle; the CHANGELOG has the details. Open: `game/`, `ai/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level.
- Principle 2: audited 2026-10-17, all four passes; every violation is fixed but the copied theme table (Open below), the dataclass defaults, the prompt markup, and the pattern for a host's `<think>` reasoning since 2026-10-20 (roadmap 9o). The code the split into layers wrote or rewrote had the four passes again on 2026-10-19, in `setting/`, `gamemaster/` with `gamemaster/npc/`, `crafters/`, `ruleset/`, and the files that call them, with the same exceptions.
- Principle 3: `mechanics/`, `npc/`, and `game/` audited 2026-10-17 and `ai/`, `datasworn/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level 2026-10-18, every pass each, parameters included; principle 3 is done. The submodule `db/` was not audited but removed on 2026-10-18, since only the Director's tool read it. The code the split into layers wrote or rewrote had every pass again on 2026-10-19, in the same packages as principle 2. The open items it found are in the roadmap's 9j.7, 11.0, and steps 11c and 12; 9j.8's is done.
- Principle 4: audited 2026-10-17, all three passes, and on 2026-10-19 every `.get()`, `.setdefault()`, and `.pop()` whose default is computed rather than a constant; every violation is fixed, the dataclass defaults of pass 4a since 2026-10-20 (roadmap 9o).
- Principle 5: `mechanics/`, `npc/`, `game/`, and `ai/` audited 2026-10-18 and `datasworn/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level 2026-10-19, every pass, with the return values and the re-exports of each `__init__.py` read as symbols; the passes 5b to 5d covered the config sections each reads, the emotions yaml for `npc/`, the prompts and every field of the AI's answers for `ai/`, the Datasworn fields the loader keeps and the setting yaml for `datasworn/`, every availability rule against the four settings' moves and every field of the Director's tool answer for `tools/`, every field of the correction analysis's answer for `correction/`, every field of the models and of the config binding, read by attribute name, for the files directly under `engine/`, every field of the messages the server sends against what the page reads and every key of `strings/`, the ones built from a prefix checked against their domain values, for `web/` and the top level, and every config field that no code reads at all; principle 5 is done. Configuration and data whose consumer a roadmap step names stay and are listed there: the scene challenge (9k), the Meta handlers (9j.7), the companion and vehicle moves (19), Delve's moves (26), and Sundered Isles' ship creation (28).
- Principle 6: audited 2026-10-20 in roadmap step 9r, all three passes over every layer at once: the rule yaml of `gamemaster/`, `crafters/`, `ruleset/`, `engine/`, and `emotions/`, the rules in Python of those packages, of `game/`, and of the Director, and the prompts with the AI calls, each read against the first commit, EdgeTales of 31 March, the design document, and the books. Every finding has its place in a roadmap step or in the register; principle 6 is done until a later change adds a rule.

## Open

- Principle 2: `theme_die_table` in `crafters/adventure_crafter.yaml` repeats the random themes of `data/adventure_crafter.json`, and the loader checks the two against each other (`docs/mechanics.md`, Adventure Crafter tables); roadmap 9j.12, which reads the theme roll in the book, rolls it from the JSON instead.
- Principle 1 for `game/`, `ai/`, `tools/`, `correction/`, the files directly under `engine/`, `web/`, and the top level. Step 1a flags `web/handlers.py` (598 lines), `game/turn.py` (465), and `prompt_shared.py` (441).
