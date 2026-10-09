# Straightjacket — Roadmap

Internal working doc: what gets built next, and in what order. The rules every change keeps and the checks before a commit are in CONTRIBUTING.md; this document adds only the order of work and what concerns the sessions with the user.

## How the roadmap works

The steps below are the order of work: NEXT STEP first, then the others in their order. Nothing is worked on outside a step, and a new finding becomes a substep of an existing step or a new step in the same commit. One step is one session: read the code, build, test, and delete what the step made obsolete. When reality diverges from the plan, the roadmap changes in the same commit; it never claims what the code contradicts.

Closing a step: the checks of CONTRIBUTING.md pass, the step leaves this document and gets its CHANGELOG entry, the next step becomes NEXT STEP with substeps, a definition of done, and reference patterns, and a decision that later steps rely on goes under Decisions. The step's area is read against the source rulebooks and, where it touches the architecture, against the design document; a departure goes to `docs/divergences.md`.

## Sessions with the user

- The user writes in Dutch and reads with a screen reader: answers are in Dutch and in plain prose, while the repository stays in English.
- A session starts by reading every md file in the root and in `docs/`, of the CHANGELOG only the entries since the last finished step, and then continues with NEXT STEP. The design document is not in the repository; README.md links it.
- The Elvira sessions a step needs are part of the work; an eight-turn session costs about 15 to 20 cents.
- Each finished release is committed and pushed to main.
- On this machine the API keys live in the Windows user environment (`TOGETHER_API_KEY` for the game, `OPENAI_API_KEY` for Elvira); a process started by a tool may need them set in its own environment first.
- The measuring setup for prompt tuning lives outside the repository in `C:\Users\radix\Documents\mimo_probe`: captured situations, the audit and blind-reading scripts, and a README.md that says how to capture, measure a variant, and read blind. Its captured situations predate the player-agency line in `prompts/tasks.yaml`; the README says how to measure against the current prompt.

## Reference patterns

- New AI-call wrapper: `ai/brain.py` → `call_brain` for a call the turn cannot do without, `ai/blueprint_voicing.py` → `call_blueprint_voicing` for one that degrades.
- Director tool: `tools/builtins.py` → `query_game_state` (`docs/ai.md`, Tool calling and prompt injection).
- Strict nested domain lookup: `mechanics/stance_gate.py` → `resolve_npc_stance`.
- New yaml-backed config section: an entry in `engine_config.py` `_SIMPLE_SECTIONS`, with its dataclass in `engine_config_dataclasses.py` (required fields, no defaults).
- New template text: `prompts/*.yaml` for AI-facing text, with narrator-facing blocks in `prompts/blocks.yaml`; `strings/*.yaml` for user-facing text; `engine/*.yaml` for engine-internal values.
- Subpackage layout: `engine/correction/`.
- Large container split: `engine_config.py` re-exporting from `engine_config_dataclasses.py`.
- No post-hoc validators of AI output: "No narration validator" in `docs/divergences.md`.

## Decisions referenced by later steps

**Track-type composition (Option C).** Domain objects that own a progress track (expeditions, sites, and thread tracks in steps 25, 26, and 31) hold a `progress: ProgressTrack` field plus their own fields. Rejected: inheriting from ProgressTrack, which would push domain concerns onto a primitive used everywhere, and a registry with a `kind` discriminator, which adds a lookup at every callsite.

**Categorisation follows implementation.** `available_moves` filters `no_roll` and `special_track` moves out of the Brain's choice, so a category on those moves cannot be enforced; `test_every_implemented_move_has_real_category` checks implemented moves only. If a filter change brings such moves back into view, they get their category and their outcomes in the same commit (steps 9k and 13b).

**Each spawn source names its own entities** from what it naturally has, as threats and clocks do (`docs/mechanics.md`, Threats and clocks). Later spawners of new entity types follow the same axis.

**One model for every role**, the user's preference, is recorded in `docs/ai.md` (Model assignment); the prompt work of step 9f relies on it.

---

## NEXT STEP — 9f: Narrator, Director, and extraction prompts

The prompts are tuned one change at a time against measurements, not impressions. A measurement replays the same situations for every variant: full narrator prompts captured from real sessions, each variant run three times per situation, every narration audited against its own prompt by a judge from a model family other than the narrator's (contradictions, information the prompt withholds, softened results, player-character overreach, word budget), and pairs of narrations read blind with the order shuffled and each model or variant on position A equally often. The measuring scripts stay outside the repository; what a change measured goes in its CHANGELOG entry. The situation set holds fourteen situations: misses with and without a match, weak and strong hits, an NPC's secrets, near death, two openings, and two dialogs without a roll; a dialog without a roll with a hostile NPC is still missing, since the Brain turns most questions into moves. On that set the unchanged prompt run twice moved the audit total by twelve findings, so a change is adopted only when it beats the spread of its own two runs and of the baseline's. A blind reading by one judge drifts toward one position, so each pair is read twice, the second time with the positions swapped, and a preference counts only when both readings agree.

**9f.3** PLAYER AGENCY's inner-life clause says to describe what a camera could record, including action, beside the clause that limits the character's actions to the stated one.

**9f.4** The action task tells a strong hit in a desperate phase to carry the surrounding darkness.

**9f.5** `fact_budget` allows one or two extra facts, while the dialog task says nothing beyond the question's scope.

**9f.6** `<style>` asks for terse prose, and much of the system prompt still addresses GENRE PHYSICS.

**9f.8** The extraction prompts (`narrator_metadata`, `opening_setup_extractor`), `revelation_check_system`, `blueprint_voicing`, and `recap` were rewritten for Haiku 5.5 in plain sentences with the reason for each rule, and Elvira showed no warning from them; no situation set measures them yet.

**9f.9** Openings slip into the third person ("Zari Kobayashi's eyes open") under the current `task_opening`, which names the player character as the "you" of the narration but does not hold the perspective, as the epilogue task does ("MUST NOT shift to third person"). The narration stays in the second person, as the user prefers.

**9f.10** An evasive NPC tells the player character's past: in almost every measured variant and with both models, Kestrel's intercom line named the character's forgotten contract or old name while her stance allows one fact. Find where that past reaches the narrator in the prompt assembly (NPC secrets, Director guidance) before tuning wording.

**9f.11** A weak hit's cost is still left out now and then, with and without the player-agency line at the end of the action task. A sentence on the result in that line did not help when measured, so the cost belongs in the result block or elsewhere in the action task.

**9f.12** The model is decided: Claude Haiku 5.5 at effort medium for every role, the user's choice of 9 October 2026. It tells the turns better than GLM 5.3 at any playable setting (fewer audit findings, preferred in blind readings, better Elvira scores, no engine warnings) and reaches the first sentence about 7 seconds later per turn. Haiku 5.5 takes no temperature, top_p, or top_k, so the roles differ only in effort and prompt. The substeps above are measured again on Haiku before any tuning; the measuring scripts are in the measuring setup outside the repository.

**9f.13** A full rewrite of the narrator's system prompt and task texts for Haiku 5.5 (plain sentences, a reason per rule, examples in tags, a glossary of the scene tags) was measured and not adopted. The audit favoured it, 79 to 97 findings in four runs against 110 to 125 in six of the unchanged prompt, with half the contradictions and about two seconds less per narration; but the blind reader preferred the unchanged prompt 14 to 3 (11 without agreement), naming objects that act on their own, NPCs with a fact budget of 0 who still tell something, and actions the player did not choose, and Elvira scored all five sessions lower, by 0.6 on average. The condensed GENRE PHYSICS section, which lost the old list of forbidden verb kinds, is the first suspect. What the variants showed, for the one-change-at-a-time work that follows: a checklist at the end of the system prompt softened more misses; an explicit rule against adding steps to the player's action raised player-character findings from about 30 to about 40; a glossary of the scene tags together with stance constraints that describe manner rather than amount lowered the information NPCs give away from about 26 to about 19 findings. The variants are kept in the measuring setup.

### Definition of Done

- Each adopted change was measured on the same situation set against the unchanged prompt, with at least two runs per variant, and beats the run-to-run spread without raising any audit kind beyond it.
- The narrations of every adopted change were read, not only counted.
- Prompt text stays in `prompts/*.yaml`; no prompt text enters Python.
- An Elvira session on the final prompts shows no new engine warnings.
- `docs/ai.md` describes the prompts as they are.
- Quality gate green, no new project-rule violations, one CHANGELOG entry with what each change measured.

### Reference patterns

- Narrator system prompt: `prompts/narrator.yaml`; task texts per scene type: `prompts/tasks.yaml`; narrator-facing blocks: `prompts/blocks.yaml`.
- Prompt assembly: `prompt_action.py`, `prompt_dialog.py`, `prompt_shared.py`.
- Director prompt: `prompts/director.yaml`.

---

## Next steps

Sketches, in the order of work; a step gets its definition of done and reference patterns when it becomes NEXT STEP.

Steps 11, 14b, 25, and 26 each plan a Director tool. The Director has one tool, `query_game_state`; whether a planned tool becomes a new one or part of it is decided when the step becomes NEXT STEP.

### 9d — Generators

Entity creation through the entry point step 9a built: `mechanics/generation.py` → `generate(game, category, context)`, whose categories are registered in `engine/generation.yaml` and dispatched through `_GENERATORS`, with `fact` as the first category. Step 9d builds the framework for entity categories, the location and settlement categories, and moves NPC naming behind an npc category; step 10 adds the encounter category and the weighting of location tables by the setting's atlas, and step 11 widens the npc category with tiers. An entity category returns a `GeneratedEntity`: the category plus the rolled table results, keyed by the role each table plays in that category.

Two decisions open the step and are taken with the user before building. First, when each category fires: a fact fires because the Brain names it, while the candidates for an entity are a move to a place the world state does not know yet, the Brain naming a new place or person the action depends on, and an altered or interrupt scene. Second, how `generate` types its context and result across categories: a union, or one typed function per category behind the registry.

**9d.1** Categories location and settlement registered in `engine/generation.yaml`, each with a callsite in play where the first decision puts it, and npc for the oracle-rolled name (9d.5). Step 10 adds encounter; steps 11, 25, and 26 widen npc and add waypoints and sites.

**9d.2** An oracle accessor that takes a table's format from setting yaml instead of branching on setting names: Starforged's flat d100 tables, classic's tables, and Delve's theme plus domain for the sites of step 26. Sundered Isles' cursed variants come with the cursed die (step 28.2); until then the accessor reads its standard tables.

**9d.3** Per-category oracle paths in setting yaml as a mapping keyed by category name, read with `get_raw` because the keys are domain data; a registered category without a path in the active setting's parent chain raises KeyError. The parent-chain lookup exists: `datasworn/settings.py` → `SettingPackage.oracle_data_for`, `_resolve_oracle_paths`. Later categories add their tables to this mapping rather than new fields on `OraclePaths` (steps 11 and 14b), and when NPC naming moves behind the npc category, `oracle_paths.names` moves into its entry.

**9d.4** Generated content reaches the narrator as a `<generated>` tag. The setting's `vocabulary.substitutions` reach the narrator today as instructions in the vocabulary block (`prompt_blocks.py`), not as replacements, and their values are descriptions ("starship — worn, patched") that would read oddly inside an oracle result; the step decides whether those instructions already cover generated content or whether a substitution needs a form that can replace a word in place. No post-hoc check.

**9d.5** NPC naming goes through the npc category. Chained oracle tables go through `datasworn/cascade.py` → `roll_oracle_cascade`, which already serves threat naming; the step gives it a callsite through a category, with the npc category as the candidate. If no 9d category rolls a chained table, that callsite moves to the encounter category of step 10.

**9d.6** Tests: smoke with stub oracle data, the registry and the yaml list stay equal (as `tests/test_fact_resolution.py` checks for `fact`), a missing path raises. If generated entities are persisted, the save format breaks.

Definition of done, as written when the step was NEXT STEP:

- Location, settlement, and npc are registered in `engine/generation.yaml` and dispatched by `generate`; an unknown category or a missing oracle path raises.
- Each category fires where the opening decision puts it, with a callsite in play.
- Oracle paths per category live in the setting yaml; no Python branches on setting names.
- Generated content reaches the narrator as `<generated>`, with the vocabulary decision of 9d.4 applied.
- Generation reads the world state it lands in, as the design document asks (no prosperous trading post in a region at war): each category names the game-state inputs that weight its tables, the way a fact type names its inputs in `engine/fact_resolution.yaml`.
- `datasworn/cascade.py` → `roll_oracle_cascade` has a callsite through a category, or 9d.5's move to step 10 is recorded.
- The entry "Locations and settlements are narrated, not generated" leaves `docs/divergences.md`.
- ARCHITECTURE.md ("Engine-resolved fiction") and `docs/mechanics.md` say what is generated and when.
- An Elvira run shows `<generated>` tags in play and no new engine warnings.
- Quality gate green, no new project-rule violations, one CHANGELOG entry.

Reference patterns:

- Entry point and registry: `mechanics/generation.py` → `generate`, `_GENERATORS`; `engine/generation.yaml`.
- A generated result as a prompt block: `prompt_shared.py` → `_facts_block`, templates in `prompts/blocks.yaml`.
- Parent-chain oracle lookup: `datasworn/settings.py` → `SettingPackage.oracle_data_for`.
- Cascade rolls: `datasworn/cascade.py` → `roll_oracle_cascade`, used today by threat naming.

### 9e — Open findings from Elvira runs

- Check against a run whether the coverage tracker still misses NPC introductions that the metadata extraction reports.
- The metadata extraction's identity reveals for unnamed NPCs are rejected for zero word overlap, and a stub NPC is created instead.
- The metadata extraction has named an NPC id that does not exist (`npc_details: could not find NPC 'npc_5'`).
- After a chapter transition a returning NPC ("Maren Silk") and a new NPC of almost the same name ("Maren") can stand side by side, since returning NPCs are merged by exact name only.
- The scene can tell the narrator through a `<fact>` that an NPC is not within reach while the same NPC is the scene's `<target_npc>`; both models then let the NPC speak. Settle presence once, so the fact and the target agree.
- The Director's final JSON answer breaks now and then: a stray control character inside a string, a run to the 8192-token limit, or its reasoning's `"..."` placeholders copied into the answer. The failure warning shows how the JSON began. First check whether Together constrains that call's JSON at all.

### 9g — Test fixtures through the real creation path

Fixtures made through the real character-creation path instead of hand-built states, since hand-built fixtures have hidden real bugs more than once (a roll bonus that never applied, momentum burns that overwrote the previous turn, progress marks that never reached a track); the tests that still build a `GameState` by hand move over one file at a time.

### 9h — Principle audits

The audits of AUDIT.md, one session per principle or submodule as it prescribes, in this order: principles 2 and 4, which are mechanical, then principles 3, 5, and 1 per submodule. Every finding is fixed in its session or becomes a substep here. Waiting for the audit to classify:

**9h.1** `game/turn.py` → `_sanitize_brain_output` turns an action-roll move with stat `none` into a dialog turn instead of `call_brain` refusing the answer; the tests treat `world_shaping` without a stat as dialog on purpose (principle 3).

**9h.2** `mechanics/tracks.py` → `roll_oracle_answer` returns an empty answer when the game has no setting or the setting fewer than two action-theme paths, and `find_progress_track` returns None for a target track of another type, which plays a progress roll on zero boxes (principle 3).

**9h.3** `game/chapters.py` → `_reset_chapter_mechanics` empties the tracks, threats, impacts, assets, threads, and lists that `_restore_chapter_mechanics` copies straight back from the chapter summary, a round trip that amounts to a copy. Those snapshot fields of `ChapterSummary` have no other reader, so ending the round trip removes them as well and breaks the save format. `_prepare_npcs_for_new_chapter` tests the same status twice (principle 3).

**9h.4** Dataclasses carry defaults against the rule as CONTRIBUTING.md states it ("Domain config keys raise on a miss, and dataclass fields have no defaults"): about two hundred defaults that are not empty collections, in 43 classes, concentrated in `models_story.py`, `models.py`, `models_base.py`, `datasworn/moves.py`, `mechanics/move_effects.py`, and `models_npc.py` (for example `KeyedScene.source` and `KeyedScene.bound_entity_id`), beside about seventy empty `default_factory` collections, which the rule allows. The optional fields of `AICallSpec` and the partial classes in `datasworn/settings.py` parse external structures and keep theirs. Each module loses its defaults with every constructor call updated, one module per session; when the last is done, the config-binding scan widens to every dataclass (pass 2d).

**9h.5** The `.get()` scan flags only constant, non-neutral defaults, so `.get("key", variable)` passes unexamined, for example in `web/serializers.py` (pass 4b).

**9h.6** Some `strings/*.yaml` keys are read by prefix (`i18n.py` → `get_disposition_labels`, `get_time_labels`, `get_story_phase_labels`) or built at runtime (`succession.legacy_track_*` in `web/serializers.py`), so a strings scan needs to know those prefixes (pass 5b).

**9h.7** For every AI-call carve-out, where its failure becomes visible: a caught failure plays on silently unless Elvira or the log shows it (principle 3).

**9h.8** Every field of `mechanics/move_effects.py` → `OutcomeResult` has a reader in the production path, not only in tests: results that were computed but never applied have hidden faults before (progress marks that never reached a track, a position factor that never fired, and `clock_fills`, step 9k) (principle 5).

### 9i — Revelations settled by the engine

Today the blueprint's revelations reach the narrator as `<revelation_ready>`, and a separate AI call (`call_revelation_check`) judges afterwards whether the prose contained one, which is the kind of post-hoc validator `docs/divergences.md` rules out. Instead the engine decides when a revelation lands (its scene range, or a keyed scene) and hands it to the narrator as a mandatory element, like a `<consequence>`, and marks it revealed at once; the `revelation_check` role, its prompt, schema, and cluster entry go. Measure with Elvira how often the narration carries the revelation before and after.

### 9j — Rules conformance: classic and the Adventure Crafter

The register of deliberate departures is `docs/divergences.md`. Already checked against the books: the action roll, momentum, Endure Harm and Endure Stress, Pay the Price, every match clause, chained and oracle moves, progress, legacy tracks and experience, connections, Mythic's fate check, fate chart, scene test, chaos factor, event focus, lists, and meaning tables, the Adventure Crafter's tables, theme priority, and turning points, Blades clock sizes, asset and connection adds, classic experience by vow rank, and Draw the Circle's boasts.

**9j.1** In classic Ironsworn, wounded and shaken no longer block recovery; classic asks only for health or spirit above 0, and the rule stays for Starforged and Sundered Isles.

**9j.2** Classic's bonds special track: Forge a Bond marks it, and Write Your Epilogue (step 13b) rolls it.

**9j.3** The Adventure Crafter's theme translation lets the adventure's tone pick a theme for the blueprint.

**9j.4** The individual words of the oracle and meaning tables are checked against the books.

**9j.5** Death through Face Death, as the rulebooks have it (the user's decision). The game no longer ends because health and spirit are both 0 (`game/finalization.py` → `_update_crisis` keeps only the crisis status). Harm or stress taken at 0 goes through Endure Harm or Endure Stress, and a miss at 0 marks an impact the move offers while one is free (a fixed choice for the register) or, when none is free, rolls the move's Datasworn table (`<setting>/oracles/moves/endure_harm` and `endure_stress`). A result that names Face Death, Face Desolation, or Forsake Your Vow starts that move through the engine, as an engine trigger. The dying result (Heal within an hour or two, or Face Death) needs a deadline, a clock or a keyed scene, decided in the step. Whether harm from Pay the Price and from miss consequences should itself be rolled through Endure Harm, as the rulebooks do, is checked against the books first. The register entry "Game over when health and spirit are both 0" leaves `docs/divergences.md`; Elvira's `near_death` scenario follows the new path.

**9j.6** Threats and Forsake Your Vow as the books have them. Advance a Threat is rolled on its Delve table when the character gives ground to a threat through inaction, failure, or delay; which misses count, and whether the autonomous tick stays as the engine's reading of delay, is checked against Delve first. A full menace track starts Forsake Your Vow as an engine trigger, with classic's spirit cost by the vow's rank through Endure Stress, and Starforged's choice of costs as a fixed choice for the register. The register entries "Threats advance by engine rule, not by Advance a Threat" and "A full menace track forsakes the vow at a fixed cost" leave `docs/divergences.md`.

Ability effects other than adds belong to step 18; outcomes where the player would choose a cost are a recorded divergence.

### 9k — Scene challenges

The scene challenge of Starforged and Sundered Isles is configured but unreachable. Begin the Scene has no roll, so `tools/builtins.py` → `available_moves` keeps it from the Brain and its entry in `track_creating_moves` never fires; without a scene-challenge track, `engine/move_availability.yaml` never offers the scene-challenge versions of Face Danger and Secure an Advantage or Finish the Scene; the `fill_clock` effect of their misses is computed into `OutcomeResult.clock_fills` and read by nothing; and no tension clock exists to fill.

**9k.1** Begin the Scene becomes a formal move: `available_moves` lets through the moves without a roll that a yaml list names as formal moves, with their category and outcome in the same commit, as "Categorisation follows implementation" requires. The Brain names the objective as the track's name and picks the rank the move gives for the situation: troublesome with a clear advantage, dangerous when ready to act, formidable when unprepared or outmatched.

**9k.2** A turn for a formal move without a roll: the state changes (the scene-challenge track and a four-segment tension clock linked to it, whose creation spawns keyed scenes like every clock) and the narrator tells it without dice.

**9k.3** `fill_clock` fills the tension clock of the active scene challenge; what a full tension clock does follows the book, checked first.

**9k.4** The engine's own rule that the ordinary Face Danger and Secure an Advantage mark scene-challenge progress (`scene_challenge_progress_moves` in `engine/track_moves.yaml`, `game/action_resolution.py` → `_maybe_mark_scene_challenge`) goes, since Starforged uses the scene-challenge versions of those moves, and with it the register entry "Ordinary moves mark scene-challenge progress".

**9k.5** A test plays a scene challenge through the real path from Begin the Scene to Finish the Scene and checks that misses fill the tension clock; an Elvira scenario starts one.

### 10 — Location and encounter generators

**10.1** The location and settlement categories of step 9d weighted by location properties and the world state, with the setting's atlas tables (10.6).

**10.2** The encounter category, registered in `engine/generation.yaml` here, weighted by location properties, active threats, and chaos; oracle for structure, AI for description. Weights in `engine/encounter_weights.yaml` (new).

**10.3** Prompt budget: `<generated>` tags replace unstructured invention, net near zero.

**10.4** Encounter output reaches the Brain as structured data through the existing state path; couples forward to steps 12 and 25.

**10.5** Tests.

**10.6** The setting's own tables feed these generators: the atlas regions of classic and Sundered Isles for locations; the Datasworn NPC entries (classic ironlanders, firstborn, animals, beasts, horrors; Delve and Starforged entries), Starforged creatures and starships, and Delve monstrosities for encounters.

If the user buys the Location Crafter (Word Mill Games, under the same CC BY-NC license as Mythic), its tables join step 10 as data for areas where the setting has no location tools of its own; until then step 10 uses the setting's oracles only.

### 10b — Campaign launch from the setting's oracles

The opening scene and the character's start come from the setting's launch tables instead of the narrator's invention: Starforged's inciting incident and background assets, and Sundered Isles' getting-underway tables (create your character, take command, chart your course). Starforged's starship history and quirks belong with the ship in step 19.

### 11 — NPC generation with tiers

**11.1** Tier 1 (throwaway): demeanor, name, and disposition rolled from oracles, no AI call, with the setting's character oracles (Starforged first look, initial disposition, role, goal, revealed aspect; classic role, goal, descriptor), and identity and descriptors from the Adventure Crafter's character-crafting tables (`mechanics/adventure_crafter.py` → `roll_character_traits`, whose `CharacterTraits` then leaves the orphan-symbol carve-out). The demeanor and disposition tables join the npc category's entry in the per-category oracle-path mapping of step 9d.3, beside the name tables; a missing path raises KeyError. The narrator receives the rolled values as structured prompt context.

**11.2** Tier 2 (recurring): full AIMS plus a goal clock, the AI writing only the AIMS. The Director generates them: it reads the tier-1 base and the active threads through its game-state tool, then writes the AIMS through its JSON schema; always-relevant context (current location, faction state once step 14 lands) is prompt-injected.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new), default three interactions in five scenes, through a DB query.

**11.4** A `tier` field on NpcData as a config-key string, not a Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed rolls; AIMS generation fires only on promotion; missing tier-1 oracle paths raise KeyError.

### 11b — NPC exits and retirement

An idea from EdgeTales: reimplement it, do not port code, and credit EdgeTales in the CHANGELOG entry that lands it.

**11b.1** Exit tracking. NPCs who walk out of a scene can be pulled back next scene by the activation bonus without narrative reason. The narrator_metadata extractor reports `exited_npc_ids` (the same pattern as `deceased_npcs`); `NpcData` gets an absent-until-scene value (the save format breaks); activation scores the NPC zero while absent unless the player names them or the Brain targets them; chapter start clears the value. Tests for exit, suppression, the player-name override, and the chapter reset.

**11b.2** Stale retirement. An active NPC with an empty connection track and no new memory for N scenes (yaml) moves to background; reactivation already exists. Guard against retiring an NPC in the scene they reappear.

### 11c — NPC-to-NPC memories in the prompt

An idea from EdgeTales: reimplement it, do not port code, and credit EdgeTales in the CHANGELOG entry that lands it. `MemoryEntry.about_npc` records what NPCs remember about each other, but the narrator never sees it. The engine selects `about_npc` memories between NPCs present in the scene (one per pair, most recent first, cap in yaml) and injects them as a block whose template lives in `prompts/blocks.yaml`. Stepping stone for step 24.

### 11d — Narrator direction on NPC backstory

An idea from EdgeTales: reimplement it, do not port code, and credit EdgeTales in the CHANGELOG entry that lands it. NPCs draw on their description, agenda, arc, and earlier scenes; where their past is not established, they keep it vague rather than invent family or history. Phrase it as direction, not prohibition, and measure with Elvira before and after, because prompt wording has caused regressions before.

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

This step covers the Datasworn moves of the shipped settings that are neither formal moves in `engine/move_outcomes.yaml` nor covered by another step (expeditions, sites, and Sundered Isles in steps 25, 26, and 28, asset abilities in steps 18 to 20), and wires them following "Datasworn mechanic naming" in `docs/mechanics.md`: a player choice with a structured outcome becomes a formal move; a consequence that fires when a condition becomes true becomes an engine trigger with a direct name.

Group A, formal moves: Forsake Your Vow as the player's own choice (`quest/forsake_your_vow`, today only an engine trigger when a threat's menace fills), `combat/turn_the_tide`, `adventure/aid_your_ally` and `relationship/aid_your_ally` (needs the NPC-action context of step 11), `relationship/write_your_epilogue` (couples with the existing retire flow), `failure/learn_from_your_failures`, `threat/take_a_hiatus`, and the progress-mark moves `legacy/advance`, `legacy/earn_experience`, `quest/advance`, `quest/reach_a_milestone`.

Group B, engine triggers: `mark_failure_on_miss` (`failure/mark_your_failure`), `face_setback_at_min_momentum` (`suffer/face_a_setback`, when momentum would drop below -6), `mark_supply_depletion` (`suffer/out_of_supply`), `face_defeat_on_objective_loss` (`combat/face_defeat`). The existing `advance_menace_on_miss` and `pay_the_price` already follow this pattern.

Group C, covered elsewhere or deliberately not wired: `legacy/continue_a_legacy` (built as succession), `fate/ask_the_oracle` (the engine's own `ask_the_oracle`), `scene_challenge/begin_the_scene` (step 9k), `threshold/overcome_destruction` (step 28), and the five session moves (a recorded divergence).

Duels: Draw the Circle's boasts are modelled, but the duel opens no combat track, so the foe's initiative after a miss or the boast Grant first strike is narrated; wiring the duel into the combat track and position belongs here.

**13b.1** Group A in `engine/move_outcomes.yaml` and `engine/move_categories.yaml`, reusing the existing handler patterns (progress mark, momentum shift, special track).

**13b.2** Group B at their callsites: the first three in `mechanics/consequences.py` (MISS resolution, the momentum clamp, the supply-zero check), the fourth where objective state changes. Each emits a tag for the narrator and updates the state. A move that creates a clock calls `spawn_keyed_scenes_for_clock` at its callsite, as every clock-creation site does.

**13b.3** Per-trigger config (failure-track length, setback redirect, supply-depletion impacts) in the relevant `engine/*.yaml`.

**13b.4** Triggered events reach the narrator as prompt-injected tags (`<failure_marked>`, `<setback>`, `<supply_depletion>`, `<defeat_faced>`).

**13b.5** Tests: each formal move through the move-outcome pipeline, each trigger under its exact condition, `advance_menace_on_miss` as regression.

Done: every move in groups A and B is wired, and `docs/mechanics.md` names the new engine triggers.

### 13c — Foe actions and plot twists from oracles

What a foe does in a fight comes from the setting's combat-action oracle (classic turning point combat action, Starforged and Sundered Isles misc combat action, Delve combat event) instead of the narrator. A new track's rank in classic comes from the challenge-rank oracle when the player names none, instead of the Brain's guess. Classic's major plot twist joins the turning-point sources. Each result reaches the narrator as a structured tag.

### 14a — Faction data model

**14a.1** FactionData dataclass: name, goal, tenets, members (NPC ids), and its standing toward the other factions (allied, rival, or hostile), which the design document places in a setting's static layer; required fields; step 16 adds reputation.

**14a.2** `faction_id` on NpcData.

**14a.3** Faction table in the DB; round trip through SerializableMixin.

**14a.4** Tests: round trip of NpcData and FactionData, membership survives save and load.

### 14b — Scheme clocks and chapter-spanning factions

**14b.1** A scheme clock per faction, ticking every N scenes (`engine/factions.yaml` → `scheme_clock_interval`, new); a fill queues a faction event. The creation site calls `spawn_keyed_scenes_for_clock` (`engine/clock_keyed_scenes.yaml` already covers `scheme`).

**14b.2** ChapterSummary gains `factions: list[FactionData]`, through the three-place chapter pattern.

**14b.3** Faction archetypes from Datasworn oracles: a faction category joins the per-category oracle-path mapping of step 9d.3, with its paths in the setting yamls (starforged `factions`, sundered_isles `faction`; classic Ironsworn has none). A setting with factions and no path raises KeyError.

**14b.4** Faction-event tags are prompt-injected for the narrator; the Director gets faction context for NPC reflections (see the note on Director tools above).

**14b.5** Tests: scheme clocks tick, faction events queue, snapshot and restore across a chapter boundary.

### 14c — Clock and threat pressure in narrative direction

An idea from EdgeTales: reimplement it, do not port code, and credit EdgeTales in the CHANGELOG entry that lands it. The narrator only learns about a clock when it fills, while the design document names clock states and threat levels as sources of narrative intensity. The engine computes a pressure tier from the fullest active threat or scheme clock and the highest threat menace (thresholds in engine yaml) and feeds it into the existing intensity derivation; no numbers or clock names reach the prompt. Measure with Elvira before and after.

### 15 — Faction prompts and status

**15.1** Faction context for activated NPCs in the prompt (about 15 tokens per NPC), budget in `engine/factions.yaml`.

**15.2** `<faction_event>` tag on a scheme-clock fill (about 30 tokens), template in `prompts/blocks.yaml`.

**15.3** `/factions` status command in narrative form, strings in `strings/*.yaml`.

**15.4** Tests.

### 16 — Faction reputation and NPC loyalty

**16.1** Player reputation per faction (hostile, neutral, allied); an extreme overrides personal bond in the stance resolver. Thresholds in yaml.

**16.2** NPC loyalty derived from faction bond against player bond through connection tracks; no new NpcData field.

**16.3** The reputation field on FactionData reserved in 14a.1.

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

Starforged's starship history and quirks (campaign launch oracles) are rolled when the command vehicle is created.

### 20 — Asset rollout per setting

One session per setting, every Datasworn asset working through the step 18 pipeline: **20.1** Starforged, **20.2** Classic, **20.3** Delve, **20.4** Sundered Isles. Classic's rituals bring the mystic-backlash oracle with them (20.2). An asset that needs a fix gets it in the pipeline, not as a per-setting patch.

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

**25.3** Waypoints as a new step 9d category in yaml.

**25.4** Each waypoint is a scene boundary with a chaos check.

**25.5** About 30 tokens of expedition state prompt-injected while an expedition is active; expedition history for the Director (see the note on Director tools above), the engine's chapter record, and the recap.

**25.6** Tests.

### 26 — Site exploration data model and Delve

**26.1** SiteData (Option C): name, objective, theme, domain, rank, `progress: ProgressTrack`, denizen matrix, discovered features, active dangers. One model for every setting.

**26.2** Theme and domain from Datasworn; Delve has 8 themes and 10 domains with feature and danger tables.

**26.3** Delve's denizen matrix: a d100 per site in four ranges (common, uncommon, rare, unforeseen), boundaries in per-setting config.

**26.4** Delve moves: Discover a Site, Delve the Depths, Find an Opportunity, Reveal a Danger, Locate Your Objective, Escape the Depths; routing config-driven.

**26.5** About 60 tokens of active site state prompt-injected, the three most recent discovered features; the full feature list for the Director (see the note on Director tools above).

**26.6** Tests.

**26.7** Delve's prepared sites (20 in the data) as ready sites, and its rarities (62) with Wield a Rarity (`rarity/wield_a_rarity`).

### 27 — Sites for Starforged and Sundered Isles

**27.1** Starforged derelicts, precursor vaults, and location themes as site configurations, no Python.

**27.2** Sundered Isles exploration as site configurations.

**27.3** Tests.

Starforged's anomaly-effect oracle goes with vaults and anomalies.

### 28 — Sundered Isles specifics

**28.1** Ship mechanics (command vehicle with modules, condition track, repair) through the step 18 and 19 asset pipeline.

**28.2** Cursed die. The Datasworn texts that mention it, all in the Chattering Skull asset, describe an extra ten-sided die added to the roll with an effect on a 10; check the Sundered Isles rules for when it is rolled at the start of this step, before designing it. The existing `cursed` impact in `engine/impacts.yaml` is a separate mechanic.

**28.3** Data config: naval encounters, treasure, the 16 Sundered Isles oracle categories, exploration.

**28.4** Tests.

Sundered Isles' misc tables join here: interlude scene, sea-battle features, ship damage, magnitude, local seas.

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

Standard, Mid-Chaos, Low-Chaos, and No-Chaos, each with its own fate chart and fate-check modifier table (`mythic_gme_2e.json` → `chaos_variants`). `fate.chaos_mode` required in config. Mythic's prepared-adventure event focus (with its Adventure Feature entry) replaces the standard focus table while a blueprint is active, since a blueprint is a prepared adventure.

### 33 — Themed element tables

`data/mythic_gme_2e.json` → `meaning_tables.elements` holds 45 themed d100 tables (locations, characters, objects, adventure tone, character traits, creature descriptors, terrain, and more). `mechanics/random_events.py` → `roll_meaning_table` reads only actions and descriptions and raises on an unknown name.

**33.1** `roll_meaning_table` accepts any table in `meaning_tables.elements`, the valid names read at load, the KeyError kept.

**33.2** Six high-use tables first, chosen through `engine/themed_tables.yaml` (new) from event focus, scene type, and location type. The same word twice means greater intensity.

**33.3** The random-event pipeline uses a themed table when one matches the context and actions and descriptions otherwise; the result goes into the existing `<random_event>` tag.

**33.4** Tests.

### 34 — Remaining themed tables

The other 39 tables mapped in `engine/themed_tables.yaml`; config only.

### 35 — Detail check chains

Multi-question fate refinement: each follow-up shifts the odds one step toward the previous answer; at most three, config-driven. Builds on fact resolution (`mechanics/facts.py`): a follow-up is a fact whose odds start from the answer before it, so the chain lands in `WorldState.facts` like any fact.

### 36 — Setting authoring tooling

The design document names tooling for setting authors as a way to lower the barrier: a command that checks a new setting package (its yaml against the Datasworn file, every oracle path it names, its inheritance) and reports what a generator category still lacks, so that adding a setting stays data work.
