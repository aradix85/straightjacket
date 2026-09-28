# Straightjacket — Roadmap

## Purpose

Internal working doc: what to build, in what order, with guardrails specific to this codebase. Read after ARCHITECTURE.md, CONTRIBUTING.md, and the code; the rules every change keeps are in CONTRIBUTING.md.

One step is one session: read the code, implement, test, pass the quality gate, delete what the step made obsolete, update this document. When reality diverges from the plan during a step, the roadmap is updated in the same commit; it never claims something the code contradicts.

## After every step

1. The workflow checks of CONTRIBUTING.md (ruff, the test suite with its coverage floor, mypy) and, where it applies, the Elvira run.
2. Violation grep on touched files: `.get("..", ` with a non-neutral literal, `or "..` on a domain value, `except Exception` outside the carve-out files. New hits are new violations; fix them.
3. `git status` confirms the obsolete code is deleted.
4. The step moves to DONE with one line; the next step is promoted to NEXT and gets substeps, a definition of done, and reference patterns; Current state records any decision taken. The md files (README, ARCHITECTURE, CONTRIBUTING, `docs/`, ORIGINS, SECURITY, AUDIT) are checked for claims the step made wrong, and the step gets one CHANGELOG entry.

## Reference patterns

- New AI-call wrapper: `ai/brain.py` (call_brain, call_revelation_check).
- Director tool: `tools/builtins.py` → `query_game_state` (`docs/ai.md`, Tool calling and prompt injection).
- Strict nested domain lookup: `mechanics/stance_gate.py` (resolve_npc_stance).
- New yaml-backed config section: an entry in `engine_config.py` `_SIMPLE_SECTIONS`, with its dataclass in `engine_config_dataclasses.py` (required fields, no defaults).
- New template text: `prompts/*.yaml` for AI-facing text, with narrator-facing blocks in `prompts/blocks.yaml`; `strings/*.yaml` for user-facing text; `engine/*.yaml` for engine-internal values.
- Subpackage layout: `engine/correction/`.
- Large container split: `engine_config.py` re-exporting from `engine_config_dataclasses.py`.
- No post-hoc validators of AI output: see "No narration validator" in `docs/divergences.md`.

## Current state

### Priorities

Set 2026-09-24, revised 2026-09-29.

1. Step 9b, the generators (NEXT STEP below). Settlements, locations, NPCs, and encounters come from the entry point step 9a built, so the narrator invents fewer entities.
2. Open findings from Elvira runs:
   - The coverage tracker counted no NPC introductions while the metadata extraction reported one.
   - The metadata extraction's identity reveals for unnamed NPCs are rejected for zero word overlap, and a stub NPC is created instead (runs of 2026-09-25).
   - The metadata extraction once named an NPC id that does not exist (`npc_details: could not find NPC 'npc_5'`, 2026.09.25.6).
   - After a chapter transition the returning NPC "Maren Silk" and a new NPC "Maren" stood side by side as two active NPCs (2026.09.27.1); returning NPCs are merged by exact name only.
   - Structured answers that ran to the 8192-token limit (the Director in about 3 percent of its calls on GLM 5.3 Flash, the Brain and the extractors on GLM 5.3, one opening setup on 2026-09-25) were a carriage-return loop, banned in 2026.09.26.20. Five sessions ran clean afterwards, but on 2026-09-29 one Director answer ran to the limit again (24,693 characters, "Invalid control character" at column 4), so some other whitespace or control character loops too. Capture the raw answer the next time it happens before choosing a fix.
3. Narrator-prompt tuning for GLM 5.3, one change at a time, measured with Elvira sessions and by reading the narrations of misses. Open:
   - A miss still sometimes hands the player a useful clue (result integrity on a miss swings between about 2.8 and 3.9 of 5). Five instruction variants did not help (2026.09.26.14 and .18), so this looks like the model. A narration now and then adds a step the player did not take.
   - Three rules still apply on a miss without exception: NPCs answer what was asked, one unexplained background detail per scene, a suspended scene ending.
   - The action task tells a strong hit in a desperate phase to carry the surrounding darkness.
   - PLAYER AGENCY's inner-life clause says to describe what a camera could record, including action, beside the clause that limits the character's actions to the stated one.
   - `fact_budget` allows one or two extra facts, while the dialog task says nothing beyond the question's scope.
   - `<style>` asks for terse prose, and much of the system prompt still addresses GENRE PHYSICS.
   - `prompts/director.yaml` still has the Director recommend a "breather", although pacing is engine-computed.
   - The extraction prompts (`narrator_metadata`, `opening_setup_extractor`), `revelation_check_system`, `blueprint_voicing`, `chapter_summary`, and `recap` have been read but not tuned.
   - The Director was about half of a session's cost in 2026.09.25.5, measured before its single tool (2026.09.26.11) and before GLM 5.3; measure again before deciding anything. Running it less often would leave NPC profiles stale and is not planned.
4. Test fixtures made through the real character-creation path instead of hand-built states, since a hand-built fixture hid the roll-bonus bug of 2026.09.24.33.
5. Smaller open items:
   - `game/action_resolution.py` → `resolve_action_phase` falls back to the literals `"vow"` and `"dangerous"` when a move has no Datasworn entry or no progress track (Principle 2 material).
   - The opening extraction returns whole descriptive sentences as location names ("Smoke-shed in a cedar canyon settlement, by a rain-swollen river, …"), which then stand in `<location>`, `<prev_locations>`, and `<fact about>`; the Brain's `location_change` already asks for a short name, the opening extractor does not.
   - `web/serializers.py` → `build_creation_options` branches on the setting id `delve` (Principle 2 material, see AUDIT.md).
   - No principle audit from AUDIT.md has been run yet.

### Working agreements

- Nothing goes in the CHANGELOG before its check has been read.
- Fewer, larger releases: one release per finished piece of work, not one per measurement.

### Running things

On this machine the API keys live in the Windows user environment: `TOGETHER_API_KEY` for the game, `OPENAI_API_KEY` for Elvira. How to run her is under Testing in CONTRIBUTING.md.

Models: every AI role runs on GLM 5.3 through Together since 2026.09.26.20; `docs/ai.md` describes the configuration, and the measurements behind it are in the CHANGELOG from 2026.09.26.2 to .20.

### Decisions referenced by later steps

**Track-type composition (Option C).** Domain objects that own a progress track (expeditions, sites, and thread tracks in steps 25, 26, and 31) hold a `progress: ProgressTrack` field plus their own fields. Rejected: inheriting from ProgressTrack, which would push domain concerns onto a primitive used everywhere, and a registry with a `kind` discriminator, which adds a lookup at every callsite. ProgressTrack stays single-purpose, snapshot and restore work through SerializableMixin on either layer, and a new track-owning object needs no change to ProgressTrack.

**Categorisation follows implementation.** `available_moves` filters `no_roll` and `special_track` moves out of the Brain's choice, so a category on those moves cannot be enforced; `test_every_implemented_move_has_real_category` checks implemented moves only. If a filter change brings such moves back into view, they get their category and their outcomes in the same commit as the filter change (step 13b).

**Each spawn source names its own entities** from what it naturally has, as threats and clocks do today (`docs/mechanics.md`, Threats and clocks). Later spawners of new entity types follow the same axis.

---

## DONE

One line per completed step, newest last. Details in CHANGELOG.

- Step 1 — Explicit chapter transitions: `ChapterSummary` carries a mechanical snapshot; three-place capture/reset/restore pattern (0.74.0).
- Step 2 — Chapter-summary contradiction validator (2026.04.25.0), removed again in 2026.04.27.9.
- Step 3 — Continue a Legacy: character succession with locked-in inheritance rolls (2026.04.25.1).
- Step 4 — Keyed scenes, consumer side: `keyed > interrupt > altered > expected` (2026.04.25.2).
- Step 5 — Adventure Crafter primitives: themes, plot points, meta dispatch (2026.04.26.0).
- Step 6 — AI data supply audit: tool-call vs prompt-inject verified at fourteen AI call sites (2026.04.28.5).
- Step 6b — AC turning points and supporting tables; shared `characters_list` plus `plotlines_list` (2026.04.29.0).
- Step 7a — AI architect replaced by AC blueprint seed plus `call_blueprint_voicing` (2026.05.06.0).
- Step 8 — `ai/architect.py` split into `ai/recap.py` and `ai/chapter_summary.py` (2026.05.06.1).
- Step 7b — AC character-crafting tables as pure helpers; `CharacterTraits` under orphan carve-out until step 11 (2026.05.06.2).
- Step 7c — Keyed-scene spawners from AC, random events, and clocks, plus pattern grammar (2026.05.06.3).
- Threat creation from random events and AC plot-points; `datasworn/cascade.py` (2026.05.11.0).
- Clock expansion — fill consequences in `engine/clocks.yaml::fill_consequences`, clock creation from random events and AC plot-points (AC clocks named after the plot point), `owner_kind`/`owner_id` refactor (2026.05.14.0).
- Providers and SDKs — per-role providers, startup model check, single retry layer, timeouts, refusals, OpenAI's own models (2026.09.24.9 to .14).
- Sentence-level narration streaming (2026.09.24.12).
- Elvira rebuilt — streaming checks, blind judge, save round trip, succession, coverage, WebSocket probes, engine events and warnings, report (2026.09.24.15 to .42).
- Rules conformance pass R, see section R (2026.09.24.17 to .34).
- EdgeTales idea E5 — the Brain's `target_npc`, `bonus_id`, and `target_track` limited to what the prompt offers (2026.09.24.58).
- Step 9a — Fact resolution: the Brain names undetermined facts, fate settles them with engine-derived odds, the narrator gets `<facts>`; Ask the Oracle answers yes/no questions through facts; the momentum burn resumes after the roll on the turn's own path (2026.09.29.0).

---

## NEXT STEP — 9b: Generators

Entity creation through the entry point step 9a built: `mechanics/generation.py` → `generate(game, category, context)`, whose categories are registered in `engine/generation.yaml` and dispatched through `_GENERATORS`, with `fact` as the first category. Step 9b adds entity categories that return a `GeneratedEntity`: the category plus the rolled table results, keyed by the role each table plays in that category. How `generate` types its context and result once there is more than one category (a union, or one typed function per category behind the registry) is decided at the start of the step.

**9b.1** Categories settlement, location, npc, and encounter registered in `engine/generation.yaml`; steps 11, 25, and 26 add npc tiers, waypoints, and sites.

**9b.2** An oracle accessor for Delve theme plus domain, Sundered Isles cursed and non-cursed variants, and Starforged flat d100, with the format taken from setting yaml, not from branching on setting names.

**9b.3** Per-category oracle paths in setting yaml as a mapping keyed by category name (the keys are domain data, decided in 2026.09.24.47); a registered category without a path in the active setting's parent chain raises KeyError. The parent-chain lookup exists: `datasworn/settings.py` → `SettingPackage.oracle_data_for`, `_resolve_oracle_paths`.

**9b.4** Generated content reaches the narrator as a `<generated>` tag after the setting's `vocabulary.substitutions` are applied: if the oracle says "spaceship", the prompt gets the setting's substitution. No post-hoc check.

**9b.5** Chained oracle tables go through `datasworn/cascade.py` → `roll_oracle_cascade`. At least one real callsite; candidate: `npc/naming.py` → `roll_oracle_name` through the `npc` category. If none fits, a documented orphan-symbol carve-out that step 10 removes, as for `CharacterTraits`.

**9b.6** Tests: smoke with stub oracle data, the registry and the yaml list stay equal (as `tests/test_fact_resolution.py` checks for `fact`), a missing path raises. If generated entities are persisted, the save format breaks.

### Definition of Done

- The four categories are registered in `engine/generation.yaml` and dispatched by `generate`; an unknown category or a missing oracle path raises.
- Oracle paths per category live in the setting yaml; no Python branches on setting names.
- Generated content reaches the narrator as `<generated>` with the setting's vocabulary substitutions applied.
- `datasworn/cascade.py` → `roll_oracle_cascade` has a real callsite through a category.
- ARCHITECTURE.md ("Engine-resolved fiction") and `docs/mechanics.md` say what is generated and when.
- An Elvira run shows `<generated>` tags in play and no new engine warnings.
- Quality gate green, no new project-rule violations, one CHANGELOG entry.

### Reference patterns

- Entry point and registry: `mechanics/generation.py` → `generate`, `_GENERATORS`; `engine/generation.yaml`.
- A generated result as a prompt block: `prompt_shared.py` → `_facts_block`, templates in `prompts/blocks.yaml`.
- Parent-chain oracle lookup: `datasworn/settings.py` → `SettingPackage.oracle_data_for`.
- Cascade rolls: `datasworn/cascade.py` → `roll_oracle_cascade`, used today by threat naming.

---

## Next steps

Sketches; order indicative. Each entry gets substeps, a definition of done, and reference patterns when it is promoted to NEXT.

Steps 11, 14b, 25, and 26 each plan a Director tool of their own. Since 2026.09.26.11 the Director has a single tool, `query_game_state`, which cut its tool rounds; whether each planned tool becomes a new one or part of that one is decided when the step is promoted.

### E — Ideas from the EdgeTales comparison (2026-09-24)

EdgeTales 0.9.67 to 0.9.96 (Lars) was read in full on 2026-09-24; its applicable bug fixes landed in 2026.09.24.6. The ideas below fit Straightjacket but need a design decision, a save-format change, or an Elvira measurement. Reimplement the idea, do not port code, and credit EdgeTales in the CHANGELOG entry that lands each one.

**E1 — Clock and threat pressure in narrative direction.** The narrator only learns about a clock when it fills, while the design document names clock states and threat levels as sources of narrative intensity. The engine computes a pressure tier from the fullest active threat or scheme clock and the highest threat menace (thresholds in engine yaml) and feeds it into the existing intensity derivation; no numbers or clock names reach the prompt. Measure with Elvira before and after.

**E2 — NPC exit tracking.** NPCs who walk out of a scene can be pulled back next scene by the activation bonus without narrative reason. The narrator_metadata extractor reports `exited_npc_ids` (the same pattern as `deceased_npcs`); `NpcData` gets an absent-until-scene value (the save format breaks); activation scores the NPC zero while absent unless the player names them or the Brain targets them; chapter start clears the value. Tests for exit, suppression, the player-name override, and the chapter reset.

**E3 — NPC-to-NPC dynamics in the prompt.** `MemoryEntry.about_npc` records what NPCs remember about each other, but the narrator never sees it. The engine selects `about_npc` memories between NPCs present in the scene (one per pair, most recent first, cap in yaml) and injects them as a block whose template lives in `prompts/blocks.yaml`. Stepping stone for step 24.

**E4 — Stale NPC retirement.** An active NPC with an empty connection track and no new memory for N scenes (yaml) moves to background; reactivation already exists. Guard against retiring an NPC in the scene they reappear.

**E6 — Narrator rule on NPC backstory.** NPCs draw on their description, agenda, arc, and earlier scenes; where their past is not established, they keep it vague rather than invent family or history. Phrase it as direction, not prohibition, and measure with Elvira before and after, because prompt wording has caused regressions before (2026.04.27.4).

### R — Rules conformance with the source systems

The principle and the list of deliberate divergences are in `docs/divergences.md`.

Checked (2026.09.24.17 to .34): the action roll, momentum, Endure Harm and Endure Stress, Pay the Price, every match clause, chained and oracle moves, progress, legacy tracks and experience, connections, Mythic's fate check, fate chart, scene test, chaos factor, event focus, lists, and meaning tables, the Adventure Crafter's tables, theme priority, and turning points, Blades clock sizes, and asset and connection adds.

Open: ability effects other than adds (step 18); wounded and shaken blocking recovery in classic Ironsworn; the individual words of the oracle and meaning tables, not checked against the books. Outcomes where the player would choose a cost are a recorded divergence, not open work.

### 10 — Location and encounter generators

**10.1** Location generator through the step 9b framework: Datasworn oracles give a structured location, the AI describes it within that structure.

**10.2** Encounter generator weighted by location properties, active threats, and chaos; oracle for structure, AI for description. Weights in `engine/encounter_weights.yaml` (new).

**10.3** Prompt budget: `<generated>` tags replace unstructured invention, net near zero.

**10.4** Encounter output reaches the Brain as structured data through the existing state path; couples forward to steps 12 and 25.

**10.5** Tests.

### 11 — NPC generation with tiers

**11.1** Tier 1 (throwaway): demeanor, name, and disposition rolled from oracles, no AI call. New oracle paths `oracle_paths.npc_demeanor` and `oracle_paths.npc_disposition` in `data/settings/*.yaml`; `oracle_paths.names` gives the name; a missing path raises KeyError. The narrator receives the rolled values as structured prompt context.

**11.2** Tier 2 (recurring): full AIMS plus a goal clock, the AI writing only the AIMS. The Director generates them: it reads the tier-1 base and the active threads through its game-state tool, then writes the AIMS through its JSON schema; always-relevant context (current location, faction state once step 14 lands) is prompt-injected.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new), default three interactions in five scenes, through a DB query.

**11.4** A `tier` field on NpcData as a config-key string, not a Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed rolls; AIMS generation fires only on promotion; missing tier-1 oracle paths raise KeyError.

### 12 — NPC goal clocks and autonomous actions

Builds on step 11 and extends `check_npc_agency` (`pacing.npc_agency_interval`).

**12.1** `goal_clock: ClockData | None` on NpcData, persisted and DB-indexed.

**12.2** Ticks after scene-end bookkeeping on triggers in `engine/npc_goal_clocks.yaml` (new): bond below N, health below N, scene count. Deterministic.

**12.3** A filled goal clock produces an `<npc_action>` tag. The action generation sits behind a callable so step 13 can swap its source (meaning table to fate question) without rewriting the fill handler. Default: meaning table plus templates in `prompts/blocks.yaml`.

**12.4** The Director sets a goal clock when an NPC is promoted to recurring. Decide at implementation: either `engine/clock_keyed_scenes.yaml` gains a `goal` clock type (small priority, full fill only) and the callsite calls `spawn_keyed_scenes_for_clock`, or goal clocks are exempt because their fill already is the `<npc_action>` event; if exempt, record why in the CHANGELOG.

**12.5** At most one `<npc_action>` per scene (config). The tag is prompt-injected: always relevant when present, bounded, no AI selection.

### 13 — NPC behavior via fate

Fate plus expected behavior derived from AIMS and stance. Data: `mythic_gme_2e.json` → `npc_behavior`. The engine derives the expected behavior, asks a fate question, and interprets the answer; a move list with cooldown as refinement. Replaces the step 12.3 callable. Once per scene after scene-end bookkeeping, only NPCs with a goal clock and AIMS, at most one per scene.

### 13b — Unimplemented Datasworn mechanics

The move categories of the four shipped settings hold 89 unique move stems; 56 are formal moves in `engine/move_outcomes.yaml` (recounted in 2026.09.24.46). The other 33 are `no_roll` (29) or `special_track` (4): 6 belong to steps 25, 26, and 28, and about 27 are general mechanics not yet wired. Asset abilities define 48 further moves, covered by steps 18 to 20. This step wires the general group following "Datasworn mechanic naming" in `docs/mechanics.md`: a player choice with a structured outcome becomes a formal move; a consequence that fires when a condition becomes true becomes an engine trigger with a direct name.

Group A, formal moves: `combat/turn_the_tide`, `adventure/aid_your_ally` and `relationship/aid_your_ally` (needs the NPC-action context of step 11), `relationship/write_your_epilogue` (couples with the retire flow of step 3), `scene_challenge/begin_the_scene`, `failure/learn_from_your_failures`, `threat/take_a_hiatus`, and the progress-mark moves `legacy/advance`, `legacy/earn_experience`, `quest/advance`, `quest/reach_a_milestone`.

Group B, engine triggers: `mark_failure_on_miss` (`failure/mark_your_failure`), `face_setback_at_min_momentum` (`suffer/face_a_setback`, when momentum would drop below -6), `mark_supply_depletion` (`suffer/out_of_supply`), `face_defeat_on_objective_loss` (`combat/face_defeat`). The existing `advance_menace_on_miss` and `pay_the_price` already follow this pattern.

Group C, covered elsewhere or deliberately not wired: `legacy/continue_a_legacy` (step 3 succession), `fate/ask_the_oracle` (the engine's own `ask_the_oracle`), `threshold/overcome_destruction` (step 28), and the five session moves (decision in CHANGELOG 2026.04.28.3).

**13b.1** Group A in `engine/move_outcomes.yaml` and `engine/move_categories.yaml`, reusing the existing handler patterns (progress mark, momentum shift, special track).

**13b.2** Group B at their callsites: the first three in `mechanics/consequences.py` (MISS resolution, the momentum clamp, the supply-zero check), the fourth where objective state changes. Each emits a tag for the narrator and updates the state. Where `scene_challenge/begin_the_scene` creates a clock, the callsite calls `spawn_keyed_scenes_for_clock`, as every clock-creation site does.

**13b.3** Per-trigger config (failure-track length, setback redirect, supply-depletion impacts) in the relevant `engine/*.yaml`.

**13b.4** Triggered events reach the narrator as prompt-injected tags (`<failure_marked>`, `<setback>`, `<supply_depletion>`, `<defeat_faced>`).

**13b.5** Tests: each formal move through the move-outcome pipeline, each trigger under its exact condition, `advance_menace_on_miss` as regression.

Done: formal-move coverage rises from 56 to about 67 stems, with four new engine triggers.

### 14a — Faction data model

**14a.1** FactionData dataclass: name, goal, tenets, members (NPC ids); required fields; step 16 adds reputation.

**14a.2** `faction_id` on NpcData.

**14a.3** Faction table in the DB; round trip through SerializableMixin.

**14a.4** Tests: round trip of NpcData and FactionData, membership survives save and load.

### 14b — Scheme clocks and chapter-spanning factions

**14b.1** A scheme clock per faction, ticking every N scenes (`engine/factions.yaml` → `scheme_clock_interval`, new); a fill queues a faction event. The creation site calls `spawn_keyed_scenes_for_clock` (`engine/clock_keyed_scenes.yaml` already covers `scheme`).

**14b.2** ChapterSummary gains `factions: list[FactionData]`, through the three-place chapter pattern.

**14b.3** Faction archetypes from Datasworn oracles: `factions: str` returns to the `OraclePaths` dataclass and the paths to the setting yamls (starforged `factions`, sundered_isles `faction`; classic Ironsworn has none). A setting with factions and no path raises KeyError.

**14b.4** Faction-event tags are prompt-injected for the narrator; the Director gets faction context for NPC reflections (see the note on Director tools above).

**14b.5** Tests: scheme clocks tick, faction events queue, snapshot and restore across a chapter boundary.

### 15 — Faction prompts and status

**15.1** Faction context for activated NPCs in the prompt (about 15 tokens per NPC), budget in `engine/factions.yaml`.

**15.2** `<faction_event>` tag on a scheme-clock fill (about 30 tokens), template in `prompts/blocks.yaml`.

**15.3** `/factions` status command in narrative form, strings in `strings/*.yaml`.

**15.4** Tests.

### 16 — Faction reputation and NPC loyalty

**16.1** Player reputation per faction (hostile, neutral, allied); an extreme overrides personal bond in the stance resolver. Thresholds in yaml.

**16.2** NPC loyalty derived from faction bond against player bond through connection tracks; no new NpcData field.

**16.3** The reputation field on FactionData reserved in 14a.1.

### 17 — Setting enrichment from sourced tables

The Yaml content boundary (CONTRIBUTING.md) rules out hand-written lists of names, descriptors, or descriptions in setting yaml. Variety comes from tables with a source: the Datasworn oracles each setting ships, through steps 9b and 10, and Mythic's element meaning tables, through steps 33 and 34. What remains of this step is wiring inside those steps: each setting's oracle-path mapping gains the tables its generator categories need.

### 18 — Asset mechanics beyond adds

`GameState.asset_abilities` records the enabled abilities of every path and asset, and enabled abilities with an add reach the action roll through the Brain's `bonus_id` (`mechanics/assets.py`, `mechanics/bonuses.py`). The steps below build on that mechanism.

**18.1** Rerolls granted by abilities.

**18.2** Extra effects on a hit (mark progress, take momentum, clear an impact) beyond the momentum-on-hit already handled.

**18.3** Condition meters on assets (companion health, vehicle integrity), shared with step 19.

**18.4** Choosing which ability an upgrade enables instead of the next in order.

**18.5** Tests per effect type with real Datasworn assets and ids exactly as character creation stores them.

### 19 — Companion and vehicle assets

**19.1** Companion health tracks (not NpcData).

**19.2** Vehicle condition tracks; Withstand Damage as a suffer move on vehicle condition.

**19.3** Setting-specific companion and vehicle assets.

**19.4** `/assets` status command.

**19.5** Companions and vehicles extend `<character_state>`; template in yaml.

**19.6** Tests.

### 20 — Asset rollout per setting

One session per setting, every Datasworn asset working through the step 18 pipeline: **20.1** Starforged, **20.2** Classic, **20.3** Delve, **20.4** Sundered Isles. An asset that needs a fix gets it in the pipeline, not as a per-setting patch.

### 21 — Relationship event detection

**21.1** Event types in `engine/relationship_events.yaml` → `types`: promise_broken, betrayal, sacrifice, debt_owed, debt_repaid, loyalty_shown. Extensible.

**21.2** The metadata extractor detects events: `relationship_events: list[{npc_id, event_type, description}]`.

**21.3** Persisted as `relationship_events: list[RelationshipEvent]` on NpcData, with snapshot and restore. Engine-internal, feeding steps 22 and 23.

**21.4** Tests.

### 22 — Emotional requests

**22.1** NPC-to-player requests generated by the engine from NPC state (disposition, bond, recent events). Rules in `engine/emotional_requests.yaml` (new); templates in `prompts/blocks.yaml`.

**22.2** `<emotional_request>` tag in the narrator prompt.

**22.3** `pending_request: str | None` on NpcData, one per NPC.

**22.4** Prompt budget about 40 tokens per NPC with a request, cap in config.

**22.5** Tests.

### 23 — Refusals, concessions, relationship effects

**23.1** The Brain classifies the player's response to a request as granting or denying.

**23.2** `concessions: int` and `refusals: int` on NpcData.

**23.3** Refusals and concessions affect bond through the connection track and the stance matrix; weights in `engine/relationship_events.yaml` → `effects`.

**23.4** Tests.

### 24 — NPC-NPC triangles involving the player

NPC-to-NPC requests and triangles, limited to those that involve the player. Inter-faction emotional dynamics are out of scope (see the relationship-layer scope in `docs/divergences.md`); factions act through schemes (steps 14 to 16).

### 25 — Expedition moves and waypoints

**25.1** ExpeditionData (Option C): destination, rank, `progress: ProgressTrack`, waypoints, dangers.

**25.2** Expedition moves: Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish, Set a Course; routing config-driven.

**25.3** Waypoints as a new step 9b category in yaml.

**25.4** Each waypoint is a scene boundary with a chaos check.

**25.5** About 30 tokens of expedition state prompt-injected while an expedition is active; expedition history for the Director's chapter summary or recap (see the note on Director tools above).

**25.6** Tests.

### 26 — Site exploration data model and Delve

**26.1** SiteData (Option C): name, objective, theme, domain, rank, `progress: ProgressTrack`, denizen matrix, discovered features, active dangers. One model for every setting.

**26.2** Theme and domain from Datasworn; Delve has 8 themes and 10 domains with feature and danger tables.

**26.3** Delve's denizen matrix: a d100 per site in four ranges (common, uncommon, rare, unforeseen), boundaries in per-setting config.

**26.4** Delve moves: Discover a Site, Delve the Depths, Find an Opportunity, Reveal a Danger, Locate Your Objective, Escape the Depths; routing config-driven.

**26.5** About 60 tokens of active site state prompt-injected, the three most recent discovered features; the full feature list for the Director (see the note on Director tools above).

**26.6** Tests.

### 27 — Sites for Starforged and Sundered Isles

**27.1** Starforged derelicts, precursor vaults, and location themes as site configurations, no Python.

**27.2** Sundered Isles exploration as site configurations.

**27.3** Tests.

### 28 — Sundered Isles specifics

**28.1** Ship mechanics (command vehicle with modules, condition track, repair) through the step 18 and 19 asset pipeline.

**28.2** Cursed die. The Datasworn texts that mention it, all in the Chattering Skull asset, describe an extra ten-sided die added to the roll with an effect on a 10; check the Sundered Isles rules for when it is rolled before designing this (section R). The existing `cursed` impact in `engine/impacts.yaml` is a separate mechanic.

**28.3** Data config: naval encounters, treasure, the 16 Sundered Isles oracle categories, exploration.

**28.4** Tests.

### 29 — Crew mechanics

The Sundered Isles crew and morale system.

### 30 — Player vs PC knowledge

Four strategies in `mythic_gme_2e.json` → `player_vs_pc_knowledge`: Test-Ask-Real (default), Reliable vs Unreliable, Going With It, Extra Knowledge as RP. New field `knowledge_status: str` on RandomEvent and on NpcData secrets, values engine_only, pc_confirmed, pc_denied; strategy in `engine/fate.yaml`.

### 31 — Thread progress tracks and discovery checks

**31.1** ThreadTrackData (Option C) with `progress: ProgressTrack`, `current_phase: int`, and `flashpoint_in_phase: bool`: the focus thread linked to a track of 10, 15, or 20, phases of 5, a forced Flashpoint at a phase boundary without one. Length by vow rank (troublesome 10, dangerous 15, formidable and higher 20; non-vow threads 15) in `engine/thread_tracks.yaml` (new) → `length_by_rank`.

**31.2** Discovery checks: a fate question with a 50/50 floor, mapped to the Thread Discovery Check Table (`mythic_gme_2e.json` → `thread_discovery_check`).

**31.3** A `thread_phase` keyed-scene trigger in `engine/keyed_scenes.yaml` (`value_format: "<thread_id>:<phase>"`) with its evaluator in `mechanics/keyed_scenes.py` → `_EVALUATORS`, and the matching entry in AC's keyed-scene mapping.

**31.4** Tests.

### 32 — Chaos factor variants

Standard, Mid-Chaos, Low-Chaos, and No-Chaos, each with its own fate chart and fate-check modifier table (`mythic_gme_2e.json` → `chaos_variants`). `fate.chaos_mode` required in config.

### 33 — Themed element tables

`data/mythic_gme_2e.json` → `meaning_tables.elements` holds 45 themed d100 tables (locations, characters, objects, adventure tone, character traits, creature descriptors, terrain, and more). `mechanics/random_events.py` → `roll_meaning_table` reads only actions and descriptions and raises on an unknown name.

**33.1** `roll_meaning_table` accepts any table in `meaning_tables.elements`, the valid names read at load, the KeyError kept.

**33.2** Six high-use tables first, chosen through `engine/themed_tables.yaml` (new) from event focus, scene type, and location type. The same word twice means greater intensity.

**33.3** The random-event pipeline uses a themed table when one matches the context and actions and descriptions otherwise; the result goes into the existing `<random_event>` tag.

**33.4** Tests.

### 34 — Remaining themed tables

The other 39 tables mapped in `engine/themed_tables.yaml`; config only.

### 35 — Detail check chains

Multi-question fate refinement: each follow-up shifts the odds one step toward the previous answer; at most three, config-driven.
