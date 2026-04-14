# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

---

## [0.49.0] — 2026-04-14

Model optimization: GLM-4.7 removed, two-model architecture (Qwen 3 narrator, GPT-OSS everything else). Narrator prompt rewritten for Qwen 3. Validator tuned for Qwen patterns. Arbitrary length limits removed.

Model changes:
- GLM-4.7 removed from all clusters. Creative cluster (architect, director) now uses GPT-OSS. Cost reduction ~54% per session, no quality loss on non-narrator roles
- Narrator: Qwen 3 235B, top_p lowered from 0.95 to 0.8 (Qwen recommended for non-thinking mode)
- All non-narrator roles: GPT-OSS 120B (~3000 t/s, $0.35/$0.75 per M tokens)

Narrator prompt (prompts.yaml):
- Header updated: GLM-specific advice replaced with Qwen 3 guidance (examples over directives, constraints at top)
- narrator_system rewritten: MUST/STRICTLY language replaced with concrete WRONG/RIGHT examples targeting Qwen patterns
- Genre physics: added Qwen-specific WRONG examples (sighs, exhales, pulses, awakens, breathes)
- Player agency: added Qwen-specific WRONG examples (sticks in your mind, you've found the break, you can tell)
- NPC speech: renamed from "SPEECH BUDGET" to "SPEECH CONTENT". Sentence/length limits removed. Constraint is now purely content-based: NPCs answer what was asked, say nothing beyond the question's scope. Length is explicitly allowed for complex answers
- task_dialog: "max two sentences" replaced with content scope rule

Validator (rule_validator.py):
- NPC monologue check: character count check removed (was 200-char limit). Only structural dominance check remains (4+ quoted segments with minimal breaks)
- Player agency: 4 new Qwen-specific regex patterns (you've found the break, sticks in your mind, you can tell, you notice yourself thinking)
- Player agency: quoted NPC speech now stripped before regex matching (fixes false positive on NPC saying "You think X?")
- GLM-specific comments removed from pattern list

Engine config:
- `monologue_max_chars` removed from engine.yaml and engine_config.py (unused after validator change)
- `description_max_chars` removed from engine.yaml, engine_config.py, and director.py (arbitrary limit, never hit in practice)
- `arc_max_chars` removed from engine.yaml, engine_config.py, and director.py (arbitrary limit, never hit in practice)
- Director: arc and description length rejection removed. `is_complete_description` check retained (catches truncated output)

Atmospheric drift (setting YAML files):
- All settings: Qwen material agency words added (sighs, exhales, awakens, shimmers)
- starforged: hums, pulses, exhales, thrums removed (legitimate sci-fi machine vocabulary). seeps removed (coolant seeps is physical)
- classic: glow/glows/glowing removed (light glows physically), seep/seeps/seeping removed (water seeps physically), whisper/whispers/whispering removed (people whisper)
- sundered_isles: seeps/seeping removed (water on ships is physical). hums, pulses, thrums removed (ship machinery)

Elvira batch runner (tests/elvira/elvira_batch.py):
- Default styles changed from all 5 to explorer, aggressor, dialogist (most diagnostic coverage)
- Text report output removed, JSON only. Default output: batch_report.json

Baseline comparison (9 sessions, Elvira batch):
- Cost per session: $0.117 → $0.055 (−53%)
- Cost per turn (real player, no bot): ~$0.012
- Genre physics violations: 24 → 7 (−71%)
- Player agency violations: 12 → 3 (−75%)
- Consequence compliance: 10 → 4 (−60%)
- Result integrity: 9 → 5 (−44%)
- Resolution pacing: stable (dominant remaining violation category, ~60% retry fix rate)

---

## [0.48.1] — 2026-04-13

Codebase audit. Module ownership cleanup. Documentation corrections.

Module split:
- `logging_util.py` split: logging functions stay (log, setup_file_logging, get_logger). User/save directory management, config load/save moved to new `user_management.py` (_safe_name, get_save_dir, create_user, delete_user, list_users, load_user_config, save_user_config, load_global_config, save_global_config)
- `engine/__init__.py` re-export hub eliminated (88→8 lines). All consumers (web/handlers.py, web/server.py, elvira runner) import directly from submodules. No module imports via the hub

Import normalization:
- All AI module imports use direct submodule paths (`from .ai.brain import call_brain`), not the ai/ re-export hub. correction.py and game_start.py were the last holdouts
- Underscore-prefixed public functions renamed: `_move_category` → `move_category`, `_time_phases` → `time_phases`, `_pick_template` → `pick_template`, `_resolve_consequence_sentence` → `resolve_consequence_sentence`. All call sites and tests updated

Bug fixes:
- `validator.py`: `sampling_params()` return dict was mutated in-place (3 sites). Now copied with `dict()` before mutation
- `brain.py`: `call_revelation_check` logged tokens as `"brain_correction"`, now correctly `"revelation_check"`

Documentation:
- ARCHITECTURE.md: file map updated for user_management.py, logging_util.py description corrected. Module ownership table: PerRoleDict reference removed, user management entry added. Known Limitations: generator system, NPC-player emotional dynamics, asset mechanics described without roadmap references
- ORIGINS.md: Mythic GME credit expanded, Ironsworn license corrected (CC BY-NC-SA 4.0), AIMS/Gnome Stew credit added
- README.md: license section corrected

692 tests, ruff clean, mypy clean (128 files: 79 source, 49 tests)

## [0.48.0] — 2026-04-13

Cluster-based AI model assignment. Full codebase review. Bug fixes.

Cluster refactor:
- Four model clusters: narrator (prose, high temperature), creative (architect, director), classification (brain, correction), analytical (validator, validator_architect, narrator_metadata, opening_setup, revelation_check, chapter_summary, recap)
- `ClusterConfig` dataclass: model, temperature, top_p, max_tokens, max_retries, extra_body. Every field required — parser validates and errors on missing fields. Clusters are the single source of truth — no per-role overrides
- `model_for_role(role)` resolves model from cluster. `sampling_params(role)` resolves all call parameters from cluster. No hidden defaults, no fallbacks, no override layers
- `max_tool_rounds` moved to engine.yaml `pacing` section (mechanical limit, not model parameter)
- Removed: `PerRoleInt` (12 hardcoded fields), `PerRoleIntDict`, `PerRoleFloat`, `PerRoleDict`, `ToolRounds`, all builder functions, `brain_model`/`narrator_model`/`director_model`/`validator_model`/`fast_model` fields, all `or` fallback chains, all legacy migration code, all per-role override dicts
- All 15 `create_with_retry` call sites refactored: model and all parameters resolved from config, no direct config field access in AI modules
- `cfg()` and `_c = cfg()` removed from brain.py, narrator.py, architect.py, correction.py, validator.py — these modules now import only `model_for_role` and `sampling_params`

Model eval (`tests/model_eval/`):
- Per-role evaluation script: tests brain (10 cases), validator (5 cases), extraction (4 cases) in isolation with fixed inputs and expected outputs
- Uses same provider/config infrastructure as engine — `model_for_role`, `sampling_params`, `create_with_retry`
- `--role` for single-role, `--model` for model override, `--verbose` for full output
- mypy checked (80 source files)

Bug fixes:
- `provider_openai.py`: duplicate `top_k`/`extra_body` assignment removed (copy-paste bug)
- `models_base.py`: `tick_chaos` default floor 3→1 (Mythic 2e)
- `correction.py`: `consequences` initialized at top of `process_correction`
- `consequences.py`: hardcoded `% 5` replaced by config-driven `eng().pacing.npc_agency_interval`
- `architect.py`: three inconsistent `log_role` values corrected (recap, architect, chapter_summary)
- `schemas.py`: duplicate section comments removed
- `index.html`: `turn_complete` and `debug_state` added as explicit no-op cases in WebSocket switch
- `turn.py`: drain `_pending_events` and `_token_log` at turn start (stale accumulator leakage on failed turns)
- `conftest.py`: chaos.min 3→1, npc_agency_interval added to stub

Documentation:
- ARCHITECTURE.md: Known Limitations section, cluster-based AI Model Assignment section
- SECURITY.md: prompt injection via player input section

692 tests, ruff clean, mypy clean (80 source files)

## [0.47.0] — 2026-04-13

Combat, expedition, and scene challenge track lifecycle (step 10). Multi-model support. Validator and Elvira overhaul.

Step 10 — Track lifecycle:
- Bug fix: `available_moves` now filters progress tracks by `status == "active"`. Completed/failed tracks no longer expose their moves
- `complete_track` clears `combat_position` when combat track completes or fails
- `sync_combat_tracks` removes orphaned active combat tracks when `combat_position` is cleared by narrative. Called in `_finalize_scene` after post-narration
- Scene challenge progress routing: `scene_challenge_progress_moves` list in engine.yaml. Adventure moves mark progress on active scene_challenge track on hit
- `/tracks` status command: handler, serializer with type-specific context, client routing, strings.yaml templates

Multi-model support:
- `extra_body` per-role via `PerRoleDict`, consistent with temperature/top_p. Flat dict becomes default; per-role overrides replace entirely. Resolved in `sampling_params()`, passed per-call — no state in provider
- `fast_model` field: used by metadata extractor, opening_setup, revelation_check, recap, chapter_summary. Falls back to `brain_model` if empty
- `validator_model` now actually used by validator (was hardcoded to `brain_model`)
- `run_tool_loop` accepts `extra_body` parameter — fixes director crash when extra_body is per-role
- Recommended config: GLM-4.7 on brain/narrator/director/architect, Qwen3-235B on validator/fast_model. Tested against GPT-OSS-120B (too strict, more retries) and GLM-only (too expensive, reasoning_effort conflicts with json_schema)

Validator prompt rewrite:
- RESOLUTION PACING: information discipline instead of sentence counting. Explicit anti-instruction against counting sentences (GLM hallucinated the old rule). NPC speech length is never a violation — only unsolicited facts
- RESULT INTEGRITY: explicit skip for STRONG_HIT and dialog (was triggering false positives)
- Empty-response fallback: retry without json_schema when GLM returns empty content, then parse from fenced blocks

Elvira test bot:
- Bot model configurable via `elvira_config.yaml` → `ai.bot_model` + `ai.temperature`
- Turn-type sequencing: `build_turn_context` injects mandatory action type per turn (DIALOG, INVESTIGATE, PHYSICAL RISK, etc.) above narration context
- Previous action tracking: prev_action passed between turns to prevent repetition
- Active tracks (vows, connections, combat) shown in bot context
- Setting selection respects config `setting_id` even in auto_mode (was always random)
- Prompts rewritten with concrete examples per action type

Bug fixes:
- `enter_the_fray` without track_name: auto-generates from player intent instead of crashing
- `SceneLogEntry` missing `oracle_answer` field: added
- `characters_list` UNIQUE constraint: INSERT OR REPLACE prevents crash on duplicate NPC ids
- Token logging: warns when provider returns no usage data

692 tests, ruff clean, mypy clean

## [0.46.50] — 2026-04-12

Config-driven prompt file. Shared resolution and narration. Typed config. Cleanup.

- Prompt file path now configurable via `config.yaml` → `ai.prompts_file` (default: `prompts.yaml`). `prompt_loader.py` reads filename from config instead of hardcoding
- `resolve_action_consequences` and `_update_crisis` in `game/finalization.py`: shared pre-narration resolution (move outcome, combat position, MISS clock ticks, crisis check) used by turn, correction, and momentum burn
- `narrate_scene` in `game/finalization.py`: shared narrator call → parse → optional validation. Used by all four narration paths (turn dialog, turn action, correction, momentum burn). Validation runs when `validate_result_type` is set. Eliminates 4 duplicated narrator→parse sequences and 2 inline `validate_and_retry` imports
- `SceneContext` dataclass in `game/turn.py`: bundles 12 shared parameters built once per turn. `_finalize_scene` signature reduced from 18 to 8 parameters
- `_ConfigNode` replaced by typed `AppConfig` dataclass tree (`AIConfig`, `ServerConfig`, `LanguageConfig`, `PerRoleInt`, `PerRoleFloat`, `ToolRounds`). No dynamic dict access, no `.get()` escape hatch, full mypy coverage
- `parse_engine_yaml` boilerplate reduced: 12 identical if/in/_build_nested blocks replaced by `_SIMPLE_SECTIONS` loop. 5 sections with pre-processing remain explicit
- correction.py: 5 inline imports moved to top-level, unused `resolve_move_outcome` import removed, `call_narrator`/`parse_narrator_response` replaced by `narrate_scene`
- Status commands (`/status`, `/score`) now fully narrative: "seriously wounded" instead of "health 2", "growing trust" instead of "bond 4/10", "building" instead of "3/6". No numbers, no momentum, no chaos factor. Aligns with design document principle: player sees only story, never system references
- Step 9b: Brain back to single-call prompt injection. All game state (available moves, NPCs with dispositions, active tracks) injected as XML context blocks. No tool loop. `fate_question` and `oracle_table` fields on BrainResult resolved by engine after classification. All Brain tool registrations removed. `query_npc` changed to director-only. ~13x Brain token reduction (67K → ~5K over 10 turns)
- 659 tests (-2 removed Brain tool registration tests, +1 Brain-deregistered verification test), ruff clean, mypy clean

## [0.46.0] — 2026-04-12

Track lifecycle. Connection tracks replace bond. Status commands. UI cleanup.

- Track lifecycle (`game/turn.py`): creation, progress marking, completion/failure. `track_creating_moves` in engine.yaml maps moves to track types. Engine creates ProgressTrack from Brain output (track_name + track_rank, both required). Vow tracks auto-create linked ThreadEntry. `complete_track` marks completed/failed, deactivates linked thread
- `ProgressTrack.status` field: active/completed/failed. `_find_progress_track` filters by status, matches by name substring via `target_track`, raises on ambiguous multiple tracks
- Progress marks wired: `outcome.progress_marks` consumed after `resolve_move_outcome`, marks progress on active track
- Track completion on progress roll: STRONG_HIT → completed, MISS → failed
- `list_tracks` Brain tool: `@register("brain")`, filters by track_type, returns id/name/type/rank/filled_boxes/ticks
- Brain schema: `track_name` (nullable string), `track_rank` (nullable enum, required on track-creating moves), `target_track` (nullable string for multi-track disambiguation)
- Connection tracks replace `NpcData.bond` and `bond_max` (deleted). Bond reads via `get_npc_bond(game, npc_id)` → connection track `filled_boxes`. New `npc/bond.py` module
- `bond` effect in move outcomes marks connection track progress instead of mutating NpcData
- `resolve_npc_stance` and `compute_npc_gate` take `game` argument, read bond from connection tracks
- All bond reads migrated: stance_gate, resolvers, prompt_builders, director, architect, chapters, lifecycle, activation, tools, correction, metadata, processing, setup_common, serializers
- DB schema: bond/bond_max columns removed from npcs table, status column added to progress_tracks
- Status commands: `/status` and `/score` (also `status`, `score`). Engine answers directly via strings.yaml templates, no AI call. Status button removed from UI
- `build_state` removed (was 80 lines). No per-turn state blob. Client state cache (`lastState`, `onState`, `showStatus`) removed
- `turn_complete` WebSocket message replaces `state` as end-of-turn signal. Elvira ws_runner updated
- Opening setup schema: bond/bond_max fields removed from NPC output
- Correction schema: bond field removed from npc_edit fields
- 662 tests (-3 net: bond invariant test, bond range query test removed; connection track tests added via expanded _find_progress_track test), ruff clean, mypy clean

## [0.45.0] — 2026-04-11

Full Forge move system. Data-driven consequence resolution. Combat position. Available moves tool.

- Move data model and loader (`datasworn/moves.py`): Move dataclass with trigger conditions, roll options, outcomes. Loader for all 4 settings with expansion merge (Delve→Classic, SI→Starforged). Cached accessor `get_moves(setting_id)`
- Move outcome resolver (`mechanics/move_outcome.py`): 15 effect types (momentum, health, spirit, supply, integrity, mark_progress, pay_the_price, next_move_bonus, suffer_move, position, legacy_reward, fill_clock, bond, disposition_shift, narrative). 3 handlers (suffer, threshold, recovery) for complex conditional moves. Config-driven from `engine.yaml move_outcomes`
- All 112 moves across 4 settings have structured outcomes in engine.yaml. No-roll and special_track moves excluded (no mechanical outcome)
- `apply_consequences` and all category-based routing deleted. `move_categories` cleaned (bond/disposition entries removed — handled by move outcomes)
- `resolve_move_outcome` wired into turn.py and correction.py (all 3 former `apply_consequences` call sites)
- Progress rolls: `roll_progress()` function, turn pipeline routes based on `move.roll_type`. No action dice, filled_boxes vs 2d10
- Combat position: `combat_position` field on WorldState (in_control, bad_spot). Set by move outcomes, persisted in snapshot/restore
- `available_moves` Brain tool: state-aware move filtering. Combat position restricts combat moves (in_control→strike/gain_ground, bad_spot→clash/react_under_fire). Track existence gates progress moves. Suffer/threshold moves excluded (reactive)
- Brain schema enum: all Datasworn moves across all settings. Brain prompt directs to call `available_moves` tool instead of hardcoded move list
- `brain_moves` and `brain_move_stats` removed from engine.yaml (replaced by Datasworn data + available_moves tool)
- All move references across codebase migrated to full Datasworn keys (category/move_key format)
- Elvira: `combat_position` in StateSnapshot, recorder, and invariant checker
- 665 tests (+127 net), ruff clean, mypy clean

## [0.44.0] — 2026-04-11

Mythic GME 2e integration: fate system, scene structure, random events. Director reduced.

- Fate system (step 3): fate chart resolver (9×9 odds/chaos matrix), fate check resolver (2d10 + modifiers), random event trigger on doublets, likelihood resolver (NPC disposition + chaos + resources → odds), `fate_question` Brain tool
- Scene structure (step 4): `check_scene()` replaces `check_chaos_interrupt()`. d10 vs CF → expected/altered/interrupt. Scene Adjustment Table (d10, single/double adjustments). `<altered_scene>` and `<interrupt_scene>` tags in narrator prompt. Scene-end bookkeeping: chaos adjustment for all scene types including dialog (NPC stance evaluation), list maintenance (weight bumps, new NPC addition, consolidation at 25 entries). Expected scene enrichment via `<active_thread>` tag
- Director reduction (step 5): pacing removed from Director output, DirectorGuidance dataclass, prompt, schema. Pacing fully engine-computed via scene structure + narrative direction. NPC reflections and AIMS retained
- Random events (step 6): event focus table (12 categories), meaning tables (actions + descriptions), random event pipeline (focus → target → meaning → assemble), weighted list selection, pending event buffer with drain, `<random_event>` tag prompt injection, fate doublet → event integration
- New dataclasses: `FateResult`, `RandomEvent`, `SceneSetup`
- New modules: `mechanics/fate.py`, `mechanics/random_events.py`, `mechanics/scene.py`
- Removed: legacy `mechanics.py` monolith (1011 lines dead code), `check_chaos_interrupt()`, `chaos_interrupt` field on SceneLogEntry, `DirectorGuidance.pacing`, `_map_pacing_hint()`
- Chaos factor range changed from 3–9 to 1–9 (Mythic 2e)
- engine.yaml: new `fate` section (default_method, likelihood_rules)
- 538 tests (+53 net: +57 new, -4 window dressing), ruff clean, mypy clean

## [0.43.0] — 2026-04-11

Config-driven refactor. Mechanics modularized. Finalization deduplicated.

- 28 magic numbers moved from Python to engine.yaml: NPC reflection importance, death corroboration threshold, seed importance floor, gate memory counts, activated memory count, memory retrieval weights, reflection recency floor, about_npc relevance boost, consolidation ratio, monologue/description/arc char limits, opening clock defaults, fired clock keep_scenes, move routing (miss_endure, recovery), architect forbidden moods
- New engine.yaml sections: `enums` (9 enum lists), `memory_retrieval_weights`, `opening`, `move_routing`, `architect`
- NARRATOR_METADATA_SCHEMA and OPENING_SETUP_SCHEMA converted to lazy cached functions with config-driven enum values
- mechanics.py (1030 lines) split into mechanics/ package: world.py, resolvers.py, consequences.py, stance_gate.py, engine_memories.py. Re-export hub preserves all existing imports
- New game/finalization.py: shared `apply_engine_memories` and `apply_post_narration` used by turn, correction, and momentum burn
- Bug fix: correction and momentum burn now run `consolidate_memory` and set `needs_reflection` flags (previously skipped)
- Pre-existing test failure fixed (test_task_mentions_consequence_weaving checked wrong prompt section)
- 485 tests, ruff clean, mypy clean

## [0.42.0] — 2026-04-10

GLM-4.7 prompt tuning. Config-driven prompts.

- Narrator system prompt restructured for GLM-4.7 begin-bias: hardest constraints (GENRE PHYSICS, PLAYER AGENCY, CONSEQUENCE COMPLIANCE) at top, MUST/STRICTLY language throughout
- New GENRE PHYSICS constraint block: materials must not exhibit consciousness, memory, or transformation
- All task templates, instruction fragments, and secrets label moved from Python to prompts.yaml (6 task templates, 2 instruction fragments). prompt_builders.py is now pure XML assembly
- Vocabulary block instruction moved from prompt_blocks.py to prompts.yaml
- Atmospheric drift wordlists expanded for GLM patterns (weep, ooze, writhe, visage, reshape, phantom, etc.) across all 4 settings. Thresholds lowered
- Player agency rule validator: 3 new regex patterns for GLM-specific violations (weight of failure, makes you want to, objects imposing feelings)
- LLM validator: new GENRE PHYSICS check with "when in doubt, FAIL" for genre drift
- Architect: rule-based mood sanitizer strips forbidden moods (surreal, haunted, dreamlike, etc.) from blueprint acts. Rule-based drift check on all blueprint text fields
- Architect/Kishōtenketsu prompts: FORBIDDEN mood terms list added
- Director system prompt: genre constraint added to guidance
- All prompts (brain, narrator, metadata, director, architect) converted to MUST/STRICTLY language
- `max_tool_rounds` config section: brain and director tool round limits now in config.yaml
- `reasoning_effort: "none"` replaces deprecated `disable_reasoning: true`
- Narrator temperature 0.8 → 1.0 per Z.ai recommendation for GLM-4.7
- Elvira results: retries 19 → 5, failures 2 → 0, first-pass rate 11% → 44%, zero genre drift, zero spatial issues
- 485 tests

## [0.41.0] — 2026-04-10

Step 2: Brain and Director tool calling, Ask the Oracle.

- Brain: two-phase call (optional tool loop + json_schema). Slim prompt with NPC names, stats, state
- Director: two-phase call (tool loop for NPC/thread/clock queries + json_schema for structured output). Tokens now tracked via `log_role="director"`
- `ask_the_oracle` move: engine rolls action/theme meaning pair from Datasworn tables, result injected as `<oracle_answer>` tag in narrator prompt
- `max_narration_history` reduced from 5 to 3 (token optimization)
- Fix: accumulator reset on failed reflections now preserves accumulator value. Only resets on successful reflection or API failure. Previously the Director's fallback reset zeroed the accumulator every time it ran without producing a reflection, preventing NPCs from ever reaching the reflection threshold
- Elvira logging: BrainRecord per turn, NPC importance_accumulator and needs_reflection, engine result field, Director npc_guidance
- Validated with GLM-4.7 on Cerebras: varied move classification, NPC memories building, Director guidance with npc_guidance
- 485 tests

## [0.40.0] — 2026-04-10

Step 1: oracle roller. Vocabulary control. Cleanup.

- `OracleResult` dataclass; `OracleTable.roll()` preserves actual die value
- `roll_oracle` Brain tool: setting-aware Datasworn oracle roll
- Vocabulary control per setting: substitutions, sensory palettes, config-driven atmospheric drift detection in rule validator. All four settings configured
- Visual bar characters removed from clock display (accessibility)
- 485 tests (18 new)

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
- 467 tests (51 new)

## [0.38.0] — 2026-04-10

Steps 3.5 + 3.6: database layer and tool calling infrastructure.

- SQLite read model (`engine/db/`): 8 tables mirroring GameState, full sync after every state change, query functions for NPCs/memories/threads/clocks
- Tool registry (`tools/registry.py`): `@register("brain", "director")` decorator, type hints → OpenAI schemas
- Tool handler (`tools/handler.py`): dispatch + iterative tool-call loop
- Built-in query tools: `query_npc`, `query_active_threads`, `query_active_clocks`, `query_npc_list`
- Tool calling probe (`tests/tool_calling_probe.py`): 15 test cases, Qwen 87% / GLM 93% pass rate
- 34 db tests, 15 tool tests

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
- 57 new tests (404 total)

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
