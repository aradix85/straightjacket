# Straightjacket — Roadmap

## Purpose

Internal working doc. Read after system prompt, ARCHITECTURE.md, codebase. What to build, in what order, with codebase-specific guardrails. Style and hard prohibitions live in system prompt.

Not committed to the repository. Lives locally.

Step sizing: one step = one session. Read codebase, implement, test, quality gate, delete obsoleted code, update roadmap. Reality diverges from roadmap during a step: update in the same commit. Never leave roadmap claiming something the code disagrees with.

## In-scope expansion

Scope is step description plus everything the work surfaces. Touched a file, saw a violation or bug: fix in same session.

Applies to: bugs in touched files regardless of step intent; absolute-rule violations (silent fallbacks, hardcoded domain strings, broad except without policy marker, dataclass defaults on config fields, inline imports without reason comment); untagged TODO or banner comments; docs-drift where step contradicts ARCHITECTURE/CHANGELOG; test-hygiene in touched tests (random.seed without teardown, module-state leak).

Stop and report only when: fix requires an architectural decision you can't take, or fix blocks the step by pulling in an unrelated subsystem. Don't silently split the step.

Not acceptable: "noted for later"; adding a TODO as closure; touching a file and leaving known violations; loosening the delivery gate because a fix breaks tests elsewhere (fix those too).

Post-flight grep is verification: hits not addressed in this commit = step not done.

## Tests are not the spec

Code leads. Tests verify code matches spec (step description + absolute rules + architecture), not the reverse.

Correct implementation breaks a test: test is suspect first. Read it. Identify which of three:

1. Tested old behavior this step replaces → rewrite for new behavior.
2. Tested an assumption that never held (self-confirming via same hardcoded value as production, like 0.63 secret-regex drift) → remove or replace.
3. Tested something now correctly defined elsewhere (strict yaml instead of silent default) → update setup.

Rarely: production is wrong. Becomes clear during reading — test reveals an invariant that should stay.

Not acceptable: changing code to make test green without reading it; `skip`/`xfail` as "temporary fix"; loosening assertion tolerance; building production around what test asserts if that conflicts with step spec; green via reintroduced silent fallback.

More than 10 tests red from one change: stop, report. Either scope is wider than expected, architectural decision surfaced, or suite is sicker than thought.

Rewriting a test: same commit as the code change. Tests and code that diverge and re-converge produce 0.63-class drift.

## After every step — post-flight

These checks run before declaring a step done. Never duplicated inside individual step sections; if they are, delete the duplication.

1. Quality gate: `pytest tests/ -q && ruff check && ruff format --check && mypy src`. Four passes. `test_project_rules.py` failures that measure residual debt are acceptable-red; every other failure is blocking.
2. Violation grep on touched files: `.get("..", ` on non-neutral literal; `or "..` on domain value; `except Exception` without policy marker. New hits not present pre-step = new violations, fix.
3. Legacy deletion confirmed in `git status`.
4. Roadmap updated: completed step moves to DONE with one-line summary; first next-steps entry promoted to NEXT and expanded (substeps, definition of done, patterns); Current state reflects any architectural decision taken during the step. md-files check: scan README, ARCHITECTURE, CHANGELOG, CONTRIBUTING, ORIGINS, SECURITY for claims invalidated by this step. Update what drifted, keep updates concise.

## Reference patterns (this codebase)

Templates for similar work. The validator stack (`ai/architect_validator.py`, `ai/chapter_validator.py`, `ai/validator.py`, `ai/rule_validator.py`) was removed in 27.8 and 27.9 as part of "AI-surface reduction over post-hoc validation"; do not use those files as patterns because they no longer exist and reintroducing the pattern works against the design decision (see Validator policy below).

- New AI-call wrapper: `ai/brain.py` (call_brain, call_revelation_check).
- New Director tool: `tools/builtins.py` (the existing `query_npc`, `query_active_threads`, `query_active_clocks` are the patterns — `@register("director")` decorator over a typed function returning a dict; type hints generate the OpenAI tool schema; the function reads from GameState and `db/queries.py`, never mutates).
- New strict nested domain lookup: `mechanics/stance_gate.py` (resolve_npc_stance).
- New yaml-backed config section: any entry in `engine_config.py` `_SIMPLE_SECTIONS` dict.
- New config dataclass: any in `engine_config_dataclasses.py` (required fields, no defaults).
- New narrator-facing template text: `prompts/*.yaml` for AI-facing, `strings/*.yaml` for user-facing, `engine/*.yaml` for engine-internal.
- New subpackage layout: `engine/correction/` — `__init__.py` re-exports public names, internal files split by responsibility.
- Large container split: `engine_config.py` + `engine_config_dataclasses.py` — orchestrator file re-exports from dataclasses file via explicit import list.

When adding a public `def`/`class` or a new `engine/*.yaml` top-level key, wire the consumer in the same commit. The orphan scans run as part of `test_project_rules.py` and reject definitions without callers as well as yaml keys without readers. Carve-outs exist for the legitimate exceptions (FastAPI route handlers, dataclasses bound only via parent-attribute, AICallSpec sub-fields) but the default expectation is that new code is consumed before merge.

## Test infrastructure

- `tests/test_project_rules.py`: 20 AST/regex scans enforcing absolute rules. Some scans may measure residual debt (acceptable-red). Run before starting a step to see current state; touched-files debt gets fixed in the same commit per the in-scope expansion rule. Three of the twenty are full-codebase consistency scans rather than per-rule pattern checks: `_check_ruff_format_clean` runs `ruff format --check` as a delivery-gate from inside pytest (catches format drift even when pre-commit is not installed locally), `_check_no_orphan_public_symbols` flags any public `def`/`class` in `src/` that has no consumer anywhere with a carve-out for terms truly used via parent-attribute or framework decorators, and `_check_no_orphan_yaml_keys` flags any top-level key in `engine/*.yaml` that has no Python reader (string-literal or dotted-path `get_raw`). The latter two would have caught the `move_routing.yaml` regression and the `drift_checks.py` residue had they existed in 27.10.
- `tests/elvira/elvira_config.yaml`: `full_debug_log: false`. One log file per run.

## Current state

Next feature step: Clock expansion (see below) — vol-consequenties plus creation from random events plus creation from AC plot-points.

Open architectural questions: none currently pending.

Forward-pointing decisions referenced by later steps:

Track-type composition (referenced by steps 25.1, 26.1, 31.1 as "Option C from the track-type decision"). Three options were considered for domain objects that own a progress track. Option A: `class ExpeditionData(ProgressTrack)` inheriting from ProgressTrack. Option B: registry pattern where ProgressTrack carries a `kind` discriminator and domain fields live as a sibling dict. Option C: composition, where the domain object holds a `progress: ProgressTrack` field plus its own fields. C was chosen. Reasons: ProgressTrack stays a single-purpose dataclass (rank, ticks, status); inheritance would push domain concerns onto a primitive used everywhere; registry pattern requires lookup indirection at every callsite. Composition keeps both layers cleanly separable, snapshot/restore works through SerializableMixin on either layer, and adding a fourth track-owning domain object requires zero changes to ProgressTrack itself.

Coverage-test precedent (28.3, referenced by step 13b): when a runtime filter excludes a class of moves (`available_moves` filters `no_roll` and `special_track` out of Brain's choice list), the contract that those moves carry a "real" categorisation is not enforceable through any code path. The 28.3 cleanup rewrote `test_every_datasworn_and_engine_move_has_category` to `test_every_implemented_move_has_real_category` — categorisation follows implementation, not anticipates it. If a future filter change brings `no_roll` moves back into Brain's view, those moves get categorised in the same commit as the filter change plus their outcome implementation, not pre-emptively.

Datasworn oracle cascade (introduced in 2026.05.11.0 threat creation step, referenced by future generator-framework callsites): `datasworn/cascade.py::roll_oracle_cascade` follows markdown-link IDs in oracle-row text (`[Label](id:setting/oracles/path)` syntax). Used by AC threat-naming to follow Delve's `threat/category` → sub-table chain. Generic helper, shared across future cascade-using callsites (step 9 generator framework, step 10 location/encounter generators).

Threat creation source-vs-naming pattern (introduced in 2026.05.11.0): two spawn-bronnen, twee naming-bronnen — random-event threats are named from the event's Mythic action+subject pair (the event already produced it); AC plot-point threats are named from a Datasworn cascade-roll on `oracle_paths.threats`. The principle: each source-system provides its own naming-input, not a forced single mechanism over both. Future spawners that introduce new entity-types follow the same axis — let the source provide what it naturally has.

---


## NEXT STEP — Clock expansion: vol-consequenties plus creation from random events plus creation from AC plot-points

Three concerns about clocks bundled in one step. After this step, clocks are a fully autonomous mechanic: ze ontstaan uit meerdere bronnen, evolueren via tikken, eindigen met betekenis ook zonder gekoppelde keyed-scene. Combined with the threat-creation step that landed in 2026.05.11.0, both `threat_menace_phase any:N` and `clock_fills any:N` patterns get real entities to bind to.

Concern one — vol-consequenties when no keyed-scene attached. Currently a clock that fills only does something if a keyed-scene happens to be tied to it via the 7c clock-spawner; without that link, the clock fills silently. Per clock-type a default consequence fires. Fallback path: when keyed-scene attached, the keyed-scene wins and the default is suppressed.

Concern two — clock creation from random events. Mythic event-focus categories that imply approaching pressure (selected `pc_negative`, `move_toward_thread`, `move_away_from_thread`) can create a fresh `ClockData` with rank-derived segments, naming from the event's Mythic action+subject pair (mirrors threat-creation precedent). Once created, the clock automatically gets per-fraction keyed-scenes via the 7c clock-spawner.

Concern three — clock creation from AC plot-points. AC plot-points whose name implies a deadline (`Time Limit`, `A Crucial Life Support System Begins To Fail`, `A Needed Resource Runs Out`, `Impending Doom`) create a fresh `ClockData` at chapter-start. Naming via Datasworn oracle cascade (mirrors threat-creation precedent — reuse `oracle_paths.threats` or add `oracle_paths.deadlines` per setting if cascade-content differs; resolve during implementation).

### Substeps

**Clock-spawn-1** Vol-consequenties. Yaml-mapping per clock-type in new `engine/clock_consequences.yaml`: `threat` → menace-escalation tag plus narrative-hint, `scheme` → faction-action tag (couples with step 14b/15; for now no-op or stub), `progress` → quest/expedition resolution (couples with `complete_track` already in `game/tracks.py`). Dataclass binding in `engine_config_dataclasses.py`. Vol-check fires when `clock.fired` transitions to True. Fallback: skip default-consequence when an attached keyed-scene has source-prefix matching this clock's id (clock-spawned keyed-scenes from 7c). Implementation in `mechanics/consequences.py` or new `mechanics/clock_consequences.py` — decide during implementation per file-size.

**Clock-spawn-2** Random-event clock spawner. New mapping in `engine/random_events.yaml::clock_creation_mapping` per event-focus: `pc_negative`, `move_toward_thread`, `move_away_from_thread` get rank-config entries. Spawner `spawn_clock_from_random_event(game, event) -> ClockData | None` in `mechanics/random_events.py`. Wired into `generate_random_event` after the keyed-scene-spawner and after `spawn_threat_from_random_event` (a random event can produce up to three entities — keyed-scene, threat, clock — depending on mapping coverage). Dedup via `clock.creation_source` field (new — `ClockData` veld toevoegen, mirror van `ThreatData.creation_source` patroon). Cap via `engine/clocks.yaml::max_clocks_per_chapter` (new key).

**Clock-spawn-3** AC plot-point clock spawner. New mapping in `engine/adventure_crafter.yaml::clock_creation_mapping`. Spawner `spawn_clocks_for_turning_point(game, turning_point) -> int` in `mechanics/adventure_crafter.py`. Wired into `assemble_blueprint_seed_from_ac` after `spawn_threats_for_turning_point`. Same dedup pattern via `clock.creation_source`. Same cap field shared across both spawn-bronnen, mirroring the threat-creation pattern.

**Clock-spawn-4** Tests: each spawner produces valid `ClockData` for mapped sources; unmapped sources skip silently; dedup holds; cap respected across both bronnen; vol-consequences fire per clock-type when no keyed-scene attached; vol-consequences suppressed when an attached keyed-scene matches the clock; `clock_fills any:N` keyed-scene fires after spawn when clock reaches the fraction.

### Definition of Done

- Clock creation from random events and AC plot-points works end-to-end: a random-event of mapped focus or an AC turning-point with a mapped plot-point places a `ClockData` on `game.clocks` (or wherever clocks live — verify during implementation).
- Vol-consequenties fire per clock-type when no keyed-scene attached; suppressed when one is.
- Existing 7c-spawned `clock_fills any:N` keyed-scenes can now actually fire because clocks exist mid-game.
- Quality gate green (pytest, ruff check, ruff format, mypy).
- Save format breekt door `ClockData.creation_source` veld; geen migratie per project-policy.
- ARCHITECTURE.md: extension of the threat-creation Key Design paragraph to include clock-creation in the same spawn-source-vs-naming-source pattern; module-ownership-rij voor clock creation; mention of `clock_consequences.yaml` if it lands.
- CHANGELOG entry.

### Reference patterns

- Threat creation step (2026.05.11.0): mapping-block in yaml, dataclass-binding, spawner-function, dedup via `creation_source` veld, cap shared across spawn-bronnen, wired in same callsites as keyed-scene-spawner. Clock creation follows the same shape — extend the existing precedent, do not invent a new pattern.
- Naming via cascade: `datasworn/cascade.py::roll_oracle_cascade` already exists from threat-creation. Reuse for AC clock-naming if cascade-content fits, else add new `oracle_paths.deadlines` field.
- Vol-consequenties suppression: pattern is "engine-emitted tag unless engine-emitted keyed-scene takes over". Source-prefix-check on attached keyed-scenes against the firing clock's id; same dedup-via-source mechanism as 7c keyed-scene-spawning.

---

## Next steps

Sketches and drafts. Order indicative, not fixed. Each entry needs substeps + definition of done + patterns before scheduling — that work happens during post-flight of the step that promotes this one to NEXT, not pre-emptively. Some entries below already have substeps drafted; those promote with less work, but Definition of Done and Reference patterns still get filled in at promotion time.

### 9 — Generator framework

Dependency: parent-chain settings resolver exists in `datasworn/settings.py` — `_resolve_oracle_paths`, `_resolve_creation_flow` plus `SettingPackage.oracle_data_for` walk the chain. (`_resolve_genre_constraints` was removed in 27.10 along with the GenreConstraints dataclass.)

The generator framework is the single engine entry-point for content the fiction needs but the game-state does not yet hold. Two consumption shapes the framework must handle, called out explicitly so step 10 plus 11 plus 25 plus 26 can build on a stable contract: entity-creation (a new settlement, location, NPC, or encounter is brought into being from a category and context — what the design document calls "fiction generation") and fact-resolution (a player action references an attribute of an existing entity that has not yet been determined — door is locked or not, NPC is alert or not, kamer holds an item or not — what the "Engine-resolved fiction" Key Design Decision calls for). Both flow through the same callable surface so that the consumer code never needs to choose between "generate" and "resolve" at the callsite — the framework determines from category+context whether to roll on a structure-table or a fate-question.

**9.1** Entry point `generate(game, category, context) -> dict`. Starting categories: settlement, location, npc, encounter (entity-creation), plus fact (fact-resolution: takes a fact_type + entity_ref, returns boolean or enum value). Extensible — step 25 adds waypoint, step 26 adds site, step 11 adds npc tiers. Registry or yaml-lookup, not closed Python enum. The fact category routes through `mechanics/fate.py::resolve_fate` with odds derived from context per `engine/fate.yaml::likelihood_rules`; entity categories route through Datasworn oracle rolls per category-specific paths.

**9.2** Oracle accessor handles Delve theme+domain, Sundered Isles cursed/non-cursed variants, Starforged flat d100. Format detection from setting yaml, not Python branching on setting name.

**9.3** Per-category oracle paths in setting YAML. Missing path = KeyError. The `fact` category does not need oracle paths — it consults fate, not Datasworn — but its odds-derivation rules live in `engine/fact_resolution.yaml` (new) keyed by fact_type, with explicit raise-on-unknown-fact-type.

**9.4** Generated content rendered through the setting's `vocabulary.substitutions` in the narrator prompt. No post-hoc validator (see Validator policy). The substitution is the constraint: if the oracle returns "spaceship", the prompt receives the setting's substitution (e.g. "starship — worn, patched") before reaching the narrator.

**9.5** AI-data-aanvoer: generated entity dicts and resolved facts are injected into the narrator prompt as structured `<generated>` and `<fact>` tags, not surfaced via tool-call. Rationale: this data is always relevant for the call that triggered it (the narrator is about to describe the entity or react to the resolved fact in this turn) and the payload is bounded (one entity dict, one fact result). Tool-calling here would add a roundtrip without the AI making a meaningful selection — engine has already determined what is relevant. Per the "When tool-call vs when prompt-inject" Key Design Decision in ARCHITECTURE.md.

**9.6** Tests: smoke with stub oracle data, category registry accepts additions, fact-resolution returns deterministic value for fixed-seed RNG, unknown fact_type raises.

Done: callable framework, returns structured output, both entity-creation and fact-resolution paths working. New category = yaml + minimal registration only.

### 10 — Location and encounter generators

**10.1** Location generator via step 9 framework. Datasworn oracles → structured location. AI for description constrained by oracle output.

**10.2** Encounter generator weighted by location properties + active threats + chaos. Oracle for structure, AI for description. Weights in `engine/encounter_weights.yaml` (new).

**10.3** Prompt budget: `<generated>` tags replace unstructured invention. Net near zero.

**10.4** Brain integration: encounter output flows into Brain context as structured data via existing state path. Couples forward to steps 12 and 25.

**10.5** Tests.

Done: locations and encounters from oracles + AI description. Brain context extensible.

### 11 — NPC generation with tiers

**11.1** Tier 1 (throwaway): oracle rolled demeanor + name + disposition, no AI. Specific oracle paths required in `data/settings/*.yaml::oracle_paths.npc_demeanor` and `oracle_paths.npc_disposition` (new keys); existing `oracle_paths.names` provides the name. Missing path = KeyError per the strict-rules. No AI call for tier-1 — the narrator receives the rolled values as structured prompt context and writes the NPC into the scene.

**11.2** Tier 2 (recurring): full AIMS + goal-clock, AI for AIMS only. AIMS generation goes through Director (existing AI role) with two-phase tool loop: Director queries `query_npc(npc_id)` for the rolled tier-1 base plus `query_active_threads()` for narrative context, then writes AIMS via json_schema. Per the "When tool-call vs when prompt-inject" Key Design Decision: NPC base data comes via tool-call because Director is best-positioned to decide whether the existing relations matter for this AIMS; thread context same. Other context (current location, faction state once step 14 lands) is prompt-injected because it is always relevant.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new). Default: 3 interactions in 5 scenes. DB query.

**11.4** `tier` field on NpcData as config-key string, not Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed oracle rolls; tier-2 promotion fires AIMS-generation only when promotion triggers; missing oracle_paths.npc_demeanor or npc_disposition raises KeyError.

Done: tiered NPCs, promotion works, new tier = yaml only.

### 12 — NPC goal-clocks and autonomous actions

Builds on step 11. Extends existing `check_npc_agency` (config-driven `pacing.npc_agency_interval`).

**12.1** Optional `goal_clock: ClockData | None` on NpcData. Persisted. DB-indexed.

**12.2** Tick after scene-end bookkeeping. Triggers in `engine/npc_goal_clocks.yaml` (new): bond_below_N, health_below_N, scene_count threshold. Deterministic.

**12.3** Filled clock → `<npc_action>` tag. Action generation behind callable abstraction so step 13 can swap source (meaning table → fate question) without rewriting clock-fill handler. Default: meaning table + engine templates → tag. Templates in yaml.

**12.4** Director sets goal-clock on NPC promotion to recurring. Decision at this step's callsite: either `engine/clock_keyed_scenes.yaml` gains a `goal` clock-type (small priority, full-fill only) and the callsite invokes `spawn_keyed_scenes_for_clock(narrative, clock)` from 7c, or NPC goal-clocks are deliberately exempted from per-fraction keyed-scenes because the goal-clock-fill itself is already the `<npc_action>` event. Pick one in the implementation commit; if exempt, document why in CHANGELOG so the pattern stays consistent across all other clock-creation sites.

**12.5** Prompt budget: 1 `<npc_action>` per scene cap, config-driven. AI-data-aanvoer: the engine-rolled action descriptor lives in the narrator prompt as a structured `<npc_action>` tag (always relevant when present, bounded payload, no AI selection needed) — not surfaced via tool. Per the "When tool-call vs when prompt-inject" Key Design Decision. (Originally a validator substep; dropped per Validator policy. Engine sets the tag, narrator is asked to reflect it; no retry-validator on output.)

Done: goal-clocks tick on triggers, filled → action tags, abstraction survives step 13 swap.

### 13 — NPC behavior via fate

Fate + AIMS-derived expected behavior. Data: `mythic_gme_2e.json` → `npc_behavior`. Engine derives expected from AIMS + stance, asks fate question, interprets. Move list + cooldown as refinement. Replaces step 12.3 callable.

Trigger timing: once per scene, after scene-end bookkeeping. Only goal-clock + AIMS NPCs eligible. Max 1 per scene.

### 13b — Unimplemented Datasworn mechanics

Datasworn covers 122 unique move stems across the four shipped settings; 56 are implemented as formal moves in `engine/move_outcomes.yaml`. The remaining 66 split into three groups by destiny: 33 are asset-dependent (covered by step 18-20), 6 are setting-specific or step-bound (covered by steps 25, 26, 28), and roughly 27 are general-mechanic moves not yet wired. Step 13b wires the general-mechanic group following the "Datasworn mechanic naming" Key Design Decision in ARCHITECTURE.md: a move that represents a player choice with structured outcome lands as a formal move in `move_outcomes.yaml`; a move that fires automatically when a mechanical condition becomes true lands as an engine-trigger with a direct name like `advance_menace_on_miss`.

Group A — formal moves (player choice, structured outcome). Add to `engine/move_outcomes.yaml` plus `engine/move_categories.yaml` per the existing patterns. Brain receives them in its filtered moves list. Roughly: `combat/turn_the_tide` (once-per-fight momentum burn), `adventure/aid_your_ally` and `relationship/aid_your_ally` (player supports an ally — requires NPC-action context already present after step 11), `relationship/write_your_epilogue` (special-track on retire — couples with step 3 succession's existing retire flow), `scene_challenge/begin_the_scene` (opens a progress track — couples with the existing scene_challenge moves), `failure/learn_from_your_failures` (special-track), `threat/take_a_hiatus` (downtime-in-safe-place), and the four progress-mark moves `legacy/advance`, `legacy/earn_experience`, `quest/advance`, `quest/reach_a_milestone` (simple progress-tick handlers).

Group B — engine-triggers (consequence, automatic). Direct names that say what the code does, no formal move-shape. `mark_failure_on_miss` (Datasworn `failure/mark_your_failure`, fires on MISS, marks a failure-track segment), `face_setback_at_min_momentum` (Datasworn `suffer/face_a_setback`, fires when momentum would drop below -6, redirects loss), `mark_supply_depletion` (Datasworn `suffer/out_of_supply`, fires when supply hits 0, queues Wounded plus Shaken on next opportunity), `face_defeat_on_objective_loss` (Datasworn `combat/face_defeat`, fires on objective abandonment — uses existing combat-state). The existing `advance_menace_on_miss` already exemplifies the pattern and stays as-is; Datasworn `threat/advance_a_threat` is conceptually that mechanic. The existing `pay_the_price` engine-trigger stays as-is; Datasworn `fate/pay_the_price` is conceptually that.

Group C — covered elsewhere or deliberately not wired. `legacy/continue_a_legacy` is fully covered by step 3 succession under a different name; not added. `fate/ask_the_oracle` overlaps with the engine-eigen `ask_the_oracle` in `engine_moves.yaml` which is the working dialog-shape; not duplicated. `threshold/overcome_destruction` is Sundered-Isles-ship and lands in step 28. The five session moves are deliberately not on the roadmap (see Current state).

**13b.1** Group A formal moves added to `engine/move_outcomes.yaml`, with appropriate categorisation in `engine/move_categories.yaml`. Outcome handlers reuse existing patterns (progress-mark, momentum-shift, special-track) — no new handler type unless one move's spec genuinely demands it.

**13b.2** Group B engine-triggers added at the right callsite. `mark_failure_on_miss` in `mechanics/consequences.py` near the existing MISS-resolution. `face_setback_at_min_momentum` in `mechanics/consequences.py` at the momentum-clamp boundary. `mark_supply_depletion` in the same file at the supply-zero check. `face_defeat_on_objective_loss` in `mechanics/threats.py` or `game/finalization.py` per where objective-state transitions happen. Each callsite emits an appropriate `<consequence>`-tag for the narrator and updates the corresponding game state. Where `scene_challenge/begin_the_scene` (Group A) creates a fresh scene-challenge clock, the same callsite invokes `spawn_keyed_scenes_for_clock(narrative, clock)` from 7c so per-fraction keyed-scenes attach automatically — same pattern any new clock-creation site uses going forward.

**13b.3** Per-trigger config in the relevant `engine/*.yaml` files (failure-track length, setback-redirect rules, supply-depletion impacts) — no domain values hardcoded in Python.

**13b.4** AI-data-aanvoer: all triggered events surface as structured tags in the narrator prompt (`<consequence>`, `<failure_marked>`, `<setback>`, `<supply_depletion>`, `<defeat_faced>`); always relevant when present, bounded payload, no tool-calling needed. Per the "When tool-call vs when prompt-inject" Key Design Decision.

**13b.5** Tests: each formal move resolves through the existing move-outcome pipeline; each engine-trigger fires under its precise condition; existing `advance_menace_on_miss` regression-tested to confirm the broader pattern stays consistent; ARCHITECTURE.md's Datasworn-naming paragraph cited in the relevant test docstrings is not required (no docstrings rule), but commit message references the principle.

Done: roughly 11 formal moves and 4 engine-triggers added; total Datasworn move-stem coverage in `move_outcomes.yaml` rises from 56 to 67; engine-trigger coverage gains 4 named triggers alongside the existing `advance_menace_on_miss` and `pay_the_price`. Asset-dependent and setting-bound moves remain untouched (their roadmap stops own them).

### 14a — Faction data model

**14a.1** FactionData dataclass: name, goal, tenets, members (NPC ids). Required fields. Extension-ready: step 16 adds reputation.

**14a.2** `faction_id` on NpcData.

**14a.3** Faction table in DB. Roundtrip via SerializableMixin.

**14a.4** Tests: NpcData + FactionData roundtrip, members link from NPC to faction holds across save+load.

Done: factions are a persisted data model. No behaviour yet — that comes in 14b.

### 14b — Scheme-clocks and chapter-spanning factions

Dependency: 14a complete (FactionData persists).

**14b.1** Scheme-clocks per faction. Tick every N scenes (`engine/factions.yaml` → `scheme_clock_interval`, new file). Fill → queue faction event. Where the scheme-clock is created at faction-construction time, the same callsite invokes `spawn_keyed_scenes_for_clock(narrative, clock)` from 7c so per-fraction keyed-scenes attach automatically (config in `engine/clock_keyed_scenes.yaml::scheme` already covers the `scheme` clock-type since 7c).

**14b.2** Snapshot/restore. ChapterSummary gains a `factions: list[FactionData]` field; `_close_previous_chapter` captures, `_reset_chapter_mechanics` zeros, `_restore_chapter_mechanics` replays — same three-place pattern as the existing chapter-spanning fields.

**14b.3** Datasworn faction oracles for generation: pull faction archetypes per setting from `data/settings/*.yaml::oracle_paths.factions` (the yaml-keys are already present in classic, starforged, and sundered_isles settings; the corresponding Python field was removed in 27.9 because no consumer existed yet, and step 14b is the consumer that justifies its return). Add `factions: str` back to `OraclePaths` dataclass in this step's commit; missing path on a setting that has factions = KeyError per strict-rules. The yaml-keys stop being orphans the moment 14b lands.

**14b.4** AI-data-aanvoer: faction-event tags in the narrator prompt are prompt-injected (always relevant when fired, bounded payload). Director gains a new `query_faction(faction_id)` tool for use during NPC-reflection generation when the NPC's faction context is selectively relevant — Director decides whether to call. Per the "When tool-call vs when prompt-inject" Key Design Decision: prompt-injection for narrator, tool-call for Director where Director-side selection makes sense.

**14b.5** Tests: scheme-clock ticks, faction event queues, snapshot+restore through a chapter boundary.

Done: factions tick independently, persisted through snapshot+save+chapter.

### 15 — Faction prompts and status

**15.1** Prompt builders include faction context for activated NPCs (~15 tok/NPC). Budget in `engine/factions.yaml`.

**15.2** `<faction_event>` tag on scheme-clock fill (~30 tok). Templates in yaml.

**15.3** `/factions` status command. Narrative form. Strings in strings/*.yaml.

**15.4** AI-data-aanvoer: faction context for activated NPCs and `<faction_event>` tags are prompt-injected (always relevant when present, bounded payload). The `query_faction(faction_id)` Director tool from step 14b stays available for selective access during reflection-generation. Per the "When tool-call vs when prompt-inject" Key Design Decision.

**15.5** Tests. (Originally a validator substep on `<faction_event>` reflection; dropped per Validator policy. Engine sets the event, narrator prompt asks for it, no post-hoc check.)

### 16 — Faction reputation + NPC loyalty

**16.1** Player reputation per faction: hostile/neutral/allied. Extreme overrides personal bond in stance resolver. Thresholds in yaml.

**16.2** NPC loyalty derived from faction bond vs player bond via connection tracks. No new NpcData field.

**16.3** Reputation field added to FactionData (extension point reserved in 14a.1).

### 17 — Setting enrichment — ONGOING

Data work, no architecture. Non-blocking.

**17.1** Per setting per category: 200+ names in setting YAML `extended_oracles.names`.

**17.2** Per setting: location descriptors in `extended_oracles.locations`.

**17.3** Per setting: NPC descriptors in `extended_oracles.npcs`.

**17.4** Per setting: extended sensory in `vocabulary.descriptions`.

Done: all four settings enriched. (17.5 — atmospheric drift detection update via rule validator drift wordlists — was deleted; the rule validator no longer exists. New vocab additions land in `vocabulary.substitutions` and `vocabulary.descriptions`, which feed the narrator prompt per turn.)

### 18a-i — Asset state migration

The current `assets: list[str]` field on GameState carries asset IDs only — assets have no mechanical effect today. This step migrates the field to a typed dataclass. The pipeline that evaluates modifiers ships in 18a-ii. Between 18a-i and 18a-ii the engine is in a transient state where AssetState exists but no modifier evaluation runs — acceptable because assets had no mechanical effect before either, so no regression.

**18a-i.1** AssetState dataclass: required fields are `id: str` plus the four modifier fields (`stat_bonuses: list[StatBonus]`, `rerolls: list[Reroll]`, `extra_effects: list[ExtraEffect]`, `condition_track: ConditionTrack | None`). Empty collections via `field(default_factory=list)` per absolute rules — empty list is absence of data, not a default. Modifier sub-dataclasses (StatBonus, Reroll, ExtraEffect, ConditionTrack) defined with required fields, no Python defaults on values.

**18a-i.2** SerializableMixin roundtrip on AssetState and the four sub-types. `assets: list[str]` becomes `assets: list[AssetState]` on GameState. Save format breaks; no migration (alpha invariant).

**18a-i.3** All callsites updated in this step (per absolute rules — when something changes, every caller updates in the same session). Eight src callsites and four test fixtures. `mechanics/legacy.py::advance_asset` continues to work on the `id` field; `chapters.py` snapshot/restore updated to copy AssetState via dataclass roundtrip rather than list-of-string copy; `succession.py` carryover updated. ChapterSummary.assets parallel field migrated to `list[AssetState]` for type symmetry. `loader.py` and `serializers.py` Datasworn-side stays on its own type — those read raw Datasworn JSON, not GameState.

**18a-i.4** Tests: AssetState roundtrip survives save+load with all four modifier fields populated and empty; chapter snapshot+restore preserves AssetState identity; succession carryover preserves AssetState; existing tests that pass `assets=["asset_x"]` rewritten to `assets=[AssetState(id="asset_x", ...)]` with required fields filled.

Done: AssetState is the live type for `game.assets`. Save format current. No modifier evaluation yet — that ships in 18a-ii.

### 18a-ii — Modifier pipeline

Dependency: 18a-i complete (AssetState live).

**18a-ii.1** Pipeline handles all four modifier types day one: stat_bonus, reroll, extra_effect, condition_track. New module `mechanics/asset_modifiers.py` with one entry-point `evaluate_modifiers(game: GameState, context: ModifierContext) -> ModifierResult`. ModifierContext carries the move category, current stat values, current dice; ModifierResult carries computed stat deltas, granted rerolls, queued extra effects, condition-track deltas.

**18a-ii.2** Stacking + eval order in `engine/asset_modifiers.yaml` (new). Per modifier type the yaml lists how multiple instances combine (sum, max, multiply) and in what order types are evaluated against each other. Pipeline reads order from yaml; adding a fifth modifier type needs only new dataclass + new yaml block + new handler — pipeline structure unchanged.

**18a-ii.3** Momentum burn timing: modifiers evaluated after upgrade, before re-resolve. Hooks into `mechanics/consequences.py::roll_action`. The hook reads from `game.assets`, builds ModifierContext, evaluates, applies result deltas to the in-flight roll resolution.

**18a-ii.4** Tests: each modifier type evaluates correctly in isolation; two-modifier stacking respects yaml eval order; momentum burn re-evaluates modifiers (regression on the existing momentum-burn tests confirmed clean); pipeline does not break when a fifth modifier type is added (test introduces a synthetic fifth type via a temporary yaml override and confirms pipeline shape).

Done: pipeline operational with at least one synthetic test asset per modifier type. No Datasworn assets loaded yet — that ships in 18b.

### 18b — Datasworn asset integration

Dependency: 18a-ii complete.

**18b.1** 5-10 representative Datasworn assets per setting selected, collectively exercising all four modifier types. Loaded into the pipeline.

**18b.2** Prompt budget: existing consequence tags (~40 tok). (Originally a validator substep on asset condition tags; dropped per Validator policy. Engine sets the asset state, prompt asks the narrator to reflect it, no post-hoc check.)

**18b.3** Tests: representative assets resolve through pipeline; AssetState changes survive save+load; modifier stacking honoured per yaml eval order.

Done: representative assets end-to-end, pipeline proven for all four types under real Datasworn data, step 20 (full per-setting rollout) won't need rewrites.

### 19 — Companion and vehicle assets

**19.1** Companion health tracks (not NpcData).

**19.2** Vehicle condition tracks. Withstand Damage = suffer move on vehicle condition.

**19.3** Setting-specific companion/vehicle assets.

**19.4** `/assets` status command.

**19.5** Companion/vehicle extends `<character_state>`. Template in engine yaml.

**19.6** Tests.

Done: companions+vehicles functional, status command works.

### 20 — Asset rollout — PER SETTING

One session per setting. All assets from Datasworn loaded and functional with step 18 pipeline.

**20.1** Starforged. **20.2** Classic. **20.3** Delve. **20.4** Sundered Isles.

Pipeline needs fix for any asset: fix pipeline, not per-setting patches.

### 21 — Relationship event detection

**21.1** Events enum in `engine/relationship_events.yaml` → `types`: promise_broken, betrayal, sacrifice, debt_owed, debt_repaid, loyalty_shown. Extensible.

**21.2** Metadata extractor detects events. New field `relationship_events: list[{npc_id, event_type, description}]`.

**21.3** Persist as `relationship_events: list[RelationshipEvent]` on NpcData. Snapshot/restore. Events engine-internal — feed steps 22 and 23, not surfaced directly.

**21.4** Tests.

### 22 — Emotional requests

**22.1** NPC-to-player requests. Engine generates from NPC state (disposition, bond, recent events). Rules + templates in `engine/emotional_requests.yaml` (new).

**22.2** `<emotional_request>` tag in narrator prompt.

**22.3** `pending_request: str | None` on NpcData. One per NPC.

**22.4** Prompt budget: per-NPC-with-request (~40 tok), config cap. (Originally a validator substep on emotional-state reflection; dropped per Validator policy.)

**22.5** Tests.

### 23 — Refusals, concessions, relationship effects

**23.1** Brain classifies player responses to requests as granting/denying.

**23.2** `concessions: int`, `refusals: int` on NpcData.

**23.3** Refusal/concession affects bond via connection track + stance matrix. Per-event weights in `engine/relationship_events.yaml` → `effects`.

**23.4** Tests.

### 24 — NPC-NPC triangles involving the player

NPC-to-NPC requests and triangles scoped to those that involve the player directly. Inter-faction emotional dynamics are out of scope per the dynamic relationship layer boundary in ARCHITECTURE.md — faction-level independence runs through schemes and scheme-interactions (steps 14, 15, 16), not through a separate faction-emotion layer.

### 25 — Expedition moves and waypoints

Uses Option C from the track-type decision in Current state: ExpeditionData dataclass with `progress: ProgressTrack` field plus its own expedition-specific fields.

**25.1** Expedition data model: destination, rank, progress track, waypoints, dangers. ExpeditionData dataclass with `progress: ProgressTrack`.

**25.2** Expedition moves: Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish, Set a Course. Move routing config-driven.

**25.3** Waypoint generation via step 9 framework — new category in yaml.

**25.4** Scene structure: each waypoint = scene boundary, chaos check.

**25.5** Prompt budget: ~30 tok when expedition active. AI-data-aanvoer: expedition state (destination, current waypoint, dangers seen so far) is prompt-injected into the narrator prompt — always relevant for any scene during an active expedition. Director gains a new `query_expedition()` tool for use during chapter-summary or recap generation when expedition history is selectively relevant. Per the "When tool-call vs when prompt-inject" Key Design Decision.

**25.6** Tests.

Done: expedition loop with scene structure + progress tracks, waypoint category registered.

### 26 — Site exploration data model and Delve

Uses Option C from the track-type decision: SiteData dataclass with `progress: ProgressTrack` field plus site-specific fields.

**26.1** Site dataclass: name, objective, theme, domain, rank, progress track, denizen matrix, discovered features, active dangers. One model for all settings (step 27 reuses). SiteData dataclass with `progress: ProgressTrack`.

**26.2** Theme + domain from Datasworn. Delve: 8 themes × 10 domains with features + dangers tables.

**26.3** Denizen matrix (Delve): per-site d100. Four ranges: common, uncommon, rare, unforeseen. Boundaries in per-setting config.

**26.4** Delve moves: Discover a Site, Delve the Depths, Find an Opportunity, Reveal a Danger, Locate Your Objective, Escape the Depths. Routing config-driven.

**26.5** Prompt budget: ~60 tok. Cap discovered features to 3 most recent. AI-data-aanvoer: active site state (theme, domain, current depth, recent discoveries) is prompt-injected. Director gains a `query_site_features(site_id)` tool for selective access to the full discovered-features list during NPC-reflection or chapter-summary generation. Per the "When tool-call vs when prompt-inject" Key Design Decision.

**26.6** Tests.

Done: Delve end-to-end, model generic for step 27.

### 27 — Sites for Starforged and Sundered Isles

**27.1** Starforged: derelicts, precursor vaults, location themes as site configurations. No Python — data config on step 26 model.

**27.2** Sundered Isles exploration as site configurations.

**27.3** Tests.

Done: three settings use site model via data config, no setting-specific Python branches.

### 28 — Sundered Isles specifics

**28.1** Ship mechanics: command vehicle with modules, condition track, repair. Via step 18/19 asset pipeline. No ship-specific pipeline.

**28.2** Cursed dice: the "cursed" impact, when present, forces rolls to be made with disadvantage (lowest of two challenge dice). This is a roll-modifier driven by impact state, not an asset modifier — `mechanics/consequences.py::roll_action` gains an impact-aware branch that checks for the cursed impact before resolving. New entry in `engine/impacts.yaml` for the cursed impact metadata. Step 18's asset pipeline is not extended for this.

**28.3** Data config: naval encounters, treasure, SI oracles (16 categories), SI exploration.

**28.4** Tests.

Done: SI fully playable, no SI-specific Python outside config registration.

### 29 — Crew mechanics

Sundered Isles crew/morale system.

### 30 — Player vs PC knowledge

Four strategies in `mythic_gme_2e.json` → `player_vs_pc_knowledge`: Test-Ask-Real (default), Reliable vs Unreliable, Going With It, Extra Knowledge as RP. New field `knowledge_status: str` on RandomEvent + NpcData secrets. Values: engine_only, pc_confirmed, pc_denied. Strategy in `engine/fate.yaml`.

### 31 — Thread progress tracks and discovery checks

Uses Option C from the track-type decision: ThreadTrackData dataclass with `progress: ProgressTrack` field plus thread-specific fields.

**31.1** Thread progress tracks: focus thread linked to track, three lengths (10/15/20), phases of 5, forced Flashpoints at phase boundaries without one. Phase lengths + flashpoint rules in `engine/thread_tracks.yaml` (new).

ThreadTrackData dataclass with `progress: ProgressTrack` and own fields: `current_phase: int`, `flashpoint_in_phase: bool`. Reset per phase boundary.

Length from thread_type: vow rank-based (troublesome=10, dangerous=15, formidable/extreme/epic=20), non-vow default 15. In yaml `length_by_rank`.

**31.2** Discovery checks: fate question with 50/50 floor. Maps to Thread Discovery Check Table (d10 + progress points → progress or flashpoint gains). Data: `mythic_gme_2e.json` → `thread_discovery_check`. Depends on 31.1.

**31.3** Add `thread_phase` keyed-scene trigger. Step 4 deliberately did not register `thread_phase` because thread progress tracks did not yet exist — registering it without an evaluator would have been a half-wired trigger. Step 31 adds the trigger to `engine/keyed_scenes.yaml` (`triggers.thread_phase` entry with `value_format: "<thread_id>:<phase>"`) and the matching evaluator in `mechanics/keyed_scenes.py::_EVALUATORS` reading `ThreadTrackData.current_phase`. AC's keyed-scene mapping (step 7c.1) gains the `thread_phase` mapping.

**31.4** Tests.

Done: thread tracks drive stories, discovery checks work.

### 32 — Chaos factor variants

Four modes: Standard, Mid-Chaos, Low-Chaos, No-Chaos. Each has own fate chart AND fate check modifier table. Data: `mythic_gme_2e.json` → `chaos_variants`. Config `fate.chaos_mode` required, no Python default.

### 33 — Themed element tables

Data: `data/mythic_gme_2e.json` → `meaning_tables.elements` (already present). 45 themed d100 Elements Meaning Tables from MGME2e: locations, characters, objects, adventure_tone, plus 41 more covering character traits, creature descriptors, terrain, magic, dungeons, etc. Currently the `roll_meaning_table` helper in `mechanics/random_events.py` only supports the two base tables (actions, descriptions); unknown table names already raise `KeyError` (fixed in 0.55 — strict-rules compliant). This step extends the helper to accept the full elements-set, no silent-fallback work needed.

**33.1** Extend `roll_meaning_table` to accept any elements-table name from `meaning_tables.elements`. Valid names discovered at load time, not hardcoded. Existing `KeyError`-on-unknown semantics preserved — extended to cover the larger valid-names set.

**33.2** 6 high-use themed tables selected for initial rollout. Selection mapping in `engine/themed_tables.yaml` (new) from (event_focus, scene_type, location_type) → chosen elements-table. Doubling rule: same word → greater intensity.

**33.3** Integration with random event pipeline. Event focus routes to themed table when one matches context; falls through to actions/descriptions otherwise. AI-data-aanvoer: rolled themed-table results are injected into the narrator prompt as part of the existing `<random_event>` tag — engine-triggered, no tool-call. The 45-table payload-set is large but only one table is rolled per event, so prompt-injection of the result remains bounded. Per the "When tool-call vs when prompt-inject" Key Design Decision.

**33.4** Tests.

### 34 — Remaining themed tables

**34.1** Remaining 39 Elements Meaning Tables mapped incrementally into `engine/themed_tables.yaml`. No code changes — the step 33 `roll_meaning_table` extension already handles them. Pure config work.

### 35 — Detail check chains

Multi-question fate refinement. Each follow-up shifts odds one step toward previous answer. Max 3, config-driven.

---
