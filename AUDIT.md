# AUDIT

Operational document for Claude. Tells Claude how to audit this codebase against the five principles below. Stateful: the status section at the bottom tracks which principles have been audited and which are next.

## Why this document exists

Earlier audit attempts in this codebase produced false reassurances. Claude was asked "is the codebase config-driven?" and answered "yes" while significant parts were still hardcoded. This document exists to prevent that failure mode by removing yes/no questions from the audit interface and replacing them with exhaustive hit-lists that the user can verify.

Default behavior is full enumeration, not summary judgment. If a principle's audit produces a hit-list of zero items, that is the answer. If it produces 80 items, that is the answer. Both are valid; selective summary is not.

## Terms

**Chat.** A single continuous Claude.ai conversation, opened fresh with empty context, ending when the user signals completion. One chat may span multiple tool-budget cutoffs internally, but context, working files, and pending state carry across those cutoffs within the same chat. A new chat starts when the user opens a new conversation; previous chat context does not transfer except through this document and the fix-files it produces.

The unit "one chat" in this document means one such conversation, not one user message and not one tool-budget window. When the document says "one principle per chat" or "one submodule per chat", it means the full conversation, however long it runs, is dedicated to that scope.

## Reading order

Every audit chat must follow this order before producing any output:

1. Clone the repo if not already cloned.
2. Read `ARCHITECTURE.md` in full. This document defines what the codebase is, where things live, and which carve-outs apply to the strict rules. Audits without this context misclassify violations and carve-outs.
3. Read this document (`AUDIT.md`) in full.
4. Check the Status section at the bottom of this document. Identify the next open principle to audit, and within that principle the next open submodule (if the principle is being audited per submodule).
5. Then begin work on that principle, or that submodule within the principle.

## Chat scope

One audit chat covers exactly one of the following: one full principle, or one submodule within an interpretive principle that requires per-submodule work. Do not attempt to combine principles. If a principle finishes faster than expected, do not opportunistically start the next one — the energy budget for an audit chat belongs to the user, not to the LLM's sense of efficiency.

The mechanical principles (2, 4) are typically one principle per chat — the greps do the heavy lifting and the hit-list is compact. The interpretive principles (1, 3, 5) are typically one submodule per chat — each hit requires a short classification, `needs human judgment` items require explanation the user can act on, and the per-chat cost compounds with each submodule. The Status section tracks submodule-level progress for these.

Halfway is a legitimate stopping point. If a chat ends with three of seven submodules audited for Principle 1, that is a successful chat, not a failed one. Update the Status section to record progress and add a hand-off note in Notes for the next chat.

## Working method

The audit interface is a list of hits, never a verdict. The following rules apply to every audit, regardless of which principle is being audited.

**No yes/no questions.** Audit questions are reformulated as "where does the codebase fail principle X?" and the answer is a hit-list. Do not answer "is principle X satisfied" with "yes" or "mostly yes" — answer with the hit-list, even if the hit-list has zero items.

**Grep first, reason second.** For any pattern that can be expressed as a grep query, the grep is run before any reading or reasoning. The grep result is the candidate hit-list. Reasoning happens per-hit, not before the grep. Every grep query run in a chat is logged with its exact pattern and result count, and that log appears in the chat-summary so the user can verify which passes were executed. If a principle requires reasoning that cannot be reduced to a grep, state explicitly that this part is non-mechanical and proceed with file-by-file reading within a defined scope (typically one submodule at a time).

**Read context before classifying.** For each grep hit, open the file at the line and read at least 10 lines of surrounding context before classifying it as violation or carve-out. Do not classify based on the grep snippet alone.

**Carve-outs require an anchor in ARCHITECTURE.md.** A hit is a carve-out only if it matches an explicit exception documented in `ARCHITECTURE.md` (Project rules, Key Design Decisions, or a named pattern such as `get_raw` or the AI-call exception). Do not classify a hit as carve-out based on inference, plausibility, or "this looks reasonable." If a hit appears legitimate but no documented exception covers it, mark it as `needs human judgment`, not as carve-out.

**Mark uncertainty, do not resolve it.** For any hit where classification is unclear, mark it explicitly as `needs human judgment` with a one-sentence note about why. Do not guess. The user's review of these markers is part of the audit, not a sign of failure.

**No skipping based on file names.** The grep determines coverage. Do not skip files because they look uninteresting, deprecated, or out-of-scope. If a file should be excluded, the exclusion is encoded in the grep query, not in post-grep filtering.

**Dynamic access defaults to `needs human judgment`.** Symbols accessed via `getattr(obj, name)` where `name` is a variable, dict-keys constructed at runtime, fixture-injection, schema generation, or serialization are invisible to grep. Any symbol whose only writers or readers exist via these patterns is marked `needs human judgment`, not as dead. Do not declare a symbol dead based on grep alone if dynamic-access patterns exist anywhere in its module.

**No premature summary.** List every hit before producing any count or summary. The list is the audit. Counts and patterns come after the list, not instead of it.

**Cross-pass dedupe.** Several principles share grep-passes (Pass 2d and Pass 4a both examine dataclass defaults; Pass 3c and Pass 5e both examine single-use functions). Each violation is assigned to exactly one principle in the fix-file — the principle whose pass first surfaced it. When auditing a later principle that reuses an earlier pass, reference the earlier fix-file entry rather than re-listing the hit. If a violation legitimately fails two principles, name both principles in the single fix-file entry and assign it to the lower-numbered principle.

## Output

Each audit chat produces three artifacts:

1. **Fix-file** for the audited principle, named `fix_principle<N>.md` where `<N>` is the principle number (1 through 5). This file contains every violation found, with file path, line number, one-sentence classification, and (for clear violations) a brief note on what the fix should be. Carve-outs are not listed in the fix-file. `needs human judgment` items are listed with a separate marker so the user can review before the fix-round runs. When a violation also fails a different principle, both principles are named in the entry.

2. **Updated `AUDIT.md`** with the Status section reflecting what this chat covered — the full principle for mechanical audits, or the specific submodule(s) within a principle for interpretive audits. If notes for the next chat are relevant (e.g. patterns to watch for, where to pick up next), they go in the Notes section.

3. **Fix-file growth.** For interpretive principles spanning multiple chats, the fix-file is appended to across chats, not overwritten. Each chat's contribution is dated and labelled with the submodule audited.

4. **Summary message for the user.** Format: number of violations found in this chat, distribution by file as prose, number of items marked `needs human judgment` with file-and-line for up to five of them, and the grep log — every grep pattern run in this chat with its result count. Keep prose tight. The full hit-list lives in the fix-file. The summary exists for the user to verify proportions and pass-coverage, not to read the full audit.

## The five principles

Each principle below is the operational version. Philosophical motivation is intentionally omitted; this document is for executing audits, not for explaining the codebase.

### Principle 1 — High modularity

The codebase aims for one concern per file, with `.py` and corresponding `.yaml` paired where the module has configurable behavior. Smaller files are preferred over larger files when the responsibility can be split without forcing artificial abstractions.

This principle is interpretive. It is audited per submodule, not codebase-wide in one pass. For each submodule under `src/straightjacket/engine/`, list every Python file with its line count and its public functions. The audit proceeds in two separate steps — mechanical flagging first, concern-analysis second — and the two outputs are kept distinct in the fix-file.

**Step 1a — Mechanical flagging.** Flag every file that exceeds 400 lines. List file path and line count. Do not classify as violation based on line count alone — line count is a lookup signal, not a verdict.

**Step 1b — Concern analysis.** For each flagged file from Step 1a, plus every file the auditor has substantive reason to suspect (gut-feeling not allowed; the reason must be nameable, e.g. "this filename suggests two domains"), examine the public API. Classify as: violation (two or more clearly distinct concerns that could split without forcing artificial coupling), legitimate (one concern, file is large because the concern is large), or `needs human judgment` (split is non-obvious or would create artificial abstraction).

Carve-outs: re-export hubs (`models.py`, `__init__.py` files exposing subpackage public API) are not modularity violations. ARCHITECTURE.md "Subpackage public API via `__init__.py`" documents this pattern.

### Principle 2 — Config-driven

No hardcoded defaults in Python for values that belong in YAML. No hardcoded user-facing strings in Python. Anything that a translator, designer, or game-rules editor would want to change without touching Python belongs in YAML.

This principle is highly grep-able. Audit in the following passes:

**Pass 2a — Hardcoded user-facing strings.** Grep `src/straightjacket/` for string literals that match patterns of narration, error messages, UI labels, or AI prompts. Cross-reference against `strings/*.yaml`, `prompts/*.yaml`. A hit is a violation if the string is user-facing, narrator-facing, or AI-readable and is not loaded from a YAML file.

**Pass 2b — Hardcoded numeric thresholds.** Grep for numeric literals in domain modules (`mechanics/`, `npc/`, `game/`, `ai/`). Cross-reference against `engine/*.yaml`. A hit is a violation if the number represents a domain threshold, limit, or rule (e.g. damage cap, NPC limit, scene-type chance) rather than a structural constant (loop bound, enum value, list index).

**Pass 2c — Hardcoded mappings.** Grep for dict literals or set literals in domain modules that contain domain-data keys (move names, NPC dispositions, status names). A hit is a violation if the mapping should be in YAML for extensibility.

**Pass 2d — Dataclass defaults outside the three carve-outs.** Grep for `field(default=`, `field(default_factory=`, and direct `=` defaults on dataclass fields in `src/straightjacket/engine/`. A hit is a violation unless it matches one of the three documented carve-outs in ARCHITECTURE.md "Project rules": empty collections via `field(default_factory=list/dict)`, external-boundary parsing where the field is intrinsically optional per contract, or AI-call exception handlers per `provider_base.py`.

Carve-outs anchored in ARCHITECTURE.md: the `get_raw` pattern for yaml whose keys are domain-data, the AI-call exception carve-out for the named files, the `theme_die_table` cross-validation pattern.

### Principle 3 — No defensive programming, no boilerplate, no dead structure

Errors propagate. Guards against impossible states are violations. Try/except clauses that catch broad exceptions outside the documented carve-out are violations. Functions that exist to wrap a single call without adding logic are violations. Classes with one instance, options always set the same way, abstractions used in only one place — all violations.

This principle has both grep-able and reasoning components.

**Pass 3a — Broad except clauses outside the AI-call carve-out.** Grep for `except Exception`, `except:`, `except BaseException`. Cross-reference against the files named in ARCHITECTURE.md "Project rules" as AI-call carve-out files. A hit is a violation if it appears in any file outside that list, or inside one of those files but around a non-AI-call operation (config loading, yaml parsing, file persistence, input validation, domain-rule enforcement — these must raise even within carve-out files).

**Pass 3b — Defensive None checks on values that cannot be None per spec.** This is non-mechanical. Per submodule, list every `if x is None:` check on a value where the type signature does not include `None`. Per hit, classify as violation (the check guards against an impossibility) or legitimate (the check exists because the value can be None per a documented protocol).

**Pass 3c — Single-use abstractions.** For each function in a submodule, count callsites within the codebase. Flag any function called exactly once where inlining would not damage readability. For each class, count instances. Flag any class with exactly one instance where a module-level function would suffice.

**Pass 3d — Wrapper functions with no added logic.** Per submodule, list every function whose body is a single `return foo(...)` or `return self.foo(...)` call. Flag as violation if the wrapper adds no parameter transformation, no error handling, no caching.

Carve-outs: the AI-call exception carve-out for broad except clauses (ARCHITECTURE.md "Project rules"). Re-export functions in `__init__.py` files that constitute the documented public API.

### Principle 4 — No backwards compatibility

Save format breaks whenever the code requires it. No migration layer. No default-on-old-fields. No `ignore_unknown_fields`. Every dataclass field is required.

This principle is fully grep-able.

**Pass 4a — Dataclass field defaults.** Reuses Pass 2d output per the cross-pass dedupe rule. Every default outside the three carve-outs already counted under Principle 2 is referenced from this audit, not re-listed.

**Pass 4b — Migration patterns.** Grep for: `if .* in data`, `data.get(`, `try:.*KeyError`, `getattr(.*default`, comments mentioning "old format", "legacy field", "for backwards compat", "migration". Each hit is examined: is it accommodating an old save format? If yes, violation.

**Pass 4c — Permissive deserialization.** Grep for `**kwargs` in `from_dict`, `__init__`, or `SerializableMixin` overrides. Grep for `extra="ignore"` in pydantic models if any. Each hit is a violation.

Anchor: ARCHITECTURE.md "Project rules" — saves break whenever the code requires it, no migration layer, no default-on-old fields, no ignore-unknown-fields.

### Principle 5 — Clean codebase, no dead code, YAML-Python alignment

No dead Python symbols. No dead YAML keys. Every YAML key has a Python consumer; every Python config-access has a YAML key that supplies it. YAGNI, KISS, LEAN, DRY applied consistently.

This principle has multiple passes.

**Pass 5a — Dead Python symbols.** For each public symbol in `src/straightjacket/`, grep for usage across all five surfaces: `src/`, `tests/`, `engine/*.yaml` (string references in config), `prompts/*.yaml` (string references), `data/`. A symbol is dead if it has no reader, no writer beyond definition, on all five surfaces. Static-analysis tools (vulture, pylint) miss dict-assignment writes, getattr reads, fixture access, schema generation, serialization — do not rely on them as primary evidence; verify by grep across surfaces. Any symbol whose containing module uses dynamic access patterns (`getattr(obj, name)` with variable `name`, `globals()[name]`, `locals()[name]`, dict-key construction at runtime, fixture-injection by string, schema generation by introspection) defaults to `needs human judgment` rather than dead, even when grep returns zero hits.

**Pass 5b — Dead YAML keys.** For each YAML file under `engine/`, `strings/`, `prompts/`, `emotions/`, list every top-level and nested key. Grep `src/` for each key as string literal. Flag keys with zero hits in `src/` as candidates. Per candidate, check whether it is consumed via `get_raw` (key may be domain-data parameter, not directly grepped) or via a dataclass field (the dataclass field name should match). Mark unambiguous orphans as violations.

**Pass 5c — Dataclass fields without YAML source.** For each subsystem dataclass in `engine_config_dataclasses.py`, list every field. For each field, locate the corresponding YAML key. Flag fields with no corresponding YAML source as violations (these are fields that exist in Python but are never populated from config). Cross-pass dedupe: if Pass 2d already flagged the field as having an illegitimate Python default, reference Pass 2d rather than re-listing.

**Pass 5d — YAML keys without dataclass field.** Inverse of 5c. For each top-level YAML block in `engine/`, locate the binding dataclass. Flag YAML keys not present in any dataclass field as violations, unless the block is consumed via `get_raw`.

**Pass 5e — Single-use functions and classes.** Reuses Pass 3c output per the cross-pass dedupe rule. Single-use functions where inlining would not damage readability are referenced from Principle 3, not re-listed.

Carve-outs: explicit orphan-symbol carve-outs documented in `tests/test_project_rules.py` (e.g., `CharacterTraits`). Symbols where the consumer side is genuinely planned in a near-term roadmap step may be flagged with `needs human judgment` rather than as outright violations.

## Status

Update this section at the end of every audit chat. Do not delete completed entries; mark them as done. The history serves as a record of what was audited when.

Interpretive principles (1, 3, 5) are tracked per submodule. Mechanical principles (2, 4) are tracked per principle. A principle is fully audited when every submodule line is marked done.

Submodule list for interpretive principles: `mechanics/`, `npc/`, `game/`, `ai/`, `db/`, `datasworn/`, `tools/`, `correction/`, plus top-level `src/straightjacket/engine/` (the files directly under engine/, not in any subpackage) plus `web/`, plus top-level `src/straightjacket/` (`i18n.py`, `strings_loader.py`).

Principle 1, high modularity (per submodule):
- mechanics/: todo
- npc/: todo
- game/: todo
- ai/: todo
- db/: todo
- datasworn/: todo
- tools/: todo
- correction/: todo
- engine/ top-level: todo
- straightjacket/ top-level: todo
- web/: todo

Principle 2, config-driven: todo, not yet audited.

Principle 3, no defensive programming (per submodule):
- mechanics/: todo
- npc/: todo
- game/: todo
- ai/: todo
- db/: todo
- datasworn/: todo
- tools/: todo
- correction/: todo
- engine/ top-level: todo
- straightjacket/ top-level: todo
- web/: todo

Principle 4, no backwards compatibility: todo, not yet audited.

Principle 5, clean codebase and YAML-Python alignment (per submodule):
- mechanics/: todo
- npc/: todo
- game/: todo
- ai/: todo
- db/: todo
- datasworn/: todo
- tools/: todo
- correction/: todo
- engine/ top-level: todo
- straightjacket/ top-level: todo
- web/: todo

### Notes for the next chat

Empty. Add observations here that the next audit chat should know — patterns that emerged, scope adjustments made, ambiguities encountered, hand-off notes when a chat ended mid-principle.
