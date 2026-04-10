# Straightjacket — Roadmap v6

Session context for Claude. Read this alongside ARCHITECTURE.md, the codebase, and `docs/narrative_rpg_engine_v2_4.pdf` (the design document). Code standards are in the system prompt and pyproject.toml. For Mythic GME 2e and Adventure Crafter implementation details (steps 8-10), read the supplementary mythic_implementation_reference.md provided as session context.

Changes from v5: Steps 3.5 and 3.6 completed. Brain migration (was 3.6.4) and Director migration (was 3.6.5) moved to step 7 — they require tools that produce information the prompt cannot (oracle rolls, fate questions). Without those tools, migration adds complexity without value. Brain keeps prompt-based json_schema output for classification; tool calling activates when oracle roller and fate system provide the first real tools. Tool calling probe evaluated Qwen 3 235B (87% pass) and GLM 4.7 (93% pass) — both viable, Qwen preferred for speed/cost. Steps 4–6 completed in v0.39.0. Current state updated.

## Vision

Solo play for any Ironsworn-family game (Classic, Starforged, Delve, Sundered Isles) with full mechanical fidelity. Mythic GME 2e handles GM-less decision making. AI writes prose within engine-dictated constraints. The player types what their character does. The engine handles everything else.

## Current state (v0.39.0)

Steps 0–6 complete. Engine: ~7K lines Python. 467 tests. Qwen 3 235B on Cerebras.

Done: character creation with Datasworn integration and Mythic seeding. Brain slimmed to 7 output fields. Metadata extractor reduced to NPC detection only. Engine-computed position, effect, time progression, pacing, act transitions, memory emotions, narrative direction. Hybrid rule-based + LLM validator. Snapshot/restore. Provider abstraction. Prompt stripping on retry. Mythic GME 2e and Adventure Crafter data extracted to `data/mythic_gme_2e.json` and `data/adventure_crafter.json`. Data download script (`data/data.py`) handles both Datasworn and Word Mill sources. SQLite read model with full sync and query layer. Tool calling infrastructure with registry, handler, iterative loop, and built-in query tools. Tool calling probe for model evaluation. Engine-dictated consequence sentences from templates. NPC behavioral stance from engine.yaml matrix (60 entries). Information gating (0–4) per NPC per scene.

Next: step 7.

## Licensing

Ironsworn / Starforged / Delve / Sundered Isles: text licensed CC BY-NC-SA 4.0 by Tomkin Press. Covers rulebooks, moves, oracles, assets, themes, domains, handouts. All Datasworn content in `data/` is covered.

Attribution: "This work is based on Ironsworn, Ironsworn: Starforged, Ironsworn: Delve, and Sundered Isles, created by Shawn Tomkin, and licensed for our use under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license."

Mythic GME 2e: text licensed CC BY-NC 4.0 by Word Mill Games / Tana Pigeon. Covers the complete fate chart, meaning tables, scene structure rules, thread tracking, all 2e mechanics. Use the actual Mythic system — no need for independent reimplementation.

Attribution: "This work is based on Mythic Game Master Emulator Second Edition by Tana Pigeon, published by Word Mill Games, and licensed for our use under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. Find out more at www.wordmillgames.com."

The Adventure Crafter: text licensed CC BY-NC 4.0 by Word Mill Games / Tana Pigeon. Covers plot points, turning points, character crafting, theme system, plotline and character list mechanics.

Attribution: "This work is based on The Adventure Crafter by Tana Pigeon, published by Word Mill Games, and licensed for our use under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. Find out more at www.wordmillgames.com."

Straightjacket is non-commercial and will remain so.

## Principles

These are stable and apply to all steps. Deviating requires explicit justification.

**Engine decides, AI tells.** Every value derivable from game state is computed by the engine. The AI receives results, not choices. When in doubt, move it to the engine.

**Minimize AI decision surface.** Five AI decision points exist (see ARCHITECTURE.md). Everything else is engine-deterministic. Each new step must evaluate whether any AI output field is derivable from game state before adding it to a schema.

**Config-driven.** Game rules, damage tables, move categories, NPC limits, stance matrices, fate charts — all in YAML. Adding a move or changing a threshold means editing config, not code.

**Tool calling over prompt injection where appropriate.** Brain and Director use tool calling to query game state and invoke engine subsystems. The engine exposes read-only query tools and action tools (oracle rolls, fate questions). Tools return structured results; the AI cannot modify state directly. Narrator stays prompt injection only — it receives a complete prompt and writes prose. Metadata extractor stays prompt injection only — pure transformation. Tool calling activates per role when that role gains tools that produce information unavailable via prompt (oracle roller at step 7, fate questions at step 8).

**More calls, less data per call.** Focused AI tasks with minimal context. The engine assembles results.

**Engine-dictated consequences.** Default for all mechanical outcomes. Prompt-constraints only for low-stakes flavor.

**Player sees only story and choices.** No stats, no dice, no system references in player-facing output. Mechanical state is translated to narrative language. Spelerskeuzes worden narratief gepresenteerd: "Wil je je eed aan Kira voltooien?" niet "Fulfill Your Vow op connection track Kira?" This applies to all future interaction patterns — momentum burn, vow decisions, scene challenges, move triggers. Screen reader accessible by design.

**World moves independently.** The world has conflicts and momentum that don't revolve around the player. Events reach the player as news about things that don't concern them. Factions act, NPCs pursue goals, clocks tick — whether the player is involved or not. Mythic's "remote event" focus category is one mechanism; autonomous clock ticks and faction turns are others.

**Structured consequence verification.** The validator checks narrator output against known prompt data without semantic AI calls. Consequence sentences injected via tags produce expected keywords. NPC stance constraints produce behavioral markers. The engine knows what MUST appear; the validator checks if it does.

**Prompt token budget.** Narrator prompt >8K tokens: investigate. Compression priority (lowest value shed first): recent_events, campaign_history, lore_figures, known_npcs, activated_npc secondary context, director_guidance detail. Never shed: core prompt, consequence tags, target_npc block, stance tags.

**Setting-agnostic mechanics.** Moves, assets, oracles, themes, domains are data. All four Ironsworn-family settings share one engine. Adding a setting means adding data, not code.

**Database as read model.** GameState dataclasses remain the write model — all mutations go through Python. SQLite is the read model and query backend. The prompt builder and tool handlers query the database. persistence.py syncs GameState → database after each turn. Snapshot/restore operates on GameState as before; the database is rebuilt from GameState on restore.

**AI role boundaries.** Narrator: prompt injection only, pure prose, no tools, no decisions. Brain: prompt-based classification (json_schema) now; gains tool calling at step 7 when oracle roller provides the first tool that delivers information unavailable via prompt. Director: prompt injection now; gains tool calling when Brain migration proves stable. Metadata extractor: prompt injection, NPC detection only (5 fields). Validator: hybrid rule-based + LLM. Rule engine grows from test data, LLM handles semantic ambiguity only.

## Dependencies and parallelism

Steps 4–6 complete. Step 7 depends on 3.6 (oracle roller is a Brain tool) and includes Brain/Director migration to tool calling. After step 7, three parallel tracks:

- **Track A (Mythic GME)**: steps 8–10. Fate, scene structure, meaning tables. Depends on step 7.
- **Track B (Starforged mechanics)**: steps 11–14. Moves, progress tracks, impacts, assets. Depends on step 7 + step 2.
- **Track C (NPC agency)**: step 18. Depends on step 5 + step 7. Uses engine.yaml templates initially; meaning tables (step 10) deepen variety when Track A completes.

After tracks complete:
- Site exploration (step 16) depends on steps 11–12.
- Expeditions (step 15.5) depend on steps 11–12 + step 9.
- Factions (step 19) depend on step 18 + step 10.
- DramaSystem (step 19.5) depends on step 19.
- Generators (steps 20–21) depend on step 7 + step 18.
- Sundered Isles specifics (step 22): ship mechanics require step 14, crew requires step 22.1, cursed dice require step 11. Oracle/exploration config requires step 7 + site exploration model.
- Campaign hardening (step 23) depends on steps 12–14.

When blocked on one track, work another.

---

## Phase 2A — Reduce AI surface, build infrastructure

### Steps 0–3 ✓ (v0.37.0)

Character creation, Brain slimming, metadata extractor split. See CHANGELOG.md for details.

### Step 3.5 ✓ (v0.38.0) — Database layer

SQLite as read model and query backend. GameState dataclasses remain the write model.

**3.5.1** ✓ Schema. 8 tables: `npcs`, `memories`, `threads`, `characters_list`, `clocks`, `scene_log`, `narration_history`, `vow_tracks`. 11 indexes. In `engine/db/schema.sql`.

**3.5.2** ✓ Sync layer. `db.sync(game)` full replace after every turn, creation, correction, burn, new chapter, load, restore.

**3.5.3** ✓ Query functions. `query_npcs`, `query_memories`, `query_threads`, `query_clocks` with optional filters. Return dataclass instances.

**3.5.4** ✓ Snapshot/restore. `GameState.restore()` calls `reset_db()` + `sync()`.

**3.5.5** ✓ Save/load. `load_game()` rebuilds database. JSON saves unchanged.

### Step 3.6 ✓ (v0.38.0) — Tool calling infrastructure

Framework for exposing engine subsystems as callable tools to Brain and Director.

**3.6.1** ✓ Tool registry. `engine/tools/registry.py`. `@register("brain", "director")` decorator. Type hints → OpenAI function calling schemas. Per-role tool subsets via `get_tools(role)`.

**3.6.2** ✓ Tool handler. `engine/tools/handler.py`. `execute_tool_call()` dispatches to registered function. `run_tool_loop()` iterative loop with configurable round limit.

**3.6.3** ✓ Provider integration. AIProvider protocol already supports tools parameter. Iterative loop in handler.py. No protocol extension needed.

**3.6.4** ✓ Built-in query tools. `tools/builtins.py`: `query_npc` (brain+director), `query_active_threads` (director), `query_active_clocks` (director), `query_npc_list` (brain). Read-only.

**3.6.5** ✓ Tool calling probe. `tests/tool_calling_probe.py`. 15 test cases, multi-model comparison. Qwen 3 235B: 87% pass, 414ms avg. GLM 4.7: 93% pass, 747ms avg. Both above viability threshold when accounting for test case design (1 case too strict, 1 edge case resolved by iterative loop).

### Step 4 ✓ (v0.39.0) — Engine-dictated consequences

**4.1** ✓ Consequence sentence generator. `consequence_templates` in engine.yaml (18 keys, multiple variants). `generate_consequence_sentences()` in mechanics.py.

**4.2** ✓ `<consequence>` tags in narrator prompt (required keyword arg). Narrator system prompt CONSEQUENCES instruction. All 4 call sites (turn, correction reroll, correction state_error, momentum burn) generate and pass sentences.

**4.3** ✓ Validator keyword matching. `check_consequence_keywords()` in rule_validator.py, integrated into `validate_narration` and `validate_and_retry` chain.

**4.4** ✓ `pay_the_price` table in engine.yaml. Full Starforged Pay the Price move integration at step 11.

### Step 5 ✓ (v0.39.0) — NPC behavioral stance

**5.1** ✓ Stance resolver. `resolve_npc_stance()` in mechanics.py. `NpcStance` dataclass. Three-level lookup: disposition → bond_range → move_category.

**5.2** ✓ Stance matrix in engine.yaml. 5 dispositions × 3 bond ranges × 4 move categories = 60 entries. Each: stance label + concrete behavioral constraint.

**5.3** ✓ `_npc_block` and `_activated_npcs_block` show stance+constraint instead of raw disposition/bond. move_category threaded from dialog (social) and action (via `_move_category`).

### Step 6 ✓ (v0.39.0) — Proactive information gating

**6.1** ✓ Gate computed from: scenes since introduction, gather_information successes (`gather_count` on NpcData), bond level, stance cap. `compute_npc_gate()` in mechanics.py. Config in engine.yaml `information_gate` section.

**6.2** ✓ Prompt builder `_npc_block` filters by gate level. Gate 0: name + description. Gate 1: + stance + constraint. Gate 2: + agenda + recent memories. Gate 3: + instinct + arc + all memories. Gate 4: + secrets.

**6.3** ✓ Gate level logged per NPC per prompt build.

### Step 7 — Oracle roller and Brain/Director tool migration ← NEXT

Oracle roller as Brain tool. First real consumer of tool calling infrastructure. Brain and Director migrate from prompt injection to tool calling alongside — the oracle roller is the tool that justifies the migration.

**7.1** Datasworn oracle roller. `roll_oracle(table_path)` as registered tool. Rolls any oracle table by ID from `data/*.json`. Returns structured result. All oracle data loaded at startup via `datasworn/loader.py`.

**7.2** Brain migration. Brain gains tools alongside json_schema classification. json_schema and tools are mutually exclusive per call, so: Brain first calls with tools available (oracle lookup, fate question, NPC query). After tool loop resolves, Brain produces final classification as JSON in text output. Falls back to current prompt-based json_schema call if tool calling fails. Prompt rewrite in prompts.yaml.

**7.3** Ask the Oracle move integration. Brain identifies the move, calls `roll_oracle` tool, result injected into narrator prompt.

**7.4** Director migration. Director gains tools for NPC queries, thread queries, clock status. Replaces full-context prompt injection with selective tool-based inspection. Prompt rewrite in prompts.yaml.

**7.5** Prompt builder migration (deferred 3.5.4). Replace in-memory iteration in `prompt_builders.py` and `npc/activation.py` with database queries. Same XML output, different data source. Query patterns designed alongside tool handler queries to avoid duplication.

**7.6** Setting-specific oracles loaded per active setting.

**7.7** Elvira baseline comparison: run before and after migration, compare validator pass rates, narration quality, and latency.

---

## Phase 2B — Mythic GME (CC BY-NC 4.0 implementation)

Implement the Mythic GME 2e system using the actual rules under license. Own engine integration, Mythic's tables and mechanics.

### Step 8 — Fate system

All fate data in `data/mythic_gme_2e.json`. Full procedure details in mythic_implementation_reference.md sections 1.1-1.6.

**8.1** Fate chart. Mythic 2e's 9 likelihood levels × chaos factor matrix. Results: yes, no, exceptional yes, exceptional no. Data: `mythic_gme_2e.json` → `fate_chart`.

**8.2** Doubles-triggered random events. On fate question d100 roll, if doublet and digit ≤ chaos factor, random event fires. Same trigger rule for fate check 2d10 method.

**8.3** Fate check. Mythic 2e's simplified 2d10 + chaos modifier alternative for quick yes/no. Data: `mythic_gme_2e.json` → `fate_check`.

**8.4** Likelihood resolver. Engine determines likelihood from context: NPC disposition, bond, chaos, active threats. Lookup in engine.yaml.

**8.5** Brain integration. `fate_question(question, context_hint)` as Brain tool. Engine resolves likelihood, rolls chart, checks doubles, returns result. Brain calls this when player asks yes/no questions or when the fiction needs an answer the engine can't determine mechanically.

**8.6** Detail check chains. Refinement chains: after initial fate question, follow-ups narrow the result. Each question is a separate fate roll with likelihood derived from prior answers. Engine tracks chain context per scene.

**8.7** Fate as RPG rules. When fate questions replace mechanical checks (skill rolls, saves), use chaos factor 5 regardless of actual value. Treat exceptional results as regular if the replaced rule has no degrees of success. Data: `mythic_gme_2e.json` → `fate_as_rpg_rules`.

**8.8** NPC statistics via fate. When determining NPC mechanical stats, fate question with chaos factor 5. Yes = expected value, Exceptional Yes = +25%, No = -25%, Exceptional No = -50%. Data: `mythic_gme_2e.json` → `npc_statistics`.

### Step 9 — Scene structure

Full procedure details in mythic_implementation_reference.md section 3. Replaces current check_chaos_interrupt in mechanics.py. Crisis mode becomes redundant after this step.

**9.1** Scene state machine. Setup → keyed scene check → chaos check → play → end → bookkeeping. State in GameState. Chaos check happens BEFORE brain call.

**9.2** Expected scene derived from: player input (primary), last scene summary, active threads (highest priority), Director guidance, story arc phase.

**9.3** Chaos check. d10 vs chaos factor. >CF = expected. ≤CF odd = altered. ≤CF even = interrupt. Replaces current `check_chaos_interrupt`.

**9.4** Altered scenes via Scene Adjustment Table (d10). 7 adjustment types from `mythic_gme_2e.json` → `scene_adjustment`. Injected as `<altered_scene>` tag.

**9.5** Interrupt scenes. Expected scene discarded, replaced by random event. Injected as `<interrupt_scene>` tag.

**9.6** Scene-end bookkeeping. Update lists (add/remove threads and NPCs, weight adjustments). Chaos factor adjustment derived from roll results: STRONG_HIT = -1, MISS = +1, WEAK_HIT = no change. Alternative chaos methods configurable.

### Step 10 — Meaning tables and random events

Full procedure details in mythic_implementation_reference.md sections 2, 4, 5, 6.

**10.1** Event Focus Table. 12 categories, d100. Data: `mythic_gme_2e.json` → `event_focus`. Engine selects from active thread/character lists when focus requires it.

**10.2** Meaning tables (Actions, Descriptions). Two d100 rolls → word pair. Data: `mythic_gme_2e.json` → `meaning_tables`.

**10.3** Random event pipeline. Focus → target selection → meaning roll → structured event description. `<random_event>` tag in narrator prompt.

**10.4** Integration with scene structure (step 9). Interrupt scenes use full random event pipeline. Altered scenes use Scene Adjustment Table.

**10.5** Themed element tables. 45 d100 tables from `mythic_elements.json`. Table selection logic in engine.yaml mapping (event_focus, scene_type, location_type) → table.

**10.6** Thread progress tracks. Optional system to drive focus thread toward resolution. 10/15/20 point tracks with phase boundaries and forced Flashpoints.

**10.7** Discovery checks. Biased fate question (minimum 50/50) for making progress when adventure stalls.

**10.8** Keyed scenes. Pre-defined triggers that override normal scene testing. Evaluated before chaos check.

**10.9** Scene-end list maintenance. Automated weight adjustments, consolidation at 25 entries.

**10.10** NPC behavior. Fate question for NPC actions outside player interaction. Engine computes expected action from AIMS + stance, asks fate question, interprets via NPC Behavior Table. Data: `mythic_gme_2e.json` → `npc_behavior`. Random Event on the fate roll = additional NPC action from meaning table.

**10.11** Chaos factor variants. Four modes: standard, mid-chaos, low-chaos, no-chaos. Each with own fate chart and fate check modifiers. Data: `mythic_gme_2e.json` → `chaos_variants`. Config switch in engine.yaml.

**10.12** Adventure Crafter integration. Plot points and turning points as alternative/supplement to story blueprint. Data: `data/adventure_crafter.json` → `plot_points` (186 entries, 5 themes), `meta_plot_points`, `characters_list_template`, `plotlines_list_template`, `turning_point_rules`. Character crafting: `character_special_trait`, `character_identity`, `character_descriptors`. Theme priority: `plot_point_theme_priority`, `random_themes`. Full procedure in reference doc section 6 and 9.

**10.13** Player vs PC knowledge. Strategies for handling player/PC knowledge gap. Data: `mythic_gme_2e.json` → `player_vs_pc_knowledge`. Default: Test-Ask-Real (engine-known info requires fate question to become PC-known).

---

## Phase 2C — Starforged mechanical completeness

### Step 11 — Move system

**11.1** Move loader. Map Brain move classification → Datasworn move ID via engine.yaml lookup. Engine reads move outcome text from Datasworn, passes to narrator as context.

**11.2** Move data model. Trigger conditions, stat, outcomes as structured data per move. Engine resolves mechanical outcome. Different moves have different consequence logic — not everything routes through generic face_danger.

**11.3** All moves from Datasworn. Starforged: 56 moves across 12 categories (see `data/starforged.json` → `moves`). Classic: 35 moves (see `data/classic.json`). Delve: 13 moves (see `data/delve.json`). Sundered Isles: 8 moves that override or extend Starforged (see `data/sundered_isles.json`). Engine loads correct set per setting_id. Move definitions are data, not code.

**11.4** Progress roll infrastructure. Some moves are progress rolls (Fulfill Your Vow, Take Decisive Action, Forge a Bond, Finish an Expedition, Locate Your Objective). Roll filled_boxes × 4 vs 2d10 instead of 2d6+stat. Engine detects progress roll moves and routes accordingly.

### Step 12 — Progress tracks

**12.1** `ProgressTrack` exists (v0.36.0). Remaining: `progress_roll()` method, Brain triggers "mark progress" on appropriate hits, full move integration.

**12.2** Track types: vows, connections, expeditions, combat (scene-length), delve sites, scene challenges, custom.

**12.3** Connections as progress tracks. Replace integer bond with ranked progress track per NPC connection. Make a Connection creates track. Develop Your Relationship marks progress. Forge a Bond is progress roll. Changes NpcData — bond becomes a progress track.

**12.4** Vow tracking. Swear an Iron Vow creates vow track + ThreadEntry. Reach a Milestone marks progress. Fulfill Your Vow is progress roll. Forsake Your Vow clears with consequences.

**12.5** Scene challenges as track type. Begin the Scene creates a scene challenge track. Face Danger / Secure an Advantage mark progress. Finish the Scene is progress roll. No separate infrastructure — it's a ProgressTrack with specific move routing.

**12.6** All tracks persist across chapters and save/load.

### Step 13 — Impacts and legacy tracks

**13.1** 10 impacts (wounded, shaken, etc.), each reduces max_momentum by 1. Some block moves. Data-driven from engine.yaml per setting.

**13.2** Legacy tracks: quests/bonds/discoveries → XP. Campaign persistent.

**13.3** XP and Advance. Spend XP on asset abilities or new assets. Costs in engine.yaml.

**13.4** Continue a Legacy. Character retirement/death. Mechanical inheritance from legacy track progress rolls.

### Step 14 — Assets

**14.1** Modifier pipeline. Types: stat_bonus, reroll, extra_effect, condition_track. Stacking rules, evaluation order, snapshot/restore, momentum burn timing. Prove with 5–10 representative assets.

Companion health tracks: companion assets have dedicated health track (separate from NPC bond). Companions are NOT NpcData — they are assets with condition_track. No NPC memory/activation/disposition.

Vehicle condition tracks: Command Vehicle and Ship assets have condition track. Withstand Damage is suffer move on this track.

**14.2** Iterative rollout. 87 Starforged assets in `data/starforged.json` → `assets` (6 categories: command_vehicle, companion, deed, module, path, support_vehicle). Roll out in batches. Classic: 78 assets. Sundered Isles: 60 assets.

**14.3** Setting-specific assets loaded per setting_id.

---

## Phase 2D — Site exploration (unified model)

One generic site exploration model. Delve sites, Starforged derelicts/vaults/themed locations, and Sundered Isles caves/ruins/overland are all instances with different oracle table sources. Build the model once, prove with Delve (most complex: denizen matrix), then others are data configuration.

### Step 15.5 — Expeditions

Starforged's travel/exploration loop. Waypoint-based with progress track.

**15.5.1** Expedition data model. Destination, rank, progress track, waypoints, dangers. Reuses ProgressTrack.

**15.5.2** Expedition moves. Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish an Expedition, Set a Course. Routing: when expedition active, exploration actions go through expedition moves.

**15.5.3** Waypoint generation from Datasworn exploration oracles per setting.

**15.5.4** Scene structure integration. Each waypoint is a scene boundary — chaos check at each waypoint.

### Step 16 — Site exploration

**16.1** Generalized site data model. Name, objective, theme, domain, rank, progress track, denizen matrix (Delve), discovered features, active dangers. One dataclass covering Delve sites, Starforged derelicts/vaults, Sundered Isles caves/ruins. Different oracle table sources per setting/type.

**16.2** Theme + domain system. Themes and domains are in Datasworn: Delve has 8 themes × 10 domains (`data/delve.json` → `site_themes`, `site_domains`). Each provides features table (d100) and dangers table (d100). Combinable.

**16.3** Denizen matrix (Delve). Per-site d100 table from theme + domain. Common/uncommon/rare/unforeseen ranges.

**16.4** Delve moves from `data/delve.json` → `moves`: Discover a Site, Delve the Depths, Find an Opportunity, Reveal a Danger, Locate Your Objective, Escape the Depths.

**16.5** Starforged exploration subsystems as site configurations. Derelicts: 8 zones with oracle tables in Datasworn. Precursor vaults: interior + sanctum layers. Location themes: 8 themes overlaying any location. All use the same site model with different oracle sources.

**16.6** Sundered Isles exploration as site configurations. Caves, ruins, overland — each with own oracle tables in `data/sundered_isles.json` → `oracles`. Same model, different tables.

### Step 17 — Threats and menace

**17.1** Threat data model. Category (Delve's 9 types), menace track (progress-style), associated vow.

**17.2** Menace advancement. On misses and triggers, engine ticks menace. Menace competes with vow progress.

**17.3** Threat resolution. Menace fills before vow completes → Forsake Your Vow forced. Vow fulfilled while menace high → bonus XP.

**17.4** Integration with random events. Threats as targets in event focus table. "Threat advance" event ticks menace on most relevant active threat.

---

## Phase 2E — NPC agency, factions, and emotional dynamics

### Step 18 — NPC moves and goal-clocks

Track C. Depends on step 5 + step 7.

**18.1** Goal-clock per NPC. Segments, tick triggers, fill consequence. In NpcData, persisted. Database indexed for trigger evaluation queries.

**18.2** Tick evaluation. Engine checks triggers after state mutations: bond_below_N, health_below_N, scene_count threshold, faction event. Deterministic. Database queries for cross-NPC trigger conditions.

**18.3** Move execution. Filled clock → engine selects move from NPC's move list. Cooldown. Result: `<npc_action>` tag with predetermined sentence. Sentence via meaning tables (step 10.3 when available, engine.yaml templates as fallback).

**18.4** Move generation. Director generates AIMS + move set on NPC promotion to recurring. Director uses tools to query existing NPC relationships and faction state for context. One-time AI call, then deterministic.

### Step 19 — Factions

**19.1** Faction data model. Name, goal, tenets, members, scheme_clock, resources, inter-faction relationships, player_reputation. Generation uses Datasworn faction oracles (available in `data/starforged.json` → `oracles`). Faction table in database with relationship queries.

**19.2** Three-zone reputation resolver. Extreme overrides personal bond. Moderate thresholds in engine.yaml. Extends step 5 stance resolver.

**19.3** Faction turns. Every N scenes, tick scheme_clocks. Filled → faction acts via goal + meaning table. `<faction_event>` tag.

**19.4** NPC loyalty. `loyalty_score: float` on NpcData. Shifts per interaction. When faction agenda conflicts personal agenda, engine compares loyalty_score against stakes-derived threshold. Result fed to narrator as stance.

### Step 19.5 — Emotional dynamics (DramaSystem concepts)

Third relational layer beyond memory (what happened) and agency (what they want): emotional dynamics (what they need from each other). Requires stable NPC moves (step 18) and faction loyalty (step 19) as foundation.

**19.5.1** NPC-to-player emotional requests. NPCs ask for things that aren't mechanical — acknowledgment, trust, honesty, loyalty. Engine generates requests from NPC state (agenda frustration, bond level, recent events). Request injected into narrator prompt as behavioral constraint.

**19.5.2** Refusals and concessions. Player actions interpreted as granting or denying requests. Engine tracks: what was asked, what was denied, what was given. Affects bond, stance, and loyalty_score.

**19.5.3** NPC-to-NPC dynamics. NPCs make requests of each other. Engine resolves based on relationship and loyalty. Creates triangles: NPC A asks player for help against NPC B, who is the player's ally.

**19.5.4** NpcData fields: `emotional_requests: list`, `concessions: int`, `refusals: int`. Datamodel already prepared in step 19 — this step activates the runtime logic.

---

## Phase 2F — Generators and world state

### Step 20 — NPC generation

**20.1** Tier 1 (throwaway): oracle-rolled demeanor + name + disposition. Datasworn tables via oracle tool.

**20.2** Tier 2 (recurring): full AIMS + moves + goal-clock. AI call for AIMS, then deterministic. Distinct from 18.4 (this creates new NPC; 18.4 adds moves to existing).

**20.3** Promotion trigger: 3 interactions in 5 scenes. Engine tracks via database query.

### Step 21 — Location, encounter, thread generators

Generators are explicitly hybrid: oracle tables produce structure, AI writes concrete description within that structure. This is the design document's generator model — structure decides, AI narrates.

**21.1** Location generator. Datasworn oracles → structured location with properties. AI call to produce contextual description from the structure.

**21.2** Encounter generator. Weighted by location + threats + chaos. Table lookup for structure, AI for description.

**21.3** Thread prioritization. Conditional: implement only if narrator ignores relevant threads despite Director guidance. If needed: utility scoring per constraint, top 2 enter narrator prompt. Rule-based, no AI.

### Step 22 — Sundered Isles specifics

Three new subsystems with explicit dependencies. Everything else is data configuration on existing infrastructure.

**22.1** Ship mechanics. Command vehicle with modules. Ship condition track. Repair. Ship assets from `data/sundered_isles.json` → `assets`. **Requires step 14** (asset/condition_track pipeline).

**22.2** Crew mechanics. Crew as resource with morale. Morale thresholds, mutiny triggers. Data-driven from engine.yaml. **Requires step 22.1** (ship must exist).

**22.3** Cursed dice. "Cursed" impact modifies die rolls. Mechanical modifier in roll pipeline. **Requires step 11** (roll pipeline).

**22.4** Data configuration (no new subsystems): naval encounters (combat moves + ship assets), treasure (oracle tables), SI oracles (16 categories in `data/sundered_isles.json` → `oracles`), SI exploration (site model + SI oracle tables). All require only step 7 + existing infrastructure.

---

## Phase 2G — Campaign hardening

### Step 23 — Cross-chapter persistence

**23.1** Chapter summary receives full mechanical state. All tracks, factions, threads, connections persist.

**23.2** Validator rejects contradictions between chapter summary and game state.

**23.3** Continue a Legacy for character succession.

---

## Beyond Phase 2

Optional, can be done by others. The engine is complete when step 23 is done.

Meta-commands: player-facing queries ("who do I know?", "what have I sworn?", "where have I been?") returning narrative-language summaries. Useful but not core.

Custom setting tooling: CLI validator, setting author guide. Requires knowing what the minimum setting package is — resolve after four Ironsworn-family settings prove the abstraction.

Localization guide: document what to translate (strings.yaml, engine.yaml templates) and what can't be translated without upstream work (Datasworn content is English). Low effort, low priority.

## UI changes

**Status display.** Current `showStatus()` sends raw stats (edge, heart, etc.), resource numbers, NPC disposition/bond values. Replace with narrative translations. `status_context_block` in prompt_blocks.py already maps resources to narrative descriptions — bring this same mapping to the serializer and client. NPC display: "Kira wantrouwt je" not "distrustful B1/4". Clocks: keep visual bar, translate labels. Stats (edge, heart, etc.): evaluate whether to show at all — the design document says "no stats." If players want orientation, translate to character descriptors.
