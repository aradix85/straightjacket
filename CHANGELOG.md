# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

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
