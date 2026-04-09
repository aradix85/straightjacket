# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

---

---

## [0.37.0] — 2026-04-09

Roadmap steps 2 + 3: Brain slimming and metadata extractor split. Massive AI surface reduction. Code audit: bloat removal, legacy cleanup, test infrastructure overhaul.

### Step 2 — Brain slimming
- **Position resolver** in mechanics.py. Engine-computed position (controlled/risky/desperate) via 8 weighted factors from engine.yaml: resource pressure, NPC disposition+bond, chaos factor, consecutive results, threat clock pressure, move category baseline, secured advantage, site depth (placeholder). 3 situational overrides for edge cases. ~25 lines scoring, deterministic, testable
- **Effect resolver** in mechanics.py. Engine-computed effect (limited/standard/great) via 5 weighted factors: position correlation, NPC bond, secured advantage, move baseline. Same threshold mechanism
- **Time progression resolver** in mechanics.py. Pure move-type → progression lookup from engine.yaml. No AI needed
- **BrainResult** stripped from 13 to 9 fields: position, effect, dramatic_question, time_progression removed
- **Brain schema** stripped of same 4 fields. ~50 tokens saved per Brain call
- **Director schema** stripped of pacing and act_transition fields (already engine-computed since v0.36.0)
- **SceneLogEntry** dramatic_question field removed
- **prompts.yaml** brain_parser prompt stripped of position/effect/dramatic_question/time_progression instructions
- 17 resolver tests added (test_resolvers.py)

### Step 3 — Metadata extractor split
- **Engine-generated memories** via `generate_engine_memories()` in mechanics.py. Templates in engine.yaml (memory_templates, memory_result_text, memory_move_verbs). Uses `derive_memory_emotion()` for emotional weight, `score_importance()` for importance scoring
- **Engine-generated scene context** via `generate_scene_context()` from template in engine.yaml
- **Metadata AI schema** reduced from 10 to 5 fields: scene_context, location_update, time_update, memory_updates, emotional_weight removed. AI extractor handles only: new_npcs, npc_renames, npc_details, deceased_npcs, lore_npcs
- **Dead code removed**: `_resolve_slug_refs` (47 lines), `apply_memory_updates` (125 lines), all NPC imports in parser.py that were only used by the removed function
- **prompts.yaml** narrator_metadata prompt stripped to NPC detection only

### Code audit
- **SerializableMixin** in serialization.py. Eliminates to_dict/from_dict boilerplate across 20 dataclasses (~80 lines removed)
- **Stub migration**: 12 test files migrated from inline `_stub()` to conftest fixtures (stub_engine, stub_emotions, stub_all, load_engine). conftest extended with death_emotions, narrative_direction, story, creativity_seeds, scene_range_default, position_resolver, effect_resolver, time_progression_map, memory templates
- **Legacy removal**: 6 NiceGUI-legacy i18n functions, `data_dir()`, `reload_emotions()`, .gitignore NiceGUI/voice entries
- **Bug fixes**: api_client.py duck typing → isinstance. correction.py import order. npc/activation.py duplicate imports. persistence.py NPC integrity restored. TurnSnapshot defensive catch removed (corrupt = crash)
- **HTML fixes**: XSS in renderSavesList and showRetryOffer (inline onclick → DOM events). Hardcoded English in showStatus → strings.yaml i18n
- **Structure**: tests/playerbot elvira/ → tests/elvira/, all doc refs updated
- **Type tightening**: prompt_builders Sequence types, GameState.from_dict strict (no backwards-compat defaults)
- **Dead code**: parser.py _process_game_data + Step 1/1.5 game_data JSON parsing removed (replaced by two-call pattern)

---

## [0.36.0] — 2026-04-08

Character creation overhaul. Progress tracks, Mythic list seeding, stat validation, truths integration. AI surface reduction: pacing, act transitions, memory emotions, opening clock to engine.

- **`ProgressTrack` dataclass** in models_base.py. Rank-based ticks_per_mark (troublesome=12, dangerous=8, formidable=4, extreme=2, epic=1). `mark_progress()`, `filled_boxes` property. `PROGRESS_RANKS` dict as single source of truth. Background vow becomes a progress track at creation
- **`ThreadEntry` dataclass** in models_story.py. Mythic threads list: id, name, type (vow/goal/tension/subplot), weight, source, linked_track_id. Background vow seeded as first thread (weight 2). Truth selections that match engine.yaml patterns seed additional tension threads
- **`CharacterListEntry` dataclass** in models_story.py. Mythic characters list: id, name, type (npc/entity/abstract), weight. Vow subject seeded as abstract entry. Opening scene NPCs populate the list after extraction
- **`NarrativeState` extended** with `threads` and `characters_list`. Both included in snapshot/restore (length-based truncation)
- **`GameState` extended** with `assets` (list of asset IDs), `vow_tracks` (list of ProgressTrack), `truths` (dict of truth selections). All serialized and persisted
- **Stat validation** in `game_start.validate_stats()`. Checks sum, per-stat range, and distribution against `engine.yaml stats.valid_arrays`. Rejects invalid client input
- **Creation enforcement** in `game_start.validate_creation()`. Validates path count, asset count, asset categories against setting's `creation_flow`, rejects truths for settings that don't support them
- **`stats.target_sum` corrected** from 7 to 9. Was a pre-existing bug — Starforged [3,2,2,1,1] sums to 9
- **Chaos factor derived from vow** in `game_start._compute_chaos_start()`. Keyword matching against engine.yaml `creation.chaos_vow_modifiers`: "survive the siege" → chaos +2, "explore the unknown" → chaos -1. Deterministic, no AI
- **Truths in narrator prompt** via `prompt_blocks.truths_block()`. Player truth selections injected as `<world_truths>` block in every narrator system prompt. Treated as established canon
- **Truth-to-thread derivation** via engine.yaml `creation.truth_threads`. Substring match on truth summaries seeds tension threads at creation. "Communities are scattered and isolated" → thread "Isolation threatens supply lines"
- **Vow subject in characters list**. `creation_data.vow_subject` seeds an abstract entry in the Mythic characters list. "Find my lost sister" → sister appears as rollable target for random events before she's on-screen
- **`build_creation_options` expanded**. Now sends: truths (per setting, with options), backstory prompts, name tables, starting assets (non-path, per setting), creation flow flags, stat constraints (target_sum, min, max, valid_arrays), creation defaults (max_paths, vow ranks). Client receives everything needed for a complete creation form
- **`creation_flow` in settings YAML**. Per-setting flags: has_truths, has_backstory_oracle, has_name_tables, has_ship_creation, starting_asset_categories. Classic skips backstory oracle. Sundered Isles enables ship creation. Engine reads flags in `build_creation_options` and `SettingPackage.creation_flow`
- **engine.yaml `creation` section**. max_paths, max_starting_assets, starting_asset_categories, background_vow_default_rank, chaos_vow_modifiers, chaos_modifier_values, truth_threads
- **Director pacing to engine.** `apply_director_guidance` now ignores AI pacing and computes it from `get_pacing_hint()` via `_map_pacing_hint()`. AI pacing value logged when it disagrees, but engine value wins
- **Director act_transition to engine.** `_check_engine_act_transition()` fires when scene_count ≥ act scene_range end. Deterministic, no AI flag needed. Back-fill of skipped acts preserved. AI `act_transition` field ignored
- **Opening scene clock to engine.** `game_start` creates a threat clock (6 segments, 1 filled, named after background vow) before any AI call. Opening setup extractor no longer needed for clock creation
- **Opening scene time_of_day to engine.** Set to "morning" by `game_start` before AI calls. AI extractor can still override if narration implies different time
- **Memory emotional_weight derivation.** `mechanics.derive_memory_emotion()` computes emotional weight from (move_category, result, disposition) via engine.yaml `memory_emotions` table. Combines base emotion ("fear_pain", "trusting_open") with disposition suffix ("_hostile", "_warm"). Reduces metadata extractor's decision surface
- **ARCHITECTURE.md updated**. File map, module ownership table, key design decisions, settings YAML format — all reflect new types, creation flow, and AI surface reduction
- 57 new tests (test_creation.py): ProgressTrack mechanics, ThreadEntry/CharacterListEntry roundtrip, NarrativeState snapshot with threads, GameState with new fields, stat validation (valid/invalid sum/range/array/missing), chaos vow modifier, vow seeding, truth thread seeding, vow subject, truths block, build_creation_options structure, creation flow per setting, creation enforcement (paths/assets/truths/vow rank/cross-setting), memory emotion derivation, engine pacing override, opening clock
- **Character creation UI rewritten.** Full creation form in index.html: setting picker with truths (per-setting, dropdown per truth category), name roll button (from Datasworn name tables), backstory roll button (from Datasworn prompts), vow rank selector (5 ranks), vow subject field, starting asset picker (grouped by category), stat validation against server-provided constraints (target sum, min/max from engine.yaml). All fields update dynamically when setting changes. Truths and assets hide for settings that don't support them (creation_flow flags). Stat total shows green/red validation
- **strings.yaml updated.** Stats label/total/validation now parameterized ({target}, {min}, {max}). New keys: ui.backstory_prompt, ui.vow_rank, ui.vow_subject, ui.truths, ui.truth_pick, ui.starting_assets, ui.name_roll
- **Elvira character creation rewritten.** Stats from engine.yaml valid_arrays (was hardcoded sum=7 brute force). Truths rolled randomly per setting. Starting assets rolled from allowed categories. Vow rank and vow subject passed to engine. `_random_stats` now picks from valid_arrays and shuffles (deterministic, no retry loop)
- **Elvira invariants expanded.** New checks: vow_tracks (id, name, rank, ticks range), threads (id uniqueness, weight > 0), characters_list (id uniqueness), truths (non-empty summaries), assets (non-empty ids)
- **Elvira state recording.** StateSnapshot gains active_threads, active_characters, active_vow_tracks counts. Logged per turn for trend analysis
- **Elvira mypy fix.** `_check_npc` `_e` parameter typed as `_ConfigNode` (was untyped, pre-existing error)
- **elvira_config.yaml** stats comment corrected (was sum=7, now references engine.yaml valid_arrays)
- 404 tests, ruff clean, mypy clean

---

## [0.35.0] — 2026-04-08

Code audit, strict type checking, Elvira batch runner, validator tuning, token logging.

- **`disallow_untyped_defs = true`** in mypy config. All 57 src files + 16 test files fully type-annotated. Tests removed from mypy exclude. 73 files, zero errors
- **Dubbele `_read_version()`** removed from `__init__.py` — imports `VERSION` from config_loader
- **`narrator_was_salvaged` global** removed (never read outside narrator.py)
- **`_default_scene_range`** made public (`default_scene_range`) — was underscore-imported across 3 modules
- **`MAX_NARRATION_CHARS`** moved to engine.yaml (`pacing.max_narration_chars`)
- **`NPC_STATUSES`** constant as frozenset in models_npc.py, used in correction.py validation
- **Snapshot/restore blueprint asymmetry** fixed — `restore()` now clears blueprint when snapshot had None
- **40 dead emoji entries** removed from i18n.py `E` dict (NiceGUI legacy)
- **`_ConfigNode` isinstance** replaced with duck typing (`hasattr(to_dict)`)
- **`get_stat()` silent fallback** replaced with `ValueError` on invalid stat name
- **`_ensure_loaded` underscore import** replaced with public `all_strings()` in strings_loader.py
- **`score_importance`** typed with `@overload` for correct debug=True/False return types
- **Elvira `--setting` and `--style`** CLI overrides added to elvira.py
- **Elvira batch runner** (`elvira_batch.py`): runs all settings × styles, aggregates compliance report
- **Session log timestamps**: log filenames include `_YYYYMMDD_HHMM` — no more overwrites
- **Token logging**: all 10 AI call sites tagged with `log_role`. Per-call token counts logged to console and accumulated per turn in Elvira session logs. Token summary in batch report
- **Validator prompt tuned** for false positive reduction: "camera test" for PLAYER AGENCY, sensory descriptions of failure explicitly allowed on MISS, "when in doubt, PASS" directive. Compliance 73% → 86.5%

---

## [0.34.0] — 2026-04-08

Code audit and cleanup. i18n for HTML client. Dice roll display removed.

- **Server binds localhost by default.** `server.host: "127.0.0.1"` in config.yaml. Was hardcoded `0.0.0.0` (all interfaces). SECURITY.md updated
- **WebSocket origin check.** Rejects cross-site connections. Non-browser clients (Elvira, curl) pass through
- **Dice roll display removed.** Server no longer sends roll data to the client. Player sees only narration — no stats, no dice, no system references (design document compliance). Engine-internal roll tracking unchanged (needed for momentum burn, correction, Elvira diagnostics). `build_roll_data()` removed from serializers.py. `appendRoll` removed from client
- **HTML client i18n.** All hardcoded English strings moved to strings.yaml (ui.* prefix). Server sends `ui_strings` message at connect. Client uses `s("key")` lookup function. Zero hardcoded UI text remaining. Translators work with strings.yaml only
- **strings.yaml cleanup.** 266 dead NiceGUI-era strings removed (332→66 live keys → 113 with new ui.* keys). All HTML (`<b>`, `<br>`) and markdown (`*...*`) stripped. Plain text only
- **emotions.yaml gaps filled.** 36 terms from disposition_map added to importance map at correct tiers. Zero gaps between disposition_map and importance
- **chapters.py refactored.** `start_new_chapter` split from ~160 lines into 6 focused functions
- **"inactive" ghost status** removed from correction.py valid_statuses
- **German strings in AI prompts** removed. "(keine)" → "(none)" in brain.py, architect.py
- **Disposition schema** narrowed to canonical 5 (hostile, distrustful, neutral, friendly, loyal). Was 8 with synonyms that were silently normalized
- **Em-dash normalization removed.** Was replacing em-dashes with " - " in 3 code paths. Em-dashes are typographically correct and screen readers handle them fine
- **MAX_VALIDATOR_RETRIES** now config-driven (reads `ai.max_retries.narrator`). Was hardcoded constant
- **config.yaml top_p** simplified. 11 identical `0.95` values → single `default: 0.95` with per-role override support
- **scene_range validation** added after blueprint parsing. Invalid arrays replaced with engine.yaml default
- **Provider cache key** changed from `hash()` to `hashlib.sha256` (stable, deterministic)
- **provider_base.py** type annotations tightened: `tool_calls: list[dict[str, str | dict]]`, `usage: dict[str, int] | None`
- **Brain dialog fallback** now sets `approach="fallback"` for downstream detection
- **Narrator truncation tracking** via module-level `narrator_was_salvaged` flag
- **api_client.py** extra_body handling made explicit (3 branches)
- **Session model documented** in SECURITY.md (single-session, tab takeover)
- **app_ws.py removed.** Duplicate entry point. Only `run.py` remains
- **__init__.py** added `__version__` (reads pyproject.toml without triggering engine imports)
- **Tooling:** `.editorconfig`, `.pre-commit-config.yaml` (ruff + mypy as system hook), `clean.py` (cross-platform pycache cleanup)
- **Test cleanup.** 8 WebSocket ceremony tests → 1 flow test. 5 coverage-padding tests removed. 8 roll display tests removed. Em-dash tests updated. 367→347 tests, all passing
- 347 tests, ruff clean, mypy clean

## [0.33.0] — 2026-04-07

Prompt rewrite for Qwen3. Hybrid validator. Retry architecture overhaul. Test cleanup.

- **prompts.yaml rewritten** for Qwen3-235B-A22B-Instruct-2507. Data-driven hierarchy: most-violated rules (information dosing, player agency, result integrity) placed directly after `<role>` tag for maximum attention weight. 217→162 lines. All conditional "If X: do Y" rules removed — XML tags in user prompt are self-documenting. Positive instructions preferred over prohibitions (SillyTavern community finding). Concrete examples per rule
- **Hybrid validator** (`ai/rule_validator.py`): instant rule-based checks (regex patterns for player agency, result integrity, genre fidelity, output format, NPC monologue heuristic) run alongside LLM semantic checks. Both layers always run, results merged with source tagging (`[rule]`/`[llm]`). LLM prompt narrowed to resolution pacing and subtle agency — the checks that require semantic understanding
- **Retry architecture overhauled**: max retries 2→3. Correction injected into system prompt (via `call_narrator` `system_suffix` parameter) AND user message prefix — double reinforcement at highest-weight positions. Concrete rewrite instructions per violation type ("Cut the NPC's speech to answer ONLY the question asked") instead of repeating what went wrong. Best-of selection across all attempts instead of always taking the last
- **Prompt stripping on retry**: RESOLUTION PACING violations trigger removal of NPC secrets, memories, and agenda from the retry prompt. The model can't leak what it doesn't have
- **Narration history skip on retry**: `call_narrator` `skip_history` parameter. Retries don't see previous narrations (which contained the same violations) as few-shot examples
- **Validator LLM prompt sharpened**: PLAYER AGENCY explicitly scoped to player character only — NPCs MAY think/feel/remember (eliminates false positives on NPC characterization). Player character name injected for disambiguation. WEAK_HIT cost must be specific and nameable, not atmospheric. Dialog scenes skip RESULT INTEGRITY
- **Validator diagnostics**: violations tagged with `[rule]`/`[llm]` source. Per-turn `validator_violations` list in Elvira session JSON. `full_debug_log` option for complete turn data
- **models.py split** into 4 files: `models_base.py` (185 lines), `models_npc.py` (82), `models_story.py` (310), `models.py` (237, re-export hub)
- **format_utils.py**: `PartialFormatDict` extracted, shared by prompt_loader and strings_loader
- **`disable_reasoning` removed** from config.yaml — Instruct-2507 is non-thinking by design, Cerebras rejects the parameter
- **Dead code removed**: sidebar strings (28 keys), `EDGETALES_CONFIG` env var, `labels` dict from `build_state()`, global F401 ruff ignore
- **Test cleanup**: coverage-padding tests removed (364→341→366 with new rule_validator tests). 25 rule_validator tests. Tests verify behavior, not coverage percentages
- **Elvira fail rate**: 84% → 27% (validator failures after all retries, measured across 4 Elvira runs)
- 366 tests, ruff clean, mypy clean

## [0.32.0] — 2026-04-06

NiceGUI replaced with Starlette + WebSocket. Minimal screen reader UI. Elvira WebSocket mode.

- **NiceGUI removed.** Entire ui/ directory (11 files, 2635 lines), app.py, custom_head.html deleted. `nicegui` and `cryptography` removed from requirements.txt
- **New web server**: Starlette + uvicorn, WebSocket protocol. Four modules: `web/server.py` (routing, dispatch), `web/handlers.py` (19 async handlers), `web/session.py` (Session + BurnOffer dataclasses), `web/serializers.py` (i18n label resolution, state/roll/creation serializers, dialog highlighting)
- **Minimal HTML client**: single-page app (645 lines), no sidebar, no overlays except burn/gameover/story-complete. Scene headings (h2) for screen reader navigation, aria-live for automatic narration readout, focus management on every phase transition. Two buttons (Status, Save/Load), one text input. Type "recap" for story summary, "## correction" for undo
- **Elvira WebSocket mode** (`--ws`): plays via WebSocket protocol, starts server in-process. Same AI behavior, same invariant/quality checks. Tests the full stack: protocol → handlers → engine → serializers. `debug_state` endpoint returns full GameState for invariant checking
- **Chapter archives removed** from persistence.py (5 functions, ~80 lines). `delete_save` inlines orphan cleanup. `get_save_info` simplified from 12 fields to 5. `list_saves` inlined into `list_saves_with_info`. Dead `audio_bytes`/`audio_format` filtering removed from `save_game`
- **Engine bug fixes**: `scene_present_ids` excluded mentioned NPCs (defeated presence guard), `"inactive"` ghost status removed from correction ops, `"TurnSnapshot"` string annotation → bare type, `damage()` fallback logs warning, dead `moves:` list removed from engine.yaml
- **Test infrastructure**: `conftest.py` rewritten (only logging_util stub, no package-level stubs). Named fixtures (`load_engine`, `stub_engine`, `stub_emotions`). All 7 test files refactored to use fixtures. 49 new web module tests (Session, BurnOffer, serializers, WebSocket integration via Starlette TestClient)
- **Docs updated**: SECURITY.md, CONTRIBUTING.md, ARCHITECTURE.md, README.md — all NiceGUI references removed, web module documented
- `provider_base.py`: "NiceGUI event loop" → "server event loop"
- `pyproject.toml`: SIM117 NiceGUI ignore removed
- 254 tests, ruff clean, mypy clean (48 source files)

---

## [0.31.0] — 2026-04-06

Project independence. Renamed to Straightjacket. Full code audit.

- **Project renamed** from EdgeTales (modular fork) to Straightjacket (standalone project)
- **ARCHITECTURE.md**: turn pipeline, module ownership, file map, extension guides
- **ORIGINS.md**: replaces UPSTREAM_SYNC.md — project history and credits
- `_fields_to_dict` / `_fields_from_dict` serialization helpers in models.py — eliminates boilerplate across 10 dataclasses (ClockData, ClockEvent, NarrationEntry, StoryAct, Revelation, PossibleEnding, NpcEvolution, PlayerPreferences, MemoryEntry, BrainResult)
- `bootstrap_log.py`: shared print-logger for early-loading modules. Replaces five duplicate `_log`/`print()` patterns in config_loader, engine_loader, emotions_loader, prompt_loader, strings_loader
- VERSION single source of truth: `config_loader._read_version()` reads from pyproject.toml instead of hardcoded string
- `app.py`: UI tuning constants (reconnect timeout, invite limits) now read from `cfg().ui` instead of hardcoded values
- `app.py`: `__import__("threading").Lock()` → proper `import threading`
- `provider_openai.py`: `from typing import Any` moved from method body to top-of-file
- `mechanics.py`: `record_scene_intensity` uses `eng().pacing.window_size` instead of hardcoded 5
- `mechanics.py`: `locations_match` docstring documents empty-input semantics
- `provider_base.py`: `create_with_retry` docstring documents blocking sleep and async-safety requirement
- `help.py`: removed `help.kid_title`/`help.kid_text` references (keys missing from strings.yaml)
- 205 tests, ruff clean, mypy clean (58 files)

---

## [0.30.0] — 2026-04-06

Upstream sync v0.9.93. NPC arc system. Phase dedup. Memory guard. Test audit.

- **Upstream sync**: all engine features through v0.9.93 backported
- `NpcData.arc` field: narrative trajectory set by Director, evolves each reflection. Exposed in `<target_npc>`, `<activated_npc>`, and Director `<reflect>` tags
- `updated_instinct` removed from Director schema and apply logic. Instinct locked after first fill via `needs_profile="true"` — never updated again. `updated_arc` replaces it: expected to change every reflection
- Instinct quality guidance in Director prompt: BAD/GOOD examples, "set once, never updated"
- `StoryBlueprint.triggered_director_phases`: phase-trigger deduplication in `should_call_director`. Phase marked as fired in turn.py and correction.py. Survives snapshot/restore
- `process_npc_details` memory guard: rejects identity reveal when NPC has memories and zero word overlap to new name. Creates stub NPC with `world_addition` fallback description. `world_addition` threaded through `apply_narrator_metadata`
- `tone_authority_block` in narrator system prompt: player's chosen tone as first-class element before rules
- NPC identity layers rule in narrator prompt: instinct (wiring) vs arc (development) as distinct dimensions
- NPC emotional range rule in narrator prompt: emotional control is one option, not the default
- `SceneLogEntry.revelation_check`: diagnostic dict logging `{id, confirmed}` per turn when a revelation was pending
- `check_npc_agency` returns `tuple[list[str], list[ClockEvent]]` — agency clock events logged in session_log (was a regression since v0.26.0)
- Social move unresolved target warning in `apply_consequences`
- **Bugfix**: Elvira spatial consistency check used `prev.last_memory` as guard instead of `prev.last_location`
- **Bugfix**: Elvira `_random_stats` had unbounded `while True` — now `for _ in range(1000)` with RuntimeError
- `NpcSnapshot.arc` field added to Elvira recorder
- `autonomous_clock_tick_chance` 0.18 → 0.20
- Tone aliases: `grounded_drama`, `pulp` in kishotenketsu probability table
- **Test audit**: 31 window-dressing tests removed (mutable defaults, trivial roundtrips, Python builtins, config value assertions, duplicate coverage). 36 stale imports cleaned
- 205 tests, ruff clean, mypy clean (66 files)

## [0.29.1] — 2026-04-05

Serialization tightening. Fallback removal. Module splits. Test coverage.

- `from_dict()` tightened across all models: `StoryBlueprint`, `ChapterSummary`, `NpcEvolution`, `ClockEvent` — direct key access, no `.get()` defaults. from_dict reads own to_dict output; call sites that pass AI output sanitize first
- `ClockEvent.to_dict()`: always writes all four fields (was conditional)
- Removed 60-line hardcoded fallback blueprints from `call_story_architect` — returns None on failure, engine runs without blueprint
- `call_story_architect`: runtime fields (`revealed`, `triggered_transitions`, `story_complete`) added at call site before `StoryBlueprint.from_dict`
- `game_start.py`, `chapters.py`: handle `blueprint=None` from architect failure
- **Module split: chapters.py** (487→303 lines): `build_epilogue_prompt`, `build_new_chapter_prompt` → `prompt_builders.py`. `call_chapter_summary` → `ai/architect.py`. chapters.py retains only orchestration (`generate_epilogue`, `start_new_chapter`)
- **Module split: gameplay.py** (532→271 lines): `render_momentum_burn`, `render_epilogue`, `render_game_over`, `_make_chapter_action` → new `ui/endgame.py` (285 lines). gameplay.py retains only `process_player_input`
- Prompt builders now use `_xa`/`_xe` from xml_utils (was raw `html.escape` — same output, consistent style)
- Removed duplicate `ucfg["dice_display"]` in `settings.py`
- Removed `test_story_blueprint_null_safety` — null-handling is not from_dict's job
- 13 unused imports cleaned across 7 files (ruff F401)
- 4 new correction flow tests, 6 new parser regression tests
- README: serialization docs updated, test conventions documented
- parser.py: docstring expanded with architecture note
- 225 tests, ruff clean, mypy clean (57 source files)

## [0.29.0] — 2026-04-05

Code audit. Config-driven game logic. Defensive code removal. Elvira mypy coverage.

- **Bugfix**: Elvira bot crashed on any turn with a story blueprint — `CurrentAct.get()` dict-style access on dataclass (recorder.py, ai_helpers.py). Same crash on chapter transitions via `ChapterSummary.get()` in runner.py
- **Bugfix**: `fuzzy_match_existing_npc` skipped edit-distance check when significant-word-overlap ratio was below threshold — `continue` exited the NPC loop instead of just skipping the overlap branch. "Markus Eisenborg" vs "Markus Eisenberg" now matches correctly as `stt_variant`
- **Bugfix**: Elvira `quality_checks.py` accessed `NpcData.memory_count` (doesn't exist) — `len(npc.memory)` is the correct access
- **Bugfix**: Elvira `recorder.py` passed `list[ClockEvent]` into `list[dict]` field — now calls `e.to_dict()` for each event
- Move categories config-driven: `COMBAT_MOVES`, `SOCIAL_MOVES` hardcoded sets → `engine.yaml move_categories` with 7 category keys (combat, social, endure, recovery, bond_on_weak_hit, bond_on_strong_hit, disposition_shift_on_strong_hit)
- Disposition shift ladder config-driven: hardcoded `shifts = {"hostile": "distrustful", ...}` → `engine.yaml disposition_shifts`
- NPC seed emotion map config-driven: hardcoded `_disp_to_emotion` dict → `engine.yaml disposition_to_seed_emotion`
- Move enum single source of truth: `schemas.py` reads `move_stats.keys()` instead of redundant `moves:` list
- `Resources.adjust_momentum` and `reset_momentum`: removed misleading hardcoded parameter defaults (`floor=-6`, `ceiling=10`). Callers must pass config values explicitly. `reset_momentum` now takes `reset_value` and `max_cap` parameters instead of hardcoded 2 and 10
- Defensive `from_dict` bloat removed: `Resources`, `WorldState`, `PlayerPreferences`, `DirectorGuidance`, `NarrativeState`, `CampaignState`, `GameState` — all tightened from `.get()`/`if key in data`/`isinstance` guards to direct key access on own `to_dict()` output
- `NarrativeState.restore()`: same treatment — `.get()` fallbacks removed on own `snapshot()` output
- `ClockEvent.from_dict`: `.get()` removed for always-present fields
- Defensive `getattr(obj, 'known_field', fallback)` removed: `prompt_blocks.py` (2x), `director.py`, `architect.py`
- `WorldState.to_dict()` was duplicate of `snapshot()` — now delegates
- mypy: Elvira bot removed from exclude list in pyproject.toml. 65 files checked (56 engine + 9 elvira), 0 errors. Two type errors caught and fixed by this change
- 216 tests, ruff clean, mypy clean

## [0.28.0] — 2026-04-05

ChapterSummary + CurrentAct dataclasses. UI bugfix. Full mypy coverage. Dead code removal.

- `ChapterSummary` dataclass: 9 typed fields, replaces `list[dict]` in `CampaignState.campaign_history`. Attribute access across brain.py, architect.py, prompt_blocks.py, chapters.py, gameplay.py
- `NpcEvolution` dataclass: typed NPC projections inside ChapterSummary
- `CurrentAct` dataclass: typed return from `get_current_act()`, replaces raw dict. Attribute access across director.py, prompt_blocks.py, sidebar.py, architect.py
- `call_chapter_summary` return type `dict` → `ChapterSummary`
- `get_current_act` return type `dict` → `CurrentAct`
- **Bugfix**: `gameplay.py _make_chapter_action` accessed `g.chapter_number`, `g.campaign_history`, `g.current_location` directly on GameState instead of sub-objects. Crashed every new-chapter and game-over flow.
- **Bugfix**: `app.py` drawer declared after lambda reference — reordered for correct scoping
- mypy: 0 errors across all 56 source files including UI layer. No suppressions. PageContext `object` → `Any`, callbacks with no-op defaults, `assert isinstance` narrowing
- Removed 15 unused emoji entries from `E` dict (castle, rocket, crystal, city, black_heart, scales, moon_half, candle, dagger, search, speech, books, purple_circle, white_circle, yellow_heart, play, globe, mic, microphone, ndash)
- Documented `CampaignState.snapshot()` scope (epilogue flags only — chapter_number/campaign_history never mutate within a turn)
- Removed defensive `isinstance(ch, dict) else ch` in CampaignState.from_dict
- Removed 13 window-dressing tests, added 10 functional tests. 216 total, ruff clean, mypy clean

## [0.27.0] — 2026-04-05

MemoryEntry dataclass. Code audit cleanup. Test coverage expansion.

- `MemoryEntry` dataclass: 10 typed fields for NPC memory entries, replaces `list[dict]` in `NpcData.memory`. Attribute access across 10 engine files, 60+ `.get()` call sites eliminated
- `NpcData.from_dict()` converts legacy dict memories to `MemoryEntry` on load. `ensure_memory_entries()` updated to convert and patch in one pass
- Removed: `prompts.py` (300+ lines dead duplicate of `prompt_builders.py`, 6 mypy errors, stale hardcoded seed words ignoring `engine.yaml`)
- `_process_deceased_npcs` → `process_deceased_npcs`: public API, eliminates cross-module underscore import in `game_start.py` and `chapters.py`
- `call_revelation_check`: type hint `dict` → `Revelation`, removed defensive `hasattr`/`.get()` hybrid that masked the actual contract
- `dmg_lookup` alias removed in `mechanics.py` — `damage()` is the function name, use it
- `provider_openai.py`: fragile `hasattr(cfg_extra, "to_dict")` duck typing → explicit `isinstance(_ConfigNode)` check
- `processing.py`: misleading 12-space indentation in for-loop bodies fixed to standard 8-space
- `_STOPWORDS` in `lifecycle.py`: documented why German stopwords are intentional (cross-language description matching for upstream compatibility)
- Ruff: `SIM105` fix in `sidebar.py` (`contextlib.suppress`), `SIM117` added to ignores (NiceGUI UI nesting)
- Elvira invariant checker updated for `MemoryEntry` (supports both dataclass and legacy dict format)
- 17 new tests: 9 `MemoryEntry` (roundtrip, from_dict, legacy compat, debug stripping), 5 correction flow (`_apply_correction_ops`: npc_edit, rename, split, location, status validation), 3 NPC lifecycle (description matching, merge with clock owner update)
- 222 tests total (was 205), ruff clean, mypy clean

## [0.26.0] — 2026-04-04

Typed data models for all mutable state. Module split. Config-driven schemas. Model tests.

- `NpcData` dataclass: 18 typed fields, attribute access everywhere, dict access removed across 20 files
- `ClockData` dataclass: 8 typed fields, attribute access everywhere, dict access removed across 9 files
- `SceneLogEntry` dataclass: 16 typed fields for session log entries, replaces dict literals in turn.py, game_start.py, chapters.py, correction.py
- `NarrationEntry` dataclass: 3 typed fields for narration history entries, replaces dict literals in same files
- `helpers.py` split into `story_state.py`, `prompt_blocks.py`, `xml_utils.py`. helpers.py 469 → 114 lines
- Brain move list and stat names config-driven from `engine.yaml`
- Schema builder helpers eliminate boilerplate (schemas.py 459 → 260 lines)
- 24 model tests (tests/test_models.py)
- Removed: `ensure_npc_memory_fields`, `_try_call_director`, `BRAIN_OUTPUT_SCHEMA` constant, duplicate `_xa`/`_xe`, duplicate `stats:` key
- Upstream backport v0.9.85: roll log shows `11→10(cap)` when action score exceeds 10
- Upstream backport v0.9.86: `compel` STRONG_HIT grants bond+1 only (no disposition shift). `test_bond` STRONG_HIT grants bond+1 and disposition shift
- Upstream backport v0.9.86: `check_npc_agency` ticks NPC-owned threat clocks in addition to scheme, uses `normalize_for_match`
- Upstream backport v0.9.86: scene continuity prompt: same-location bridging sentence, scene endings as emotional suspension
- Upstream backport v0.9.87: WEAK_HIT threat clock ticking — controlled=no tick, risky=50%, desperate=guaranteed. Config: `pacing.weak_hit_clock_tick_chance`
- Upstream backport v0.9.87: Director includes NPCs with empty agenda/instinct regardless of reflection threshold

## [0.25.0] — 2026-04-03

Upstream sync v0.9.84. NPC system hardening. Director race condition fix. Elvira test bot.

- Off-screen death detection via cross-NPC memory voting
- `normalize_for_match()` as single source of truth for NPC name comparison (replaces 20+ `.lower().strip()` calls)
- `absorb_duplicate_npc` with richness scoring — richer NPC wins on merge
- Clock owners updated on NPC rename
- `resolve_about_npc` rejects self-references
- Director: inline await replaces background task (eliminates zombie-reflection loop)
- Story completion back-fill when Director was consistently superseded
- 3-act architect prompt: dual-layer conflict, anti-escalation transitions, perception-shift revelations
- Elvira test bot: headless AI player, 5 play styles, Datasworn character creation, state invariant checks

## [0.24.0] — 2026-04-01

XML injection escaping. NPC rename via correction. Campaign mechanical persistence principle.

- XML escaping across all prompt builders (player input, content boundaries, backstory)
- `PROJECT_ROOT` centralizes project root path
- NPC rename and deceased status via correction system
- Blueprint null-stripping on load
- Narrator: scene continuity, emotional carry-through, thematic thread surfacing

## [0.23.0] — 2026-04-01

Datasworn integration. Setting-driven character creation. Vocabulary control.

- Datasworn loader for Classic, Delve, Starforged, Sundered Isles
- Setting packages with vocabulary substitutions, genre constraints, oracle paths
- Deterministic character creation (no AI call until opening scene)
- `narrative_direction_block()` derives writing instructions from game state via engine.yaml
- Validator reads genre constraints from active setting package

## [0.22.0] — 2026-03-31

Constraint enforcement overhaul.

- `validate_and_retry()`: up to 2 retries with re-validation after each
- `validate_architect()`: genre fidelity check on story blueprints
- 77 engine tests
- Validator expanded: resolution pacing (NPCs answer only what's asked), speech handling, player agency

## [0.21.0] — 2026-03-30

GameState decomposition. Save format break.

- GameState split into typed sub-objects: Resources, WorldState, NarrativeState, CampaignState, PlayerPreferences
- Resource mutation via methods with clamping and logging
- Symmetric `snapshot()`/`restore()` replaces manual field-by-field copy
- Nested `to_dict()`/`from_dict()` replaces SAVE_FIELDS list

## [0.20.0] — 2026-03-30

Upstream sync v0.9.71. Constraint validator. Open model prompt hardening.

- Constraint validator: result integrity, genre fidelity, player agency, resolution pacing, speech handling
- Temperature tuning per AI role for open model compliance
- Narrator prompt hardened: genre-as-physics, information dosing, backstory canon, pure prose
- emotions.yaml restored to 9-tier importance (131 entries)
- NAME_TITLES expanded to 227 entries for fantasy/sci-fi/multilingual NPC dedup

## [0.19.0] — 2026-03-29

Config-driven engine.

- engine.yaml: all damage tables, resource caps, NPC limits, chaos, pacing, narrative direction
- emotions.yaml: importance scoring, keyword boosts, DE→EN normalization, dispositions
- Zero hardcoded game numbers in Python. 82 config values, 82 read sites verified.

## [0.18.0] — 2026-03-28

i18n extraction.

- UI strings extracted to strings.yaml (372 keys). Add languages via strings_{code}.yaml.
- German removed from code. English-only UI, YAML-driven.

## [0.17.0–0.17.1] — 2026-03-28

Upstream UI sync (v0.9.49–v0.9.63). Cleanup.

- CSS variables, Google Fonts, Design Mode effects, sidebar rewrite, help rewrite
- turn.py: `_finalize_scene` eliminates dialog/action duplication
- Public API cleanup: zero cross-module underscore imports

## [0.16.0] — 2026-03-28

Upstream sync v0.9.66.

- Chapter transition NPC ID collision fix
- Revelation verification via `call_revelation_check`
- Fired clock cleanup and tracking

## [0.15.0] — 2026-03-23

AI call audit.

- Metadata extractor receives mechanical ground truth from Brain
- Kid-friendly and content boundary blocks on all AI calls
- Raw stat numbers removed from narrator prompts

## [0.14.0] — 2026-03-22

KISS cleanup. 13.4K → 11.2K lines.

- Removed voice I/O and 5 dependencies
- Emotion taxonomy, NPC title list, disposition map trimmed
- Dead code removed across engine

## [0.13.0] — 2026-03-22

Upstream sync v0.9.61. GLM 4.7.

- Fired clocks become history. Location fuzzy matching. Post-epilogue Director trigger.
- GLM 4.7 as default. Lean prompt set (1644 words).

## [0.12.0–0.12.3]

Provider tuning, sampling params, multi-model testing.

## [0.11.0]

YAML configuration. Multi-instance support.

## [0.10.0]

Modular refactor from upstream v0.9.44. Monolithic engine.py (6400 lines) → packages.
