# Straightjacket — Roadmap v12

Session context for Claude. Read this alongside ARCHITECTURE.md, the codebase, and `docs/narrative_rpg_engine_v2_4.pdf` (the design document). Code standards are in the system prompt and pyproject.toml.

This document is self-contained. All Mythic GME 2e and Adventure Crafter procedures are inline at the step where they are needed. No separate reference documents required.

This roadmap is linear. Steps are numbered and executed in order. Each step is scoped to one Claude session. No parallel tracks. Each step builds on what came before.

Steps 0–6 from earlier roadmap versions are complete (see CHANGELOG.md). Steps 1–7 of roadmap v10 are complete.

Source material: Mythic Game Master Emulator Second Edition by Tana Pigeon (CC BY-NC 4.0). The Adventure Crafter by Tana Pigeon (CC BY-NC 4.0). Data files: `data/mythic_gme_2e.json`, `data/adventure_crafter.json`. Themed element tables when extracted: `data/mythic_elements.json`.

## Vision

Solo play for any Ironsworn-family game (Classic, Starforged, Delve, Sundered Isles) with full mechanical fidelity. Mythic GME 2e handles GM-less decision making. Adventure Crafter as alternative/supplemental event generator. AI writes prose within engine-dictated constraints. The player types what their character does. The engine handles everything else.

## Current state (v0.45.1)

Steps 1–7 complete. Code audit complete (v0.45.1): `vow_tracks` renamed to `progress_tracks`, `_ConfigNode` replaced with typed `EngineSettings` dataclasses for engine.yaml, turn pipeline dialog/oracle paths deduplicated, test backoff sleeps eliminated (14s from 35s). Engine: ~15K lines Python. 665 tests. GLM-4.7 on Cerebras.

Next: step 8.

## Licensing

Ironsworn / Starforged / Delve / Sundered Isles: text licensed CC BY-NC-SA 4.0 by Tomkin Press. Covers rulebooks, moves, oracles, assets, themes, domains, handouts. All Datasworn content in `data/` is covered.

Attribution: "This work is based on Ironsworn, Ironsworn: Starforged, Ironsworn: Delve, and Sundered Isles, created by Shawn Tomkin, and licensed for our use under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license."

Mythic GME 2e: text licensed CC BY-NC 4.0 by Word Mill Games / Tana Pigeon. Covers the complete fate chart, meaning tables, scene structure rules, thread tracking, all 2e mechanics.

Attribution: "This work is based on Mythic Game Master Emulator Second Edition by Tana Pigeon, published by Word Mill Games, and licensed for our use under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. Find out more at www.wordmillgames.com."

The Adventure Crafter: text licensed CC BY-NC 4.0 by Word Mill Games / Tana Pigeon. Covers plot points, turning points, character crafting, theme system, plotline and character list mechanics.

Attribution: "This work is based on The Adventure Crafter by Tana Pigeon, published by Word Mill Games, and licensed for our use under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. Find out more at www.wordmillgames.com."

Straightjacket is non-commercial and will remain so.

## Principles

These are stable and apply to all steps. Deviating requires explicit justification.

**Engine decides, AI tells.** Every value derivable from game state is computed by the engine. The AI receives results, not choices. When in doubt, move it to the engine.

**Minimize AI decision surface.** Each new step must evaluate whether any AI output field is derivable from game state before adding it to a schema.

**Config-driven.** Game rules, damage tables, move categories, NPC limits, stance matrices, fate charts — all in YAML/JSON. Adding a move or changing a threshold means editing config, not code.

**Tool calling over prompt injection where appropriate.** Brain and Director use tool calling to query game state and invoke engine subsystems. Tools return structured results; the AI cannot modify state directly. Narrator and metadata extractor stay prompt injection only.

**More calls, less data per call.** Focused AI tasks with minimal context. The engine assembles results.

**Engine-dictated consequences.** Default for all mechanical outcomes. Prompt-constraints only for low-stakes flavor.

**Player sees only story and choices.** No stats, no dice, no system references in player-facing output. Screen reader accessible by design.

**State communication: on-demand over ambient.** The player queries mechanical state via `##` commands. The engine answers directly with narrative translations — no AI call needed. The narrator receives state *changes* (consequence tags, stance shifts) but not standing state. Every step that introduces new mechanical state must specify both the status template (strings.yaml) and which changes warrant consequence tags.

**Conditionele implementatie.** Steps marked CONDITIONAL are not built until playtesting demonstrates the need. The trigger condition is stated explicitly. Data preparation (schemas, config keys) may happen earlier; the implementation waits.

**World moves independently.** The world has conflicts and momentum that don't revolve around the player.

**Structured consequence verification.** The validator checks narrator output against known prompt data. The engine knows what MUST appear; the validator checks if it does.

**Prompt token budget.** Narrator prompt >8K tokens: investigate. Never shed: core prompt, consequence tags, target_npc block, stance tags.

**Setting-agnostic mechanics.** All four Ironsworn-family settings share one engine. Adding a setting means adding data, not code.

**Database as read model.** GameState dataclasses remain the write model. SQLite is the read model. Database rebuilt from GameState on restore.

**AI role boundaries.** Narrator: prompt injection, pure prose. Brain: classification + fate triage via tool calling. Director: NPC reflection and AIMS only. Metadata extractor: prompt injection, NPC detection only. Validator: hybrid rule-based + LLM.

**No backward compatibility.** No deprecated fields, no optional parameters that change behavior, no legacy code. When something is replaced, the old version is deleted.

---

## Completed steps

### Step 1 — Oracle roller ✓ (v0.40.0)
### Step 2 — Brain and Director tool calling, Ask the Oracle ✓ (v0.41.0)
### Step 3 — Fate system ✓ (v0.44.0)
### Step 4 — Scene structure ✓ (v0.44.0)
### Step 5 — Director reduction ✓ (v0.44.0)
### Step 6 — Random events and meaning tables ✓ (v0.44.0)
### Step 7 — Move system ✓ (v0.45.0)

Not in scope (data available, activate if scope changes): **Fate as RPG rules** (`mythic_gme_2e.json` → `fate_as_rpg_rules`). **NPC statistics via fate** (`mythic_gme_2e.json` → `npc_statistics`). **Prepared adventure event focus** (`mythic_gme_2e.json` → `prepared_adventure_event_focus`).

---

## Step 8 — Track lifecycle, wiring, and status commands ← NEXT

Track creation, progress marking, completion/failure. Brain schema extension. New tool. Player-facing status queries.

### Architecture decisions

**Track creation: Brain schema fields, not tool calls.** Brain output gets two optional fields: `track_name` (string, nullable) and `track_rank` (enum: troublesome/dangerous/formidable/extreme/epic, nullable). Engine creates the track automatically when the move is a track-creating move (swear_an_iron_vow, make_a_connection, enter_the_fray, undertake_an_expedition, begin_the_scene). If Brain omits track_name on a track-creating move, engine rejects the turn (validation error, not silent fallback). track_rank defaults to "dangerous" if omitted.

**Track selection: Brain schema field + engine fallback.** Brain output gets `target_track` (string, nullable). When a move targets a specific track (fulfill_your_vow, forge_a_bond, reach_a_milestone, develop_your_relationship, test_your_relationship, take_decisive_action, finish_an_expedition, finish_the_scene), engine needs to know which one. Rule: if only one track of the matching type exists, engine auto-selects (no Brain input needed). If multiple exist, Brain must set `target_track` to the track name. Engine matches by name substring (case-insensitive). Missing target_track with multiple candidates → validation error.

**Track querying: `list_tracks` tool.** New Brain tool `list_tracks(track_type?)` returns active tracks with name, type, rank, filled_boxes, ticks. Brain calls this before progress moves to see what's available. Prompt injection tells Brain to call `list_tracks` before any progress move when unsure which track to target.

**Status commands: engine-direct, no AI.** Player types `## status`, `## tracks`, `## [npc name]`. Engine answers directly via narrative templates in strings.yaml. No AI call. Extends the `##` command pattern from correction. WebSocket handler dispatches to a status handler that reads GameState and returns templated prose.

### Substeps

**8.1** `vow_tracks` → `progress_tracks` rename. ✓ Done in v0.45.1 audit.

**8.2** Wire `progress_marks` consumption. Turn pipeline after `resolve_move_outcome`: if `result.progress_marks > 0`, find active track via `_find_progress_track`, call `track.mark_progress()` N times. Log ticks added.

**8.3** Brain schema: add `track_name` (nullable string), `track_rank` (nullable enum), `target_track` (nullable string) to Brain output schema in schemas.py.

**8.4** `list_tracks` tool. `@register("brain")`. Parameters: `track_type` (optional string filter). Returns list of `{name, type, rank, filled_boxes, ticks, max_ticks, id}` for all active tracks, filtered by type if given.

**8.5** Track creation in turn pipeline. After Brain output parsed, before roll: if move is in `TRACK_CREATING_MOVES` set (defined in engine.yaml under `track_creating_moves`), engine creates ProgressTrack from `track_name` + `track_rank` + move's track_category. Generates id as `{type}_{slugified_name}`. Appends to `game.progress_tracks`. For vow-type tracks: also creates ThreadEntry with `linked_track_id`. Validation: missing `track_name` on track-creating move → raise ValueError (Brain retry).

**8.6** Add `status: str = "active"` field to ProgressTrack ("active"/"completed"/"failed"). Track completion helper `complete_track(game, track_id, outcome)`. For vows: updates linked ThreadEntry status. For connections: marks completed (bond is permanent). For combat/scene_challenge: removes track. Turn pipeline calls this after progress roll.

**8.7** `_find_progress_track` updated: accepts optional `target_track` name. If provided, matches by name substring case-insensitive. If not provided and multiple tracks of the type exist, raises ValueError. Filter out completed/failed tracks.

**8.8** Status command system. New WebSocket message type `status_query`. Handler parses `## status`, `## tracks`, `## [name]`. Dispatcher in `web/handlers.py`. Status handler reads GameState directly, formats via strings.yaml templates. Templates use narrative language: "Je eed om [name] weegt zwaar — je hebt nog een lange weg te gaan" not "vow: [name], 3/10 boxes filled." Three initial commands: `## status` (resources, momentum, active impacts), `## tracks` (all active progress tracks), `## [npc name]` (NPC relationship summary). Response sent as regular message, not narration — no scene heading, no aria-live announcement.

**8.9** Tests: progress_marks wiring, list_tracks tool, track creation from Brain output, track completion, _find_progress_track with target_track selection, validation errors for missing track_name and ambiguous target_track, status command parsing and template rendering.

Done when: tracks can be created, progressed, completed, and queried. progress_marks wired. Brain schema extended. Status commands return narrative state summaries.

## Step 9 — Connection tracks replace bond

Replaces integer bond with connection ProgressTrack. NPC bond reads from track filled_boxes.

**9.1** Connection track creation. When Brain selects `connection/make_a_connection` with `track_name` (NPC name) and `track_rank`: engine creates connection track with `id=connection_{npc_id}`, `track_type="connection"`, linked to NPC via `linked_npc_id` field (new on ProgressTrack, nullable). Engine resolves NPC from `target_npc` Brain field. Validation: target_npc required for make_a_connection.

**9.2** Deprecate `NpcData.bond` and `bond_max`. Remove fields. All code reading `npc.bond` → helper `get_npc_bond(game, npc_id) -> int` that finds connection track and returns `filled_boxes` (0 if no track). All code reading `npc.bond_max` → 10 (max filled_boxes on any track).

**9.3** Stance resolver migration. `stance_gate.py`: replace `npc.bond` reads with `get_npc_bond(game, npc_id)`. Thresholds stay the same (bond >= 4 → high, bond >= 2 → mid). Pass `game` into stance functions that currently only take `npc`.

**9.4** Prompt builder migration. NPC tags replace `bond="{n.bond}/{n.bond_max}"` with `bond="{get_npc_bond(game, n.id)}/10"`. Same display format, different source.

**9.5** Tool migration. `query_npc_details` and `query_npc_list` replace `npc.bond` with `get_npc_bond`. Add connection track info to NPC detail output.

**9.6** Other migrations. `architect.py`, `metadata.py`, `correction.py`, `processing.py`, `lifecycle.py`, `activation.py`, `chapters.py`, `setup_common.py`, `director.py`, `db/sync.py`: all `npc.bond` references → `get_npc_bond`. DB schema: drop bond/bond_max columns from npcs table, connection tracks in progress_tracks table.

**9.7** Status command: `## [npc name]` updated to include connection track progress in narrative form. "Je band met Kira groeit langzaam" (low progress) vs "Kira en jij hebben een sterk vertrouwen opgebouwd" (high progress).

**9.8** Elvira updates. StateSnapshot: replace bond with connection track filled_boxes. Invariants: check connection track consistency.

**9.9** Tests: connection track creation via make_a_connection, get_npc_bond helper, stance resolver with connection tracks, NPC without connection track returns bond 0, serialization round-trip, DB sync with new schema.

Done when: `NpcData.bond` and `bond_max` fully removed. All bond logic reads from connection tracks.

## Step 10 — Combat, expedition, and scene challenge tracks

Track type-specific lifecycle. Builds on step 8 track infra.

**10.1** Combat tracks. `enter_the_fray` is track-creating move → engine creates combat track. `take_decisive_action` is progress roll on combat track. Track completed on strong hit, failed on miss (face_defeat consequences). Track removed on completion/failure (combat ends). `battle` (abstract combat) does NOT create a track — it's a single roll.

**10.2** Combat track auto-cleanup. If `combat_position` is cleared (combat ends via narrative) but combat track still active → engine removes track. If combat track completed/failed → engine clears `combat_position`.

**10.3** Expedition tracks. `undertake_an_expedition` is track-creating move. `explore_a_waypoint` marks progress. `finish_an_expedition` is progress roll. Track completed/failed on resolution.

**10.4** Scene challenge tracks. `begin_the_scene` (Classic/Delve only) is track-creating move. Face Danger and Secure an Advantage mark progress when used within a scene challenge (engine detects active scene_challenge track). `finish_the_scene` is progress roll.

**10.5** `available_moves` updated. Existing boolean checks in `_is_move_available` already use `has_combat_track`, `has_expedition`, `has_scene_challenge`. Verify no new filter logic needed.

**10.6** Status command: `## tracks` updated to show combat/expedition/scene challenge tracks with contextual language. "Je vecht tegen [name] — je hebt de overhand" (in_control) vs "Je bent in het nauw gedreven" (bad_spot).

**10.7** Tests: combat track lifecycle (create → progress → decisive action → cleanup), expedition track lifecycle, scene challenge lifecycle, combat position ↔ combat track consistency, available_moves filtering with active tracks.

Done when: all track types have full lifecycle. Combat track syncs with combat_position. Steps 8 + 9 + 10 together form complete progress track system.

## Step 11 — Threats and menace

Threat data model with menace tracks that compete against vow progress. Depends only on progress tracks (step 8), adds gameplay tension immediately.

**11.1** Threat data model. Category (Delve's 9 types), menace track (progress-style), associated vow. Data-driven from engine.yaml.

**11.2** Menace advancement. On misses and triggers, engine ticks menace. Menace competes with vow progress.

**11.3** Threat resolution. Menace fills before vow → Forsake Your Vow forced. Vow fulfilled with high menace → bonus XP.

**11.4** Integration with random events. Threats as targets in event focus table. "Threat advance" event ticks menace.

**11.5** Status command: `## threats` shows active threats with narrative urgency. Menace near full → "De [threat] nadert een kantelpunt." Consequence tag when menace advances: narrator knows the threat grew.

**11.6** Tests.

Done when: threats tick, menace competes with vow progress, random events can target threats.

## Step 12 — Impacts and legacy tracks

**12.1** 10 impacts (wounded, shaken, etc.), each reduces max_momentum by 1. Some block moves. Data-driven from engine.yaml per setting.

**12.2** Legacy tracks: quests/bonds/discoveries → XP. Campaign persistent.

**12.3** XP and Advance. Spend XP on asset abilities or new assets. Costs in engine.yaml.

**12.4** Continue a Legacy. Character retirement/death. Mechanical inheritance from legacy track progress rolls.

**12.5** Status command: `## status` updated to include active impacts in narrative form. "Je bent gewond en geestelijk geschokt — je reserves slinken." Consequence tag when impact is gained or cleared: narrator must acknowledge the change.

**12.6** Tests.

Done when: impacts modify momentum and block moves, legacy tracks accumulate XP, character succession works.

## Step 13 — Asset modifier pipeline

Build the asset subsystem. Prove with representative assets, not full rollout.

**13.1** Modifier pipeline. Types: stat_bonus, reroll, extra_effect, condition_track. Stacking rules, evaluation order, snapshot/restore, momentum burn timing. Prove with 5–10 representative assets across categories.

**13.2** Companion health tracks: companion assets have dedicated health track (separate from NPC connection). Companions are NOT NpcData — no memory, activation, or disposition.

**13.3** Vehicle condition tracks: Command Vehicle and Ship assets have condition track. Withstand Damage is a suffer move on the vehicle condition track.

**13.4** Setting-specific assets loaded per setting_id.

**13.5** Status command: `## assets` shows active assets and condition track status. "Je metgezel [name] is gewond." "Je schip heeft ernstige schade." Companion/vehicle damage → consequence tag so narrator reflects it.

**13.6** Tests.

Done when: 5–10 representative assets work end-to-end, modifier pipeline proven, companion and vehicle tracks functional.

## Step 14 — Asset rollout

Batch data work. No new architecture.

**14.1** All 87 Starforged assets in `data/starforged.json` → `assets` (6 categories).

**14.2** Classic: 78 assets. Delve: additional assets.

**14.3** Sundered Isles: 60 assets.

Done when: all assets across all settings loaded and functional.

## Step 15 — NPC moves, goal-clocks, and autonomous behavior

NPC agency layer. Includes NPC behavior via fate — same layer, natural fit.

**15.1** Goal-clock per NPC. Segments, tick triggers, fill consequence. In NpcData, persisted. Database indexed for trigger evaluation.

**15.2** Tick evaluation. Engine checks triggers after state mutations: bond_below_N, health_below_N, scene_count threshold, faction event. Deterministic. Database queries for cross-NPC conditions.

**15.3** Move execution. Filled clock → engine selects move from NPC's move list. Cooldown. Result: `<npc_action>` tag with predetermined sentence. Sentence via meaning tables (step 6) with engine.yaml templates as fallback.

**15.4** Move generation. Director generates AIMS + move set on NPC promotion to recurring. Director uses tools to query existing NPC relationships and faction state for context. One-time AI call, then deterministic.

**15.5** NPC behavior via fate (was O1). NPCs act autonomously outside player interaction via fate questions + NPC Behavior Table. Data: `mythic_gme_2e.json` → `npc_behavior`.

Procedure: (1) Engine derives expected NPC action from AIMS + stance + situation. (2) Ask fate question with appropriate odds. (3) Interpret result. Yes: NPC does expected action or continues current behavior. No: NPC does next most expected behavior; roll meaning table if unclear. Exceptional Yes: expected action with greater intensity. Exceptional No: opposite of expected or alternative intensified; roll meaning table if unclear. Random Event triggered alongside any answer: NPC takes additional action determined by meaning table roll. For conversations: same procedure; expected action = expected conversational direction.

NOTE — trigger timing: engine evaluates NPC autonomous behavior once per scene, after scene-end bookkeeping. Only NPCs with goal-clocks and AIMS are eligible. Max 1 autonomous NPC action per scene to avoid narrator overload.

Note: prompt builders iterate `game.npcs` in-memory. If NPC count or cross-NPC trigger queries require indexed lookups at this point, migrate relevant prompt builder loops to database queries.

Done when: NPC clocks tick on triggers, filled clocks produce actions in narrator prompt, fate-driven NPC behavior works.

## Step 16 — Factions

**16.1** Faction data model. Name, goal, tenets, members, scheme_clock, resources, inter-faction relationships, player_reputation. Generation uses Datasworn faction oracles. Faction table in database with relationship queries.

**16.2** Three-zone reputation resolver. Extreme overrides personal bond. Moderate thresholds in engine.yaml. Extends stance resolver.

**16.3** Faction turns. Every N scenes, tick scheme_clocks. Filled → faction acts via goal + meaning table. `<faction_event>` tag.

**16.4** NPC loyalty. `loyalty_score: float` on NpcData. Shifts per interaction. When faction agenda conflicts personal agenda, engine compares loyalty_score against stakes-derived threshold. Result fed to narrator as stance.

**16.5** Status command: `## factions` shows faction relationships in narrative form. "De [faction] beschouwt je als een bondgenoot" / "De [faction] ziet je als een bedreiging." Faction event → consequence tag. Reputation shift → consequence tag.

**16.6** Tests.

Done when: factions act independently, reputation affects NPC stance, loyalty conflicts resolve deterministically.

## Step 17 — NPC-player emotional dynamics

First half of DramaSystem emotional layer. Builds on NPC moves (step 15) and factions (step 16).

**17.1** NPC-to-player emotional requests. Engine generates from NPC state (agenda frustration, bond level, recent events). Injected as behavioral constraint in narrator prompt.

**17.2** Refusals and concessions. Player actions interpreted as granting or denying. Engine tracks: what was asked, what was denied, what was given. Affects bond, stance, loyalty_score.

**17.3** NpcData fields: `emotional_requests: list`, `concessions: int`, `refusals: int`.

Done when: NPCs make and track emotional requests, refusals affect relationships.

## Step 18 — NPC-NPC emotional dynamics — CONDITIONAL

Second half of DramaSystem. Significantly more complex than step 17.

CONDITION: implement only after step 17 has been playtested and the game regularly produces 3+ simultaneously active NPCs with overlapping agendas. If solo play rarely generates enough concurrent NPC interaction to make triangles emerge, this step adds complexity without payoff.

**18.1** NPC-to-NPC dynamics. NPCs make requests of each other. Engine resolves based on relationship and loyalty.

**18.2** Triangle creation. Conflicting requests between NPCs create relational triangles. Engine detects and surfaces these as narrator constraints.

Done when: NPC-to-NPC dynamics create triangles, resolved deterministically.

## Step 19 — Expeditions

Starforged's travel/exploration loop. Track infrastructure from step 10 already supports expedition tracks.

**19.1** Expedition data model. Destination, rank, progress track, waypoints, dangers. Reuses ProgressTrack.

**19.2** Expedition moves. Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish an Expedition, Set a Course. Routing: when expedition active, exploration actions go through expedition moves instead of generic face_danger.

**19.3** Waypoint generation from Datasworn exploration oracles per setting.

**19.4** Scene structure integration. Each waypoint is a scene boundary — chaos check at each waypoint.

Done when: expedition loop works with scene structure and progress tracks.

## Step 20 — Site exploration

One generic model. Delve sites, Starforged derelicts/vaults, Sundered Isles caves/ruins are all instances with different oracle table sources.

**20.1** Generalized site data model. Name, objective, theme, domain, rank, progress track, denizen matrix (Delve), discovered features, active dangers. One dataclass covering all settings.

**20.2** Theme + domain system from Datasworn. Delve: 8 themes × 10 domains. Each provides features and dangers tables.

**20.3** Denizen matrix (Delve). Per-site d100 table from theme + domain. Four ranges: common, uncommon, rare, unforeseen.

**20.4** Delve moves from `data/delve.json`: Discover a Site, Delve the Depths, Find an Opportunity, Reveal a Danger, Locate Your Objective, Escape the Depths.

**20.5** Starforged exploration as site configurations. Derelicts, precursor vaults, location themes.

**20.6** Sundered Isles exploration as site configurations.

Done when: Delve site works end-to-end, Starforged and SI are data config on same model.

## Step 21 — NPC generation

**21.1** Tier 1 (throwaway): oracle-rolled demeanor + name + disposition. Datasworn tables via oracle tool.

**21.2** Tier 2 (recurring): full AIMS + moves + goal-clock. AI call for AIMS, then deterministic. Distinct from 15.4 (this creates new NPC; 15.4 adds moves to existing).

**21.3** Promotion trigger: 3 interactions in 5 scenes. Engine tracks via database query.

Done when: throwaway NPCs generate from oracles, promotion creates full NPC with AIMS and goal-clock.

## Step 22 — Location, encounter, and thread generators

Generators are hybrid: oracle tables produce structure, AI writes description within that structure.

**22.1** Location generator. Datasworn oracles → structured location with properties. AI call for contextual description.

**22.2** Encounter generator. Weighted by location + threats + chaos. Table lookup for structure, AI for description.

**22.3** Thread prioritization — CONDITIONAL. Implement only if narrator ignores relevant threads despite guidance. If needed: utility scoring, top 2 enter prompt. Rule-based, no AI.

Done when: locations and encounters generate from oracles with AI description.

## Step 23 — Sundered Isles specifics

Three new subsystems. Everything else is data configuration on existing infrastructure.

**23.1** Ship mechanics. Command vehicle with modules. Ship condition track. Repair. Ship assets from `data/sundered_isles.json` → `assets`. Uses asset pipeline from step 13.

**23.2** Crew mechanics — CONDITIONAL. Crew as resource with morale. Morale thresholds, mutiny triggers. Data-driven from engine.yaml. CONDITION: implement only if Sundered Isles is actively playtested and crew/morale adds meaningful gameplay. Ship mechanics (23.1) work without crew — crew is a layer on top.

**23.3** Cursed dice. "Cursed" impact modifies die rolls. Mechanical modifier in roll pipeline.

**23.4** Data configuration (no new subsystems): naval encounters (combat moves + ship assets), treasure (oracle tables), SI oracles (16 categories), SI exploration (site model + SI oracle tables).

Done when: Sundered Isles fully playable with ship, cursed dice, all SI-specific oracles. Crew mechanics if condition met.

## Step 24 — Campaign hardening

**24.1** Chapter summary receives full mechanical state. All tracks, factions, threads, connections persist.

**24.2** Validator rejects contradictions between chapter summary and game state.

**24.3** Continue a Legacy for character succession (extends step 12.4).

Done when: multi-chapter campaigns persist all state, validator catches contradictions, character succession works across chapters.

## Step 25 — Player vs PC knowledge + keyed scenes

Two scene-level systems. Combined because both are lightweight and modify scene evaluation.

**25.1** Player vs PC knowledge (was O2). Track gap between what the engine knows and what the PC knows. Data: `mythic_gme_2e.json` → `player_vs_pc_knowledge`.

Four strategies: (1) Test-Ask-Real (default): engine-known info requires fate question before becoming PC canon. (2) Reliable vs Unreliable: player knowledge unofficial until discovered; may be wrong. (3) Going With It: cinematic, player knowledge = PC knowledge. (4) Extra Knowledge as RP Opportunity: triggers in-game opportunity for PC to earn it.

NOTE — storage model: new field `knowledge_status: str` on relevant data (RandomEvent, NpcData secrets). Values: "engine_only", "pc_confirmed", "pc_denied". Random events and NPC secrets default to "engine_only". Fate question confirmation flips to "pc_confirmed". Strategy selection stored in GameState preferences.

**25.2** Keyed scenes (was O4). Pre-defined triggers overriding normal scene testing. Evaluated at scene start before chaos check.

Trigger types: thread reaches progress phase X, bond crosses threshold, clock fills, scene count reaches N, chaos factor extreme (1 or 9), custom game state condition. Stored in NarrativeState as list of `KeyedScene` dataclass. Director or story blueprint can create them. Engine evaluates deterministically.

Priority: keyed scene > interrupt > altered > expected.

NOTE — conflict resolution: when multiple keyed scenes trigger simultaneously, engine selects by priority field (int, lower = higher priority). Equal priority: first match wins. Consumed triggers are removed after firing.

Done when: player/PC knowledge gap tracked, keyed scenes override chaos checks on triggers.

## Step 26 — Thread progress tracks, discovery checks, chaos variants

Three related Mythic deepening systems.

**26.1** Thread progress tracks (was O5). Focus thread linked to a thread track. Three track lengths: 10, 15, 20 points. Track divided into phases of 5 points.

Progress earned by: Progress event (significant step toward focus thread, 2 points). Flashpoint event (dramatic event involving focus thread, 2 points).

At each phase boundary (every 5 points): if no Flashpoint during that phase, engine forces a Flashpoint. Treat as Random Event with automatic Current Context focus, interpreted in terms of focus thread.

Conclusion: track fills → focus thread reaches resolution. Engine generates concluding event.

NOTE — track length selection: determined by thread_type. Vow threads use rank-based mapping (troublesome=10, dangerous=15, formidable/extreme/epic=20). Non-vow threads default to 15. Stored as separate `ThreadTrack` dataclass (not ProgressTrack — uses points not ticks, has phase/flashpoint tracking).

NOTE — phase tracking fields: `current_phase: int`, `flashpoint_in_phase: bool`. Reset `flashpoint_in_phase` at each phase boundary.

**26.2** Discovery checks (was O6). Special fate question for finding clues when adventure stalls. Depends on 26.1 (thread progress tracks).

Key rule: odds can NEVER be worse than 50/50. Hard floor overrides normal likelihood resolution.

Results: Yes → roll Thread Discovery Check Table (d10 + current progress points). Exceptional Yes → roll TWICE, combine. No → nothing found. Exceptional No → nothing found AND no further discovery checks this scene.

Thread Discovery Check Table: low totals → Progress +2, mid → Progress +3, high → Flashpoint +2, very high → Flashpoint +3.

**26.3** Chaos factor variants — CONDITIONAL. Four modes: Standard (default, full chaos influence), Mid-Chaos (reduced), Low-Chaos (minimal), No-Chaos (pure odds, no chaos influence). CONDITION: implement only if playtesters report that standard chaos is consistently too wild or too tame. Config key reserved in engine.yaml under `fate.chaos_mode` (defaults to "standard").

Each mode has own fate chart AND fate check modifier table. Data: `mythic_gme_2e.json` → `chaos_variants`.

Done when: thread tracks drive stories forward, discovery checks let players investigate. Chaos variants if condition met.

## Step 27 — Themed element tables + detail check chains

Two meaning table extensions.

**27.1** Themed element tables (was O3). 45 themed d100 tables replacing generic meaning tables with context-specific word lists. Data: `data/mythic_elements.json` (4500 entries total, extracted from source material).

Start with 6 high-use tables: character_actions_general, character_motivations, character_personality, locations, objects, adventure_tone. Remaining tables added in batches.

Table selection: mapping in engine.yaml from (event_focus, scene_type, location_type) → element table name. Examples: NPC Action → character_actions_general or character_actions_combat. PC Negative in dungeon → dungeon_descriptors. Remote Event → Actions meaning table (default fallback).

Doubling rule: if both rolls produce same word → interpret with greater intensity.

**27.2** Detail check chains — CONDITIONAL. Multi-question fate refinement within a scene. CONDITION: implement only if playtesters request deeper scene investigation tools beyond single fate questions. Follow-ups narrow results with odds derived from prior answers. Initial fate question uses normal likelihood resolution. Each follow-up shifts odds one step toward the previous answer (Yes→Likely, Likely→Very Likely, etc.). Chain ends when player stops asking or after 3 follow-ups.

Done when: themed tables replace generic meaning tables contextually. Detail chains if condition met.

## Step 28 — Adventure Crafter core

Core Adventure Crafter systems (was O9, part 1). Data: `data/adventure_crafter.json`.

**28.1** Theme system. Five themes: Action, Tension, Mystery, Social, Personal. Adventure has 5 theme slots ordered by priority. Random assignment: d10, 1–2 Action, 3–4 Tension, 5–6 Mystery, 7–8 Social, 9–10 Personal.

**28.2** Plot points. 186 plot points, each with ranges in 1–5 themes. Data: `adventure_crafter.json` → `plot_points`. Special results: Conclusion (1–8 any theme) resolves plotline. None (9–24) means no plot point. Meta (96–100) rolls on Meta Plot Points table.

**28.3** Meta plot points. Character Exits (1–18), Character Returns (19–27), Character Steps Up (28–36), Character Steps Down (37–55), Character Downgrade (56–73), Character Upgrade (74–82), Plotline Combo (83–100).

**28.4** Turning points. 2–5 plot points combined into coherent narrative event. Procedure: (1) Roll d100 on plotlines list for focus plotline. (2) Generate 2–5 plot points via 3d10 each (one d10 for theme priority, two d10 as d100 for plot point). (3) When plot point invokes character, roll d100 on characters list. (4) Engine provides structured plot points to AI for interpretation.

**28.5** Supporting tables. Plot Point Theme Priority: roll d10, 1–4 first priority, 5–7 second, 8–9 third, 10 fourth or fifth (alternating). Track alternation in game state. Characters List: d100 table, 25 slots of 4 each. Empty slots = "New Character". Max 3 entries per character. Plotlines List: same structure, inverted: most slots "Choose Most Logical Plotline". Keeps adventure focused.

Done when: Adventure Crafter generates turning points from plot points with theme awareness.

## Step 29 — Adventure Crafter integration + character crafting

Was O9, part 2.

**29.1** Mythic integration. Altered scene → turning point with 1–2 plot points (instead of Scene Adjustment Table). Interrupt → turning point with 2–3 plot points (instead of random event). Theme Translation: Standard Mythic → any AC theme, Horror → Tension, Action Adventure → Action, Mystery → Mystery, Social → Social, Personal → Personal, Epic → any. Config switch in engine.yaml under `scene.event_generator: "mythic"` (default) or `"adventure_crafter"`.

**29.2** Character crafting. When plot point needs new character: (1) Roll Character Special Trait (d100) for type. (2) Roll Character Identity (d100) for role; roll 1–33 means dual identity, roll twice. (3) Roll Character Descriptors (d100); roll 1–21 means two traits, roll twice.

Done when: Adventure Crafter works as drop-in replacement or supplement for Mythic altered/interrupt scenes.

---

## Status command reference

Accumulated across steps. All commands use the `##` prefix. Engine answers directly — no AI call.

| Command | Introduced | Content |
|---|---|---|
| `## status` | Step 8 | Resources, momentum. Extended in step 12 (impacts), step 13 (asset conditions) |
| `## tracks` | Step 8 | Active progress tracks. Extended in step 10 (combat/expedition context) |
| `## [npc name]` | Step 8 | NPC relationship. Extended in step 9 (connection track progress) |
| `## threats` | Step 11 | Active threats, menace urgency |
| `## assets` | Step 13 | Active assets, companion/vehicle condition |
| `## factions` | Step 16 | Faction relationships, reputation |

All responses use narrative templates from strings.yaml. No mechanical values exposed. Future commands added as new mechanical state is introduced.
