# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

---

## [0.64.0] — 2026-04-20

Full sweep of the v0.63.0 audit. Ten batches covering hardcoded narrator/UI strings, silent error suppression, half-wired features, magic truncation numbers, SQL schema drift, inline-import hygiene, orphan config keys, test isolation, and cosmetic noise. A handful of live bugs surfaced while sweeping and were fixed in passing.

Hardcoded strings moved to config. Ten violation-message templates in `ai/rule_validator.py` now live in `engine/rule_validator.yaml` under `violation_templates`; the category prefixes ("PLAYER AGENCY:", "IMPACT CHANGE:", etc.) stay as stable labels so downstream substring matching keeps working. Ten threshold dictionaries in `web/serializers.py` (`_HEALTH_DESC` through `_MENACE_DESC`) moved to a new `engine/status_descriptions.yaml` with a typed `StatusDescriptionsConfig`. Five error strings from `web/handlers.py` and `web/server.py` live in `strings/error.yaml`. Two prompt-structural replacements in the retry-strip path moved to `validator.yaml` under `retry_strip`. The hardcoded `"morning"` fallback in `ai/narrator.py` now reads `narrator_defaults["unknown_time"]` from `ai_text.yaml`. The vow-ranks list in `build_creation_options` is derived from `eng().legacy.ticks_by_rank.keys()` instead of hardcoded.

Silent error suppression cleaned up. `persistence.list_saves_with_info` no longer papers over corrupt save files with placeholder records — it skips them with a warning and a new test exercises the path. Four sites in `user_management.py` replaced bare `except Exception: pass` with narrow filesystem-exception clauses and warning logs. Three `contextlib.suppress` / `except Exception: pass` sites in `web/handlers.py` and `web/server.py` became typed catches on `WebSocketDisconnect / RuntimeError / OSError` with logs that explain why the swallow is acceptable (dead socket, stale client, invariant-transition race).

Pay-the-price consumer wired up. The feature had been half-built for several versions: `OutcomeResult.pay_the_price` was being set, the yaml referenced the effect, tests checked the flag, but no code actually rolled the oracle or passed the result to the narrator. New helper `_roll_pay_the_price` picks a random line from `engine/pay_the_price.yaml`, substitutes `{player}`, and appends it to `result.consequences`. Wired into both write sites (`apply_effects` and `apply_recovery_handler` miss branch). Narrator now sees the chosen consequence as a regular `<consequence>` tag and the rule-validator checks for reflection.

Magic truncation numbers consolidated. Thirty-five `[:N]` slice sites across logs and prompts (`N` in {40, 60, 80, 100, 120, 200, 300, 500, 600, 1000, 2000, 4000}) now read named keys from `engine/truncations.yaml` via a new `TruncationsConfig`: `log_xshort/short/medium/long/xlong`, `prompt_xshort/short/medium/long/xlong/xxlong`, `narration_preview`, `narration_max`. The `log_truncate_*` fields moved out of `architect_limits` where they didn't belong. The dead `retry.max_retries: 2` key (never read in production) was replaced with `constraint_check_max_retries: 1`, which the three sites that previously hardcoded `max_retries=1` overrides (validator, architect-validator, tool-handler) now consume.

SQL schema aligned with the `sync.py` insert contract. Every `DEFAULT` clause on data columns was dropped — `sync.py` is the sole writer and always provides every column, so DEFAULTs were dead code that hid bugs. `scene_type` had an odd inconsistency (no `NOT NULL`, double-quoted literal) that got fixed in the same pass. A genuine bug surfaced: `SceneLogEntry.oracle_answer` was present in the dataclass, serialised to savefiles, but absent from `schema.sql` and `sync.py` — so DB state and savefile state disagreed. Added to both for consistency.

Inline imports swept. From 154 function-level imports across the codebase down to roughly a dozen, each of those now carrying a comment explaining why it can't be top-level: `models.py → db` is a genuine cycle (db queries import models); `npc/lifecycle.py → mechanics` is another (mechanics.consequences imports find_npc); `api_client.py` provider imports stay lazy so unused providers don't need their SDK installed. The rest got promoted. This surfaced and fixed a family of subtle bugs from ruff's auto-fix ripping top-level imports that it considered unused while inlines still existed — every such case is now either top-level-and-used or inline-with-comment.

Orphan strings scan found zero real orphans after accounting for html consumers, `get_strings_by_prefix` usage, and dynamic key construction (`handlers.py:451` builds `"advance.upgraded"` vs `"advance.acquired"` at runtime). The two vermeende orphans were false positives; nothing to delete.

Test isolation hardened. New autouse `_reset_random` fixture in `conftest.py` reseeds `random` after every test — tests that call `random.seed(N)` for deterministic rolls no longer bleed their seed into subsequent tests. Shebang-before-imports in `test_engine.py` fixed.

Cosmetic pass: 83 unused shebangs removed from non-entry-point modules. 255 lines of section-banner comments (`# ─── NAME ───`) removed across the codebase. Trivial one-line docstrings left alone — judgment call; they're noise but some are close enough to borderline useful that a mechanical sweep would lose signal too.

Delivery gate: 786 tests green, ruff + ruff format + mypy clean on 87 source files.

---

## [0.63.0] — 2026-04-19

Two small audit batches (N — validator regex drift, and G — `_raw` direct access). What started as a cosmetic cleanup turned up a live latent bug along the way.

The secret-stripping regex in `ai/validator.py` hardcoded the literal label `"weave subtly,never reveal"`, a string that was supposed to mirror `secrets_label` in `prompts/blocks.yaml`. That yaml value currently reads `"MUST NOT reveal directly,weave across 3+ scenes"` — the two drifted apart at some earlier point and nobody noticed, because the existing tests fabricated their input using the old label, so the test suite kept matching itself. In production the regex never matched the real prompts; every retry on a pacing violation was running with NPC secrets left in the context block. The regex is now structural — `secrets\([^)]*\):\[.*?\]` — so it matches any parenthetical label. Tests for both the pacing-match and the agency-nomatch paths were rewritten to read `secrets_label` from yaml at test time.

The `_raw` audit called out two callsites (`ai/rule_validator.py`, `ai/validator.py`) that bypassed `EngineSettings.get_raw()` and reached into the private `_raw` dict directly. Both now go through `get_raw()`. A third site surfaced while sweeping — `engine_loader.damage()` itself was walking from `eng()._raw` root to support dotted-path lookups like `"damage.miss.clock_ticks"`. Split on the first segment and the rest of the path walks through `get_raw(first)` just fine, so that's now consistent too.

Delivery gate: 783 tests green in 4.3s, ruff + ruff format + mypy clean on 87 source files.

---



Batch E from the v0.61.0 audit. Five domain enums that were hardcoded inside `src/straightjacket/engine/ai/schemas.py` and `src/straightjacket/engine/mechanics/fate.py` now live in `engine/enums.yaml` alongside the existing enum lists. `EnumsConfig` grew five fields: `tone_keys`, `correction_ops`, `correction_fields`, `dramatic_weights`, `odds_levels`. The schema builders read them via `eng().enums.<name>`.

`DIRECTOR_OUTPUT_SCHEMA` and `STORY_ARCHITECT_OUTPUT_SCHEMA` were still import-time module constants — the only two left after the v0.58 schema-builder refactor moved validator/revelation-check/architect-validator to lazy builders. Both are now `get_director_output_schema()` and `get_story_architect_output_schema()`. Their callsites in `architect.py` and `director.py` were updated, and a pre-existing function-level import of the old constant in `director.py` got promoted to the top of the file.

`fate.py`'s module-level `ODDS_LEVELS` tuple is gone; `get_odds_levels()` returns a tuple built from `eng().enums.odds_levels`. Test `test_fate.py` flipped the import, updated call sites to the function, and the two tests that iterate all odds now request the `load_engine` fixture.

One divergence surfaced and got fixed in passing. The correction schema advertised six editable NPC fields (`name`, `description`, `disposition`, `agenda`, `instinct`, `aliases`) while `_apply_correction_ops` in `correction.py` also accepted `status`. The allowed-set was the wider contract; the schema is now aligned to it, so the AI can propose `status` edits directly instead of the code silently accepting a field the schema never exposed.

Delivery gate: 783 tests green in 4.2s, ruff + ruff format + mypy clean on 87 source files.

---



Batch F from the v0.60.0 audit. Dataclass-field defaults that duplicated yaml or hardcoded a domain enum are gone. `Resources` and `WorldState` got `from_config()` classmethods used as `GameState`'s default factories. `ProgressTrack` and `ThreatData` got `.new()` factories that read `max_ticks` from the new `progress.yaml max_ticks` key. `ClockData`, `FateResult`, `MemoryEntry`, `RandomEvent`, and the structural fields on `NpcData` are now required. `NpcData.introduced` flipped from True to False — fresh NPCs haven't been shown on screen. `CampaignState` legacy tracks read display names from `strings/status.yaml` and rank from `legacy.yaml`. `BrainResult.type/move/stat` became kw_only required; the brain-exception fallback and the correction null-brain sentinel supply them explicitly.

`db/schema.sql` dropped `DEFAULT` clauses on now-required fields and flipped `introduced` to 0. Dead `game.resources.health = ...` overrides in `game_start.py` are gone — `from_config()` already reads those keys. Two silent fallbacks found in passing: the `"neutral"` on `disp_to_emotion.get(...)` in `npc/processing.py` and the `"actions"` default on `roll_meaning_table()` both raise now.

Tests: `tests/_helpers.py` grew from one helper to nine, one per dataclass, holding test-only defaults like `"dangerous"` rank and `"neutral"` disposition. 30 test files migrated to the helpers; tests that exercise specific values still pass their own kwargs. Production stays strict, test boilerplate lives in one place.

Delivery gate: 783 tests green in 3.8s, ruff + ruff format + mypy clean on 87 source files.

---

## [0.60.0] — 2026-04-19

Tranche 8 expanded: every yaml store in the repo is now modular. Callsites unchanged — each loader globs its directory, merges top-level keys, raises on duplicates.

`engine.yaml` (2165 lines) split into 58 files under `engine/`, one per subsystem, filename matching the section. Small siblings bundled where splitting would give one-key files: `npc.yaml` bundles npc/name_titles/npc_matching, `memory.yaml` the six memory sections, `architect.yaml` architect/architect_limits, `disposition.yaml` the two disposition maps, `scene_context.yaml` the two one-liners, `creativity_seeds.yaml` adds scene_range_default, `track_moves.yaml` the two track-move lists. Per-subsystem split chosen because tranches cluster that way (tranche 5 = move_availability only, tranche 6 = ai_text+architect, tranche 7 = stats only).

`emotions.yaml` (293 lines) split into `emotions/importance.yaml`, `keyword_boosts.yaml`, `disposition_map.yaml`. `prompts.yaml` (30 prompts) split into seven cluster-files under `prompts/`: brain, narrator, architect, validator, director, tasks, blocks. `strings.yaml` (142 keys) split into eighteen files under `strings/`, one per dotted-key prefix so translators edit one file at a time. `config.yaml` stays single — 62 lines, user-edited, not worth the usability hit.

One config rename: `ai.prompts_file` → `ai.prompts_dir` in `config.yaml` and `AIConfig`. One test-helper config followed. Session-cache behaviour preserved in `tests/conftest.py`.

Delivery gate: 783 tests green in 3.4 seconds, ruff + ruff format + mypy clean on 87 source files.

---

## [0.59.0] — 2026-04-19

Tranche 7: the five hardcoded stat fields on GameState (`edge`, `heart`, `iron`, `shadow`, `wits`) are gone. They duplicated `engine.yaml stats.names` in Python, carried the canonical 3-2-2-1-1 array as magic-number dataclass defaults, and had been flagged as a storage-schema migration since tranche 3. GameState now has a single `stats: dict[str, int]` field declared `kw_only=True` so it can sit among default fields while remaining a required kwarg — no default dict, no silent substitute for a missing character-creation state. `GameState.get_stat` reads from the dict and raises on an unknown or unset key. Save-file format breaks; there were no live saves to migrate.

One architecturally significant pre-existing violation got swept up. The Brain prompt in `ai/brain.py` rendered stats as a hardcoded `E{edge} H{heart} I{iron} Sh{shadow} W{wits}` f-string, duplicating the stat names a second time and hardcoding the English abbreviations. The abbreviations now live in a new `stats.prompt_abbreviations` yaml subsection (which also carries a field in `StatsConfig`), and `ai/brain.py` gained a `build_stats_line(game)` helper that iterates `eng().stats.names` and emits only stats that have an abbreviation. The stat named `none` has no abbreviation and is not rendered. The same helper is called from `tests/model_eval/eval.py` which had two copies of the same hardcoded template; they're gone. `tests/elvira/elvira_bot/runner.py` built a stats dict via attribute access on the five old fields — it now copies `game.stats` directly.

Tests got a `tests/_helpers.py` module with a single `make_game_state(**kwargs)` helper. It defaults to the canonical 3-2-2-1-1 array when a test doesn't pass `stats=` explicitly, so tests that don't care about specific stat values keep their minimal constructors. Tests that do care pass their own dict, which wins via setdefault. Roughly 125 `GameState(...)` call sites across 34 test files were migrated — 36 explicit stat-kwarg sites to the dict form, the rest to `make_game_state`. `GameState.stats` being a required kwarg in production means the helper is the only place the canonical test array is stated; production code (`game/game_start.py`) passes stats explicitly from validated creation data.

Delivery gate: 783 tests green in under 5 seconds, ruff + ruff format + mypy clean on 87 source files.

---



Tranche 6: every hardcoded English string that ends up in an AI prompt, narrator output, or json_schema description now lives in `engine.yaml` under a new `ai_text:` section. Eight `TODO tranche 6` markers across the codebase are gone, plus roughly fifteen unmarked sites discovered along the way.

The new section has six dataclass-bound subsections. `brain_trigger_hints` carries the contrastive move descriptions Brain feeds the classifier. `schema_descriptions` holds the field-level `description=` strings injected into json_schema for the validator, revelation-check, and architect-validator outputs — these became lazy builder functions (`get_validator_schema()`, `get_revelation_check_schema()`, `get_architect_validator_schema()`) replacing the old import-time constants, and three callsites that still imported the old `VALIDATOR_SCHEMA`/`REVELATION_CHECK_SCHEMA`/`ARCHITECT_VALIDATOR_SCHEMA` constants were broken-but-untested before this release; they now call the builders. `consequence_labels` covers all thirteen narrator-facing templates produced by `move_outcome.py` — momentum changes, track gains and losses, mark-progress, clock fills, bond progress, disposition shifts, mark-impact, clear-impact, threshold vow — replacing roughly twenty-five inline f-strings across `apply_effects`, `apply_suffer_handler`, `apply_threshold_handler`, `apply_recovery_handler`, and `_apply_generic_suffer`. `validator_blocks` holds the wrapper text for the validator's correction-mode retry prompt, the `Fix: {violation}` fallback for unmatched violations, and the `<momentum_burn>` injection string used by `momentum_burn.py`. `narrator_defaults` collects the scattered placeholder strings that flow into AI prompts when game state is empty — `unknown_location`, `unknown_time`, `no_npcs`, `no_npcs_yet`, `no_npcs_nearby`, `no_roll`, plus the templated fallbacks `npc_appeared_event`, `unnamed_track`, `reflection_tone_fallback`, `default_act_mood`, `recap_fallback`, `chapter_summary_fallback_title`, and `chapter_summary_fallback_text`. `architect_labels` carries the three label fragments (`Forbidden terms`, `Forbidden concepts`, `Test`) that `architect_validator.py` concatenates into its constraint_text prompt.

Routes to the yaml: roughly eleven scattered `or "unknown"` / `or "(none)"` / `or "none"` defaults across `narrator.py`, `correction.py`, `prompt_builders.py`, `engine_memories.py`, `npc/processing.py`, `turn.py`, `director.py`, `momentum_burn.py`, and `architect.py` now read their fallback string from `eng().ai_text.narrator_defaults`. The two `or "?"` defaults in `web/serializers.py` and `director.py` stayed put — the former is an empty-state UI placeholder for the player status block (not config data), the latter only appears in a debug log line. Three pre-existing pieces of broken English that didn't carry TODO markers were swept up in passing: `correction.py`'s `"dialog (no roll)"` next to the `(none)` it sat alongside, `engine_memories.py`'s `"no one nearby"` next to the `or "unknown"` on the previous line, and `narrator.py`'s second-site `(none)` in the metadata-extractor prompt.

`architect.py` and `architect_validator.py` got the same treatment as the rest of the codebase, with their misleading "slated for deletion" docstrings removed along with the comment claim that magic numbers were "intentionally left hardcoded — fixing them would be wasted work before removal." Both files now use a new `architect_limits:` yaml section (twelve typed integer fields) for every truncation length and history window: recap log/narration/campaign windows, chapter-summary log window, and four log-truncation lengths. Architect_validator's three log-line magic numbers (`[:60]`, `[:5]`, `[:80]`) route through the same section; `drift_words_log_window: 5` was added for the previously inline `found[:5]`.

Two pre-existing inconsistencies surfaced and were fixed. The vorige tranche renamed `memory_move_verbs._default` to `_catchall` in `engine.yaml` but left the callsite in `engine_memories.py:61` reading `verb_map["_default"]` — that branch would have raised KeyError on any move outside the explicit verb map, but no test exercised it. The schema-builder refactor in `schemas.py` replaced module constants with lazy functions and renamed the references from `VALIDATOR_SCHEMA` etc. to `get_validator_schema()` etc., but three lazy `from .schemas import ...` lines inside AI-call functions still pointed at the old names; tests passed because no test path reached those AI calls. Both classes of bug would have surfaced as runtime failures the first time a player triggered the affected paths in production.

---

## [0.57.1] — 2026-04-18

Test suite runs 16x faster — 49 seconds down to 3 seconds — with no test removed.

The `load_engine` and `stub_engine` fixtures in `tests/conftest.py` were function-scoped, which meant every test that used them reparsed the 82KB `engine.yaml` from scratch. Measurement showed that 427 tests each spent ~100ms in setup, totalling 44 of the 49 seconds. The actual test logic across 783 tests ran in under a second.

Fix: session-scope the yaml parse behind two hidden fixtures (`_real_engine`, `_stub_engine_instance`). The per-test `load_engine` and `stub_engine` fixtures now just pointer-swap the cached instance into `engine_loader._eng`. A duplicate `load_engine` fixture in `test_web.py` was updated to use the same session cache.

Safe because no test mutates `eng()` after installing it — they only read from the config snapshot.

---

## [0.57.0] — 2026-04-18

Tranches 4 and 5: yaml-internal naming cleanup, and move availability rules moved from Python into `engine.yaml`.

Tranche 4 reviewed six `_default` entries in `engine.yaml`. `time_progression_map._default` is a real resolver fallback and was renamed to `_catchall` (with the callsite in `resolvers.py` updated) so the naming matches the semantics. `narrative_direction.result_map._default` turned out to be dead — no callsite ever read it, the resolver raises on unknown keys — and was removed outright rather than renamed as the handover suggested. `move_verbs._default` is narrator-facing text and stays for tranche 6. The remaining three were already correctly named.

Tranche 5 moved the 77-line `_is_move_available` rule table in `tools/builtins.py` into a new `move_availability:` section in `engine.yaml`. Every rollable move across Classic, Delve, Starforged, and Sundered Isles is listed explicitly; unlisted keys raise. Each entry is either `{never: true}` (reactive moves that are never player-initiated) or `{available: [<conditions>]}` where conditions combine named boolean flags and combat-position checks. Three new condition dataclasses (`FlagCondition`, `NotFlagCondition`, `CombatPosCondition`) plus `MoveAvailabilityRule` in `engine_config.py`; the Python function is now a thin yaml-driven evaluator. Before extraction, the Python was cleaned up: a dead duplicated branch in `scene_challenge`, several redundant `return True` statements, and a stale delve comment referencing unimplemented site-state were removed.

---

## [0.55.0] — 2026-04-18

Tranche 3: data tables that lived only in Python moved to `engine.yaml`. Silent fallbacks found alongside now raise.

Progress-track ticks-per-mark, fate odds/chaos modifier tables, random-event focus-category sets, consequence/general/location stopwords, and NPC honorifics are all yaml-driven. Engine-specific moves (`dialog`, `ask_the_oracle`, `world_shaping`) consolidated into a single `engine_moves:` section read by `builtins.available_moves` and the brain schema. Reads that used to silently fall back — unknown fate odds, unknown chaos factors, unmatched score-to-odds, out-of-range event-focus rolls, invalid progress ranks — now raise.

Cleanup along the way: `_STAT_NAMES` frozenset, `CORRECTION_OUTPUT_SCHEMA` constant, and several hardcoded enums in the brain schema replaced by lookups against their yaml sources. A tranche-2.1 residue in `ai/schemas.py` (a hardcoded 4-settings tuple with `try/except pass`) now uses `list_packages()`.

Two tests flipped from expecting silent fallback to expecting raises.

---

## [0.54.0] — 2026-04-18

Tranche 2 of the config-strict refactor: settings discovery and inheritance.

Setting discovery is yaml-driven — no more Python mapping tables. `list_available()` scans `data/settings/*.yaml`; `get_moves()` reads `parent:` from the child. Settings yaml is strict-parsed with required top-level keys; `parent` and `creation_flow` are optional. Oracle paths, genre constraints, and creation flow now use per-field inheritance through the parent chain.

Delve yaml collapsed to pure inheritance from Classic. `active_package` no longer swallows errors on invalid setting ids. Oracle-path cascades deleted; `SettingPackage.oracle_data_for(path)` walks the chain. Multilingual residue in `parser.py`, `chapters.py`, and `web/serializers.py` removed along with two obsolete tests.

`ARCHITECTURE.md` "Settings YAML format" section rewritten.

---

## [0.53.0] — 2026-04-18

Tranche 1 of the config-strict refactor. Every domain-config access now raises on missing data; every tuning number that determines engine behaviour moved to yaml.

Strict dataclasses in `engine_config.py` and `config_loader.py` — no hidden Python defaults, no `get_raw(key, default)`. Nineteen new `engine.yaml` sections consolidating magic numbers from across the engine (TF-IDF, fuzzy-match, monologue-detection, rate-limit, retry, memory, description-dedup, rule-validator, parser, chapter, and more). Fifteen `get_raw` call sites and dozens of individual `.get(k, default)` fallbacks replaced with strict lookups. `engine_loader.damage()` rewritten to raise on missing paths, positions, or non-numeric leaves.

AI-call exception suppression is now a documented carve-out: twelve sites across `brain.py`, `narrator.py`, `validator.py`, etc. each log at warning level and carry a one-line comment pointing to the policy in `provider_base.py`'s module docstring.

Ruff config adds `SIM401` to ignore — it conflicts with the no-fallback rule on `dict.get`.

---

## [0.52.2] — 2026-04-17

Config-driven cleanup, second pass.

Two architect-validator prompts moved from Python f-strings to `prompts.yaml`. The `{dash}` placeholder retired project-wide — em-dashes are now literal `—` in all 33 prompt locations. Format-leak patterns and curly-quote regexes moved from module-level constants in `ai/rule_validator.py` to `engine.yaml`.

New EngineSettings helpers `compiled_patterns`, `compiled_labeled_patterns`, and `compiled_pattern` cache regex lists on the settings instance.

---

## [0.52.1] — 2026-04-17

Config-driven cleanup: AI-facing text removed from Python.

Seven prompts (validator system, director task, revelation check, and related blocks) relocated from f-strings in `ai/validator.py`, `director.py`, and `ai/brain.py` to `prompts.yaml`. A new `validator:` section in `engine.yaml` carries twelve rewrite-instruction templates (replacing an eleven-branch if/elif), twenty-seven consequence stem mappings, and regex pattern lists for agency violations, miss silver linings, and annihilation markers.

`run.py` startup fixed (stale re-export import). Stale `pacing={...}` log line in `director.py` removed.

---

## [0.52.0] — 2026-04-17

Legacy tracks and XP — campaign progression mechanics.

Three campaign-persistent `ProgressTrack`s on `CampaignState` (`legacy_quests`, `legacy_bonds`, `legacy_discoveries`), all epic rank. `mark_legacy` consumes `outcome.legacy_track` (which was previously set but never acted upon). Filled boxes grant XP; XP spent on asset upgrades via `advance_asset`. Bonus XP when a vow completes with its linked threat at high menace.

Architectural fix: new `apply_progress_and_legacy` helper in `game/finalization.py` consumed by turn, correction (input_misread re-roll), and momentum burn. Without it, correction and momentum burn silently dropped progress marks and legacy rewards from re-resolved outcomes. `/status` reports XP and legacy progress narratively (no numbers).

---



## [0.51.0] — 2026-04-16

Codebase audit and modularization. No new features.

Five splits: `game/tracks.py`, `game/momentum_burn.py`, `ai/architect_validator.py`, `ai/json_utils.py`, and `check_story_completion` moved to `story_state.py`. Main turn file dropped from 739 to 599 lines; correction, validator, and brain all shrank comparably.

`apply_opening_setup()` in `setup_common.py` unifies the wiring previously duplicated between `game_start.py` and `chapters.py`. `generate_epilogue` now uses the main parser pipeline instead of four custom regexes. Dead code removed: the `ai/__init__.py` re-export hub (59 lines, zero consumers), nine stub functions in `conftest.py`, Delve's 32-entry atmospheric_drift copy-paste (now inherits from Classic).

---

## [0.50.0] — 2026-04-16

Threats and menace, impacts, NPC name generation via oracles. Plus a typed-config refactor across engine.yaml and settings yamls.

Threats carry rank-based menace tracks linked to vows. Menace advances on MISS and autonomously per scene; full menace forces Forsake Your Vow. Ten impacts defined in `engine.yaml` — each reduces max momentum, some block specific recovery moves. Suffer and threshold handlers mark impacts; recovery handlers clear them. NPC name generation routes through the active setting's `oracle_paths.names` with parent-chain fallback (Delve inherits from Classic).

Typed-config refactor: five new config dataclasses (`ImpactConfig`, `PositionResolverConfig`, `EffectResolverConfig`, `InformationGateConfig`, `NarrativeDirectionConfig`); settings yamls get `SettingConfig`, `VocabularyConfig`, `OraclePaths`, `CreationFlow`. `SettingPackage.raw_config` removed. New `ValidationContext` dataclass replaces threading six loose params through the validator chain. `progress_tracks` added to GameState snapshot/restore.

---

## [0.49.0] — 2026-04-14

Model optimization: GLM-4.7 removed, two-model architecture. Qwen 3 for the narrator, GPT-OSS for everything else. Cost per session down ~53% ($0.117 → $0.055); cost per turn ~$0.012.

The narrator prompt was rewritten for Qwen 3 — MUST/STRICTLY language replaced with concrete WRONG/RIGHT examples, Qwen-specific agency and genre-physics failure modes added. NPC "speech budget" length limits retired in favour of a content-scope rule (answer the question, say nothing beyond it). The rule validator gained four Qwen-specific agency patterns and now strips quoted NPC speech before matching to eliminate a false positive.

Three arbitrary length limits (`monologue_max_chars`, `description_max_chars`, `arc_max_chars`) deleted. Atmospheric-drift wordlists cleaned of terms that have legitimate literal uses in their settings.

Measured over nine Elvira batch sessions: genre-physics violations −71%, player-agency violations −75%, consequence compliance +60%, result integrity +44%. Resolution pacing stable and still dominant.

---

## [0.48.1] — 2026-04-13

Codebase audit. Module ownership cleanup.

`logging_util.py` split: logging stays, user/save directory management and config load/save moved to new `user_management.py`. The `engine/__init__.py` re-export hub eliminated (88 → 8 lines); consumers import directly from submodules. Four underscore-prefixed public functions renamed to drop the underscore. `validator.py`'s `sampling_params()` return dict was being mutated in-place at three sites — now copied before mutation.

---

## [0.48.0] — 2026-04-13

Cluster-based AI model assignment.

Four model clusters (narrator, creative, classification, analytical), each with its own `ClusterConfig` (model, temperature, top_p, max_tokens, max_retries, extra_body — every field required). `model_for_role(role)` and `sampling_params(role)` resolve everything from cluster — no per-role overrides, no fallback chains, no hidden defaults. All fifteen `create_with_retry` call sites refactored to resolve parameters via these two helpers; direct config-field access removed from the AI modules.

New per-role evaluation script in `tests/model_eval/` — tests brain, validator, and extraction in isolation against fixed inputs. Uses the same provider/config infrastructure as the engine.

Bug fixes: duplicate `top_k`/`extra_body` assignment in `provider_openai.py`; `tick_chaos` floor 3 → 1 per Mythic 2e; hardcoded `% 5` in `consequences.py` replaced by `eng().pacing.npc_agency_interval`; stale accumulator leakage on failed turns fixed by draining `_pending_events` and `_token_log` at turn start.

## [0.47.0] — 2026-04-13

Combat, expedition, and scene-challenge track lifecycle. Multi-model support. Validator tuning.

`available_moves` now filters progress tracks by `status == "active"`. `complete_track` clears combat_position on combat track completion or failure; `sync_combat_tracks` removes orphaned active combat tracks when combat_position is cleared by narrative. Adventure moves mark progress on an active scene-challenge track on hit. `/tracks` command added.

Multi-model: `extra_body` configurable per-role via `PerRoleDict`, `validator_model` now actually used (was silently falling back to brain_model), `fast_model` field added for lightweight extraction roles. `run_tool_loop` accepts `extra_body`.

Validator RESOLUTION PACING rewritten: information discipline rather than sentence counting, with an explicit anti-instruction against counting (GLM hallucinated the old rule). RESULT INTEGRITY skips STRONG_HIT and dialog. Empty-response fallback retries without json_schema.

Bug fixes: `enter_the_fray` without track_name auto-generates from player intent instead of crashing; `SceneLogEntry.oracle_answer` added; `characters_list` INSERT OR REPLACE prevents crash on duplicate NPC ids.

## [0.46.50] — 2026-04-12

Config-driven prompt file. Shared resolution and narration. Typed config.

Prompt file path configurable via `config.yaml → ai.prompts_file`. New `resolve_action_consequences` and `narrate_scene` helpers in `game/finalization.py` unify four duplicated narrator → parse → validate sequences across turn, correction, and momentum burn. `SceneContext` dataclass reduces `_finalize_scene`'s signature from 18 parameters to 8. `_ConfigNode` replaced by a typed `AppConfig` dataclass tree with full mypy coverage. Status commands (`/status`, `/score`) now fully narrative — no numbers, no momentum, no chaos factor.

Brain back to single-call prompt injection. All game state (available moves, NPCs, active tracks) injected as XML context blocks; no tool loop. ~13× Brain token reduction (67K → ~5K over 10 turns).

## [0.46.0] — 2026-04-12

Track lifecycle. Connection tracks replace bond.

Progress tracks now have creation, progress marking, and completion/failure. `track_creating_moves` in `engine.yaml` maps moves to track types. Engine creates a `ProgressTrack` from Brain output (track_name + track_rank both required). Vow tracks auto-create linked `ThreadEntry`. `ProgressTrack.status` (active/completed/failed); `_find_progress_track` filters by status and disambiguates multi-matches via `target_track`.

`NpcData.bond` and `bond_max` deleted. All bond reads go through `get_npc_bond(game, npc_id)`, which reads `filled_boxes` on the NPC's connection track. The `bond` effect in move outcomes marks connection-track progress instead of mutating NpcData. Callers across stance, resolvers, prompt builders, director, architect, chapters, lifecycle, activation, tools, correction, metadata, processing, and serializers all migrated.

`/status` and `/score` commands — engine answers directly via `strings.yaml` templates, no AI call. `build_state` removed (80 lines); the per-turn state blob is gone. `turn_complete` WebSocket message replaces `state` as end-of-turn signal.

## [0.45.0] — 2026-04-11

Full Forge move system. Data-driven consequence resolution. Combat position.

New `Move` dataclass and setting-level loader in `datasworn/moves.py`, with expansion merge (Delve → Classic, Sundered Isles → Starforged). New `mechanics/move_outcome.py` with fifteen effect types (momentum, health, spirit, supply, integrity, mark_progress, pay_the_price, next_move_bonus, suffer_move, position, legacy_reward, fill_clock, bond, disposition_shift, narrative) plus three handlers for suffer, threshold, and recovery moves. All 112 moves across four settings have structured outcomes in `engine.yaml`.

`apply_consequences` and its category-based routing deleted — `resolve_move_outcome` now handles everything. Progress rolls are first-class: `roll_progress()` uses `filled_boxes` vs 2d10 instead of action dice. `combat_position` on `WorldState` (in_control, bad_spot) set by move outcomes. `available_moves` tool filters by game state — combat position restricts combat moves, track existence gates progress moves, suffer/threshold moves are excluded as reactive-only.

Brain move enum now covers all Datasworn moves across all settings; Brain prompt directs to call `available_moves` instead of a hardcoded list.

## [0.44.0] — 2026-04-11

Mythic GME 2e integration: fate system, scene structure, random events.

Fate system: fate-chart resolver (9×9 odds/chaos matrix), fate-check resolver (2d10 + modifiers), random-event trigger on doublets, likelihood resolver (NPC disposition + chaos + resources → odds), `fate_question` Brain tool.

Scene structure replaces chaos interrupts: `check_scene()` rolls d10 vs chaos factor → expected/altered/interrupt. Scene Adjustment Table drives altered scenes. Scene-end bookkeeping runs for every scene type including dialog (stance evaluation, list maintenance, consolidation at 25 entries). Chaos factor range changed from 3–9 to 1–9 per Mythic 2e.

Random events pipeline: event focus (12 categories) → target selection → meaning table (actions/descriptions) → structured `RandomEvent`. Weighted list selection, pending event buffer with drain, `<random_event>` tag in narrator prompt.

Director reduced: pacing removed from Director output and schema — now fully engine-computed from scene structure + narrative direction. NPC reflections and AIMS retained. Legacy `mechanics.py` monolith deleted (1011 lines of dead code).

## [0.43.0] — 2026-04-11

Config-driven refactor. Mechanics modularized.

Twenty-eight magic numbers moved from Python to `engine.yaml` — NPC reflection thresholds, death corroboration, seed importance floor, gate memory counts, retrieval weights, monologue/description/arc limits, opening clock defaults, move routing, architect forbidden moods. New yaml sections: `enums`, `memory_retrieval_weights`, `opening`, `move_routing`, `architect`.

Narrator-metadata and opening-setup schemas converted to lazy cached functions with config-driven enum values. Legacy `mechanics.py` monolith (1030 lines) split into a `mechanics/` package with `world.py`, `resolvers.py`, `consequences.py`, `stance_gate.py`, `engine_memories.py`. New `game/finalization.py` provides shared `apply_engine_memories` and `apply_post_narration` used by turn, correction, and momentum burn.

Bug fix: correction and momentum burn now run memory consolidation and set `needs_reflection` flags (previously skipped).

## [0.42.0] — 2026-04-10

GLM-4.7 prompt tuning. Config-driven prompts.

Narrator system prompt restructured for GLM-4.7's begin-bias: hardest constraints (GENRE PHYSICS, PLAYER AGENCY, CONSEQUENCE COMPLIANCE) at the top in MUST/STRICTLY language. New GENRE PHYSICS constraint: materials must not exhibit consciousness, memory, or transformation. All task templates, instruction fragments, and secrets labels moved from Python to `prompts.yaml`; `prompt_builders.py` is now pure XML assembly.

Atmospheric-drift wordlists expanded for GLM patterns across all four settings (weep, ooze, writhe, visage, reshape, phantom). Three new player-agency regex patterns for GLM-specific violations. New GENRE PHYSICS check in the LLM validator. Architect: rule-based mood sanitizer strips forbidden moods (surreal, haunted, dreamlike) from blueprint acts. Narrator temperature 0.8 → 1.0 per Z.ai recommendation.

Elvira results after tuning: retries 19 → 5, failures 2 → 0, first-pass rate 11% → 44%, zero genre drift, zero spatial issues.

## [0.41.0] — 2026-04-10

Brain and Director tool calling. Ask the Oracle.

Brain and Director both moved to two-phase calls: optional tool loop followed by json_schema. Director can query NPCs, threads, and clocks through tools. `ask_the_oracle` move: engine rolls an action/theme meaning pair from Datasworn tables, result injected as `<oracle_answer>` tag in the narrator prompt.

Bug fix: the Director's fallback accumulator reset was zeroing NPC importance every time it ran without producing a reflection, preventing NPCs from reaching the reflection threshold. Now only resets on successful reflection or API failure.

## [0.40.0] — 2026-04-10

Step 1: oracle roller. Vocabulary control. Cleanup.

- `OracleResult` dataclass; `OracleTable.roll()` preserves actual die value
- `roll_oracle` Brain tool: setting-aware Datasworn oracle roll
- Vocabulary control per setting: substitutions, sensory palettes, config-driven atmospheric drift detection in rule validator. All four settings configured
- Visual bar characters removed from clock display (accessibility)

## [0.39.0] — 2026-04-10

Steps 4–6: consequence sentences, NPC stance, information gating. Code audit.

- Consequence sentence templates in engine.yaml; `generate_consequence_sentences()` produces narrative sentences per mechanical change
- `<consequence>` tags in narrator prompt (required for action turns); validator checks keyword presence
- NPC stance matrix in engine.yaml: 60 entries mapping (disposition, bond, move_category) → stance + behavioral constraint
- `resolve_npc_stance()` replaces raw disposition/bond in narrator prompt with concrete instructions
- Information gate (0–4) per NPC per scene; `compute_npc_gate()` from scenes known, gather successes, bond, stance cap
- Prompt builder filters NPC data by gate level: gate 0 = name only, gate 4 = full secrets
- `gather_count` field on NpcData, incremented on successful gather_information
- `pay_the_price` table in engine.yaml for generic MISS consequences
- Code audit: operator precedence bug fixed in position resolver, floor_at_risky logic bug fixed, mypy 0 errors across 100 files, serialization unified (RollResult/BrainResult/TurnSnapshot on SerializableMixin), sampling_params filters None values, `_safe_name` hardened, CHANGELOG trimmed
- Stale `tests/playerbot elvira` directory removed; requirements.txt cleaned

## [0.38.0] — 2026-04-10

Steps 3.5 + 3.6: database layer and tool calling infrastructure.

- SQLite read model (`engine/db/`): 8 tables mirroring GameState, full sync after every state change, query functions for NPCs/memories/threads/clocks
- Tool registry (`tools/registry.py`): `@register("brain", "director")` decorator, type hints → OpenAI schemas
- Tool handler (`tools/handler.py`): dispatch + iterative tool-call loop
- Built-in query tools: `query_npc`, `query_active_threads`, `query_active_clocks`, `query_npc_list`
- Tool calling probe (`tests/tool_calling_probe.py`): 15 test cases, Qwen 87% / GLM 93% pass rate

## [0.37.0] — 2026-04-09

Steps 2 + 3: Brain slimming, metadata extractor split, code audit.

- Position/effect/time resolvers: engine-computed from game state via engine.yaml weights
- BrainResult stripped from 13 to 9 fields; Brain schema and prompts updated
- Engine-generated memories and scene context from templates in engine.yaml
- Metadata AI schema reduced from 10 to 5 fields (NPC detection only)
- SerializableMixin eliminates to_dict/from_dict boilerplate across 20 dataclasses
- Test stubs migrated to conftest fixtures
- Legacy NiceGUI code removed, XSS fixes in HTML client, i18n for status display
- Dead code: `_resolve_slug_refs`, `apply_memory_updates`, game_data JSON parsing

## [0.36.0] — 2026-04-08

Character creation overhaul. AI surface reduction.

- ProgressTrack, ThreadEntry, CharacterListEntry dataclasses; Mythic lists seeded at creation
- GameState extended with assets, vow_tracks, truths
- Stat validation and creation enforcement against engine.yaml constraints
- Truths in narrator prompt as `<world_truths>` block; truth-to-thread derivation
- Chaos factor derived from background vow keywords
- Director pacing and act transitions moved to engine (deterministic)
- Opening clock and time_of_day set by engine before AI calls
- Memory emotional_weight derived from (move_category, result, disposition) via engine.yaml
- Full creation UI: truths, name tables, backstory roll, vow rank, starting assets

## [0.35.0] — 2026-04-08

Strict typing. Elvira batch runner. Validator tuning.

- `disallow_untyped_defs = true` in mypy — 73 files, zero errors
- Dead code and legacy NiceGUI remnants removed
- Snapshot/restore blueprint asymmetry fixed
- Elvira: batch runner, `--setting`/`--style` CLI overrides, token logging
- Validator false positive reduction (73% → 86.5% compliance)

## [0.34.0] — 2026-04-08

Code audit. Minimal UI.

- Server binds localhost by default; WebSocket origin check added
- Dice roll display removed from client (design doc: player sees only narration)
- HTML client fully i18n'd via strings.yaml
- 266 dead NiceGUI-era strings removed
- emotions.yaml gaps filled (36 terms)
- chapters.py refactored into 6 focused functions
- config.yaml top_p simplified to single default with per-role overrides

## [0.33.0] — 2026-04-07

Prompt rewrite for Qwen3. Hybrid validator.

- prompts.yaml rewritten: data-driven hierarchy, positive instructions, concrete examples
- Hybrid validator: rule-based regex + LLM semantic checks, merged results
- Retry overhauled: 3 retries, correction in system prompt + user message, best-of selection
- Prompt stripping on retry: NPC secrets/memories removed for pacing violations
- Narration history skipped on retry to prevent poisoned few-shot
- models.py split into 4 files (models_base, models_npc, models_story, models)
- Elvira fail rate 84% → 27%

## [0.32.0] — 2026-04-06

NiceGUI replaced with Starlette + WebSocket.

- Starlette + uvicorn server with 19 async WebSocket handlers
- Single-page HTML client: screen reader accessible, scene headings, aria-live
- Elvira WebSocket mode (`--ws`): full stack testing via `debug_state` endpoint
- Chapter archives and dead persistence code removed

## [0.31.0] — 2026-04-06

Project independence. Renamed to Straightjacket.

- ARCHITECTURE.md: turn pipeline, module ownership, file map, extension guides
- ORIGINS.md: project history, EdgeTales credits
- VERSION reads from pyproject.toml; bootstrap_log for early-loading modules

## [0.30.0] — 2026-04-06

NPC arc system. Config-driven moves.

- `NpcData.arc`: narrative trajectory, set by Director, evolves each reflection
- Instinct locked after first fill; arc evolves per reflection
- Phase-trigger deduplication in Director scheduling
- `process_npc_details` memory guard: rejects spurious identity reveals
- 31 window-dressing tests removed

## [0.29.1] — 2026-04-05

Serialization tightening.

- `from_dict()` tightened: direct key access, no fallback defaults
- Hardcoded fallback blueprints removed from architect
- chapters.py and prompt_builders.py split out from monolithic modules

## [0.29.0] — 2026-04-05

Config-driven game logic. Defensive code removal.

- Bugfixes: Elvira CurrentAct/ChapterSummary dict access, fuzzy match `continue` bug, missing fields
- Move categories, disposition shifts, NPC seed emotions moved to engine.yaml
- `Resources.adjust_momentum`/`reset_momentum` require explicit config values
- Defensive `.get()` guards removed from `from_dict` methods
- Elvira added to mypy coverage

## [0.28.0] — 2026-04-05

ChapterSummary + CurrentAct dataclasses. Bugfix: gameplay.py sub-object nesting.

## [0.27.0] — 2026-04-05

MemoryEntry dataclass (10 fields). Dead `prompts.py` removed.

## [0.26.0] — 2026-04-04

Typed models: NpcData, ClockData, SceneLogEntry, NarrationEntry. Module split. Config-driven schemas.

## [0.25.0] — 2026-04-03

NPC hardening. Off-screen death detection. Elvira test bot.

## [0.24.0] — 2026-04-01

XML injection escaping. NPC rename via correction.

## [0.23.0] — 2026-04-01

Datasworn integration. Setting packages with vocabulary control and genre constraints.

## [0.22.0] — 2026-03-31

Constraint validator with `validate_and_retry()` and architect genre check.

## [0.21.0] — 2026-03-30

GameState decomposition into typed sub-objects. Save format break.

## [0.20.0] — 2026-03-30

Constraint validator. Open model prompt hardening. emotions.yaml (131 entries).

## [0.19.0] — 2026-03-29

engine.yaml: all damage tables, resource caps, NPC limits, chaos, pacing, narrative direction.

## [0.18.0] — 2026-03-28

strings.yaml: UI text extraction (372 keys). German removed from code.

## [0.17.0] — 2026-03-28

Upstream UI sync. turn.py `_finalize_scene` eliminates dialog/action duplication.

## [0.16.0] — 2026-03-28

Upstream sync v0.9.66. Revelation verification. Fired clock tracking.

## [0.15.0] — 2026-03-23

AI call audit. Metadata extractor receives mechanical ground truth.

## [0.14.0] — 2026-03-22

KISS cleanup (13.4K → 11.2K lines). Voice I/O removed.

## [0.13.0] — 2026-03-22

Upstream sync v0.9.61. GLM 4.7 as default.

## [0.12.0] — Provider tuning, multi-model testing.

## [0.11.0] — YAML configuration, multi-instance support.

## [0.10.0] — Modular refactor from upstream v0.9.44. Monolithic engine.py → packages.
