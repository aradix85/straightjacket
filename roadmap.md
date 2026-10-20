# Straightjacket — Roadmap

Internal working doc: what gets built next, and in what order. The rules every change keeps and the checks before a commit are in CONTRIBUTING.md, the audit method in AUDIT.md; this document adds only the order of work, the decisions later steps rely on, and what concerns the sessions with the user.

## Always

Every substep and every session ends with both of these before its commit:

- **Read the whole diff back** against CONTRIBUTING.md (Workflow, step 4) and fix what it finds; a green suite does not replace it.
- **Move what is finished to DONE.** A finished step, substep, or session leaves its list and goes, cut short, under DONE, into its step's line while the step stays open. Every session also reads DONE for what can be shorter and cuts it.

## How the roadmap works

The steps are the order of work: NEXT STEP first, then the others in their order, DONE at the bottom. Nothing is worked on outside a step; a new finding becomes a substep of an existing step or a new step in the same commit. One step is one session: read the code, build, test, and delete what the step made obsolete. When reality diverges from the plan, the roadmap changes in the same commit; it never claims what the code contradicts.

The roadmap stays short. A later step is a sketch: its aim, its substeps where they are known, the decisions taken with the user, and the facts a session could not find again in the code, the data, the CHANGELOG, or `docs/`; its definition of done and reference patterns are written when it becomes NEXT STEP. What CONTRIBUTING.md, AUDIT.md, `docs/`, or the CHANGELOG already says is pointed to, not repeated.

Closing a step: the checks of CONTRIBUTING.md pass, the step moves to DONE cut to what a later session needs, its CHANGELOG entry carries the details, the next step becomes NEXT STEP with substeps, a definition of done, and reference patterns, and a decision later steps rely on goes under Decisions. The step's area is read against the source rulebooks and, where it touches the architecture, the design document; a departure goes to `docs/divergences.md`.

## Sessions with the user

- The user writes in Dutch and reads with a screen reader: answers are in Dutch and in plain prose; the repository stays in English.
- A session starts by reading every md file in the root and in `docs/`, of the CHANGELOG only the entries since the last finished step, and continues with NEXT STEP. The design document is not in the repository; README.md links it.
- The user wants as much as possible to come from the source material: where a rulebook table can settle what the narrator still invents, that is the fix to reach for, ahead of new prompt wording, which on Sonnet stayed within the noise (9f).
- The Elvira sessions a step needs are part of the work; a twelve-turn session on Sonnet costs about 55 to 65 cents. Say what a measuring round will cost before starting it; the API spend limit is set in the Claude Console (Settings, Billing). The user keeps runs to what a change needs, no extra ones, since they are costly.
- Elvira runs on the real models again since 9i, the user's choice now that the work builds rather than tidies, but only when a run makes a real difference to the work, and never more runs or turns than that needs: tokens and credit are not to be wasted. A measurement of the engine as it was, when the decision does not hang on it, is no such run. The runs that releases without them left open are not caught up.
- Each finished release is committed and pushed to main.
- The API keys live in the Windows user environment (`ANTHROPIC_API_KEY` for the game and Elvira, `OPENAI_API_KEY` for the judges of the measuring setup); a process started by a tool may need them set in its own environment.
- Outside the repository, in `C:\Users\radix\Documents`: the scan script of the principle-3 audit in `straightjacket_audit` (it takes a submodule name and writes its hit-list beside itself), and the measuring setup for prompt tuning in `mimo_probe`, whose README.md says how to use it.

## Reference patterns

- New AI-call wrapper: `ai/brain.py` → `call_brain` for a call the turn cannot do without, `ai/blueprint_voicing.py` → `call_blueprint_voicing` for one that degrades.
- Director tool: `tools/builtins.py` → `query_game_state` (`docs/ai.md`, Tool calling and prompt injection).
- Strict nested domain lookup: `gamemaster/stance_gate.py` → `resolve_npc_stance`.
- New yaml-backed config section: an entry in its layer's `config.py` `_SIMPLE_SECTIONS` (`gamemaster/config.py`, `ruleset/config.py`, or `engine_config.py` for `engine/`), with its dataclass in the layer's `config_types.py` (required fields, no defaults).
- New template text: `prompts/*.yaml` for AI-facing text, with narrator-facing blocks in `prompts/blocks.yaml`; `strings/*.yaml` for user-facing text; the layer's own yaml folder (`gamemaster/`, `crafters/`, `ruleset/`) for a rule's values, `engine/*.yaml` for engine-internal values that are no rule.
- Subpackage layout: `engine/correction/`.
- Large container split: `gamemaster/config.py` beside `gamemaster/config_types.py`.
- No post-hoc validators of AI output: "No narration validator" in `docs/divergences.md`.

## Decisions referenced by later steps

**Bound to the rules (9h).** The user wants the game bound to the engine and its rules as tightly as it can be: what the rules, the source data, or the story already know is read and acted on or told. A field without a reader is first a missing reader (AUDIT.md, principle 5). Every step that brings source data into play (9j, 9k, 10, 10b, 13b, 13c, 18 to 29) first reads what Datasworn carries for its mechanic (roll instructions, named results, texts) and builds on that rather than on rules of its own; data the engine holds and does not yet read is named in the step it belongs to, or in 13b when no step names it.

**Four layers (9n).** Mythic is the game master over whatever system is played, the Crafter books add content to it, and the ruleset and the setting are separate layers, even while every shipped setting runs on an Ironsworn ruleset, with as little as possible fixed in Python. From 9n on, a step that adds rules (9j, 13b, 18 to 29) builds them in the ruleset, one that adds world content (10, 10b, 27) in the setting, and one that extends Mythic or a Crafter (30 to 35, the Location Crafter of step 10) in its own layer. The user's order: the audits of principles 3 and 5 first, since they shrink what the split moves, then the split, with the audit of principle 1 on the layout it makes. Dependencies point up from the setting, the content every layer reads: the game master builds on it, the crafters on the game master, and the ruleset on both, so another system replaces only the ruleset; the AI calls, prompts, Director, and orchestration sit above all four. Where the game master needs to know something of the system, the system's own rules leave it first, and what remains it asks in its own coarse words, which each ruleset answers from its yaml: how an action went, what kind of action it was, how close an NPC is to the character, how hard pressed the character is and whether in crisis, whether the last action gained an advantage, whether an action gathers information, and how far a danger has advanced; a value the turn already hands along stays a parameter. Threats belong to the ruleset (Delve's menace, ranks, and Forsake Your Vow): the game master and the crafters ask for a new danger in their own words, and each ruleset decides what it becomes, which keeps the most room for other systems. Each layer reads its yaml through its own accessor, so reading against the direction is importing against it, rather than one merged configuration watched by a scan. The user's choices, 9n.

**Config over code (9h).** CONTRIBUTING.md states the rules (config-driven, what belongs together lives together, lean); the user settled the judgment calls of the principle-2 audit: the markup of prompts, the source systems' rule constants, named status groups, and patterns for the AI's words move to yaml.

**When a generator fires (9d).** A place is generated when the Brain moves the character to a place that is neither a generated place nor in the location history: the Brain names the place's kind from the engine's list, and the engine rolls it. An NPC's name is rolled when the metadata extraction registers a new NPC. Altered and interrupt scenes get no generator, since Mythic's random events serve them. Facts go through `generate_fact` and entity categories through `generate_entity`, behind the registry in `gamemaster/generation.yaml`, each returning a `GeneratedEntity` from the role tables its setting names. Later categories (encounters, waypoints, sites, NPC tiers) follow both choices.

**Each spawn source names its own entities** from what it naturally has, as threats and clocks do (`docs/mechanics.md`, Threats and clocks).

**Track-type composition (Option C).** Domain objects that own a progress track (expeditions, sites, thread tracks: steps 25, 26, 31) hold a `progress: ProgressTrack` field plus their own. Rejected: inheriting from ProgressTrack, which would push domain concerns onto a primitive used everywhere, and a registry with a `kind` discriminator, which adds a lookup at every callsite.

**Categorisation follows implementation.** `available_moves` keeps `no_roll` and `special_track` moves from the Brain, so `test_every_implemented_move_has_real_category` checks implemented moves only; a filter change that brings such moves back gives them their category and outcomes in the same commit (9k, 13b).

**Tone (9h).** The player picks a tone at character creation, preset to the setting's `default_tone`; it decides each chapter's story structure (`story.kishotenketsu_probability`) and is the narrator's tone authority.

**Sources bought when a step needs them.** A Word Mill book or Mythic Magazine issue is bought only for a gap the setting's Datasworn data, Mythic 2e, and the Adventure Crafter leave, when a step needs it. A step with candidates starts by reading their product pages with the user; an issue costs $4.95, and a compilation of six $14.95 is chosen when several needed issues fall in the same six. A candidate that fills no gap leaves the list. The Creature Crafter is left out, since it adjusts stat blocks Ironsworn's foes do not have. Candidates, by title in Robin's subject index of Mythic Magazine (linked from Word Mill's Mythic Magazine page), not yet read:

- 9j: #5 Combining Mythic With The Adventure Crafter, #57 Evolve Adventure Settings With The Adventure Crafter, #64 Adventure Crafting Mythic.
- 10: #2 Randomized Location Crafting, #16 Location Crafting Random Cities, #36 Location Based Adventures, #61 The City Crafter, where the Location Crafter and the setting's tables leave a gap.
- 11 and 11d: #8 Generating Compelling Backstories, #41 The Villain Crafter, #63 Rivals, and #45 One-Page Character Crafter only where the Adventure Crafter's character tables fall short.
- 12 and 13: #39 NPC Evolving Motivation Rules, #9 Generating NPC Behavior With Fate Questions, #1 Behavior Checks Simplified, #12 RPG Social Skills With Mythic's Behavior Check, #58 Creating Dialogue With NPCs.
- 14a to 16: #49 The Society Crafter, #63 The Campaign Crafter.
- 14c: #30 Dealing With Solo Adventure Pacing, #32 Dealing With Time Pressure.
- 21 to 24: #24 When Characters Distrust Each Other, #14 Emotional Quest Adventures.
- 25 and 31: #25 Handling Long Journeys In Solo Play, #53 Discovery Prompts.
- 27: #3 Random Dungeon Crawl Generation, only where a site's own tables leave a gap.
- 29: #32 "Gather A Crew" Mythic Adventures, #54 Simplify Playing Parties Solo.
- 32: #34 Fluid Scene Structure, #10 Starting, And Ending, Scenes, against the register entry "Chaos factor per turn".
- 33 and 34: #18 Specialized Meaning Tables, #22 MORE Specialized Meaning Tables!, #40 Meaning Table Collections, beyond the 45 tables of Mythic 2e.
- 35: #56 Detail Check Revisited, #61 Degrees of Fate.

---

## NEXT STEP — 9i: Revelations settled by the engine

A blueprint holds three revelations (`crafters/adventure_crafter.yaml` → `revelations_per_blueprint`), voiced from the first plot points of the Adventure Crafter's turning points (`crafters/blueprint.py` → `_flatten_revelation_seeds`, so mostly from the first act's turning point) or, in a Kishōtenketsu chapter, from the central conflict. Every revelation gets the first act's opening scene as `earliest_scene` (`materialize_blueprint`), so all three are pending from the first scene; the narrator receives the first pending one as `<revelation_ready>` on every turn that is not a miss (`prompt_blocks.py` → `story_context_block`), and after narration a separate AI call judges whether the prose carried it (`ai/brain.py` → `call_revelation_check`, from `game/scene_finalization.py`), which marks it revealed and makes the Director run (`director.py` → `should_call_director`, `revelation_used`). That call is the post-hoc validator `docs/divergences.md` rules out. Instead the engine decides when a revelation lands, tells it as a mandatory element, and marks it revealed itself.

**9i.0** Elvira measures it first: on every turn whose narrator prompt holds a revelation, her judge also answers whether the narration conveyed it, and her report gives how often it did and in which scene each revelation was first conveyed. One run of about twenty turns after 9i.3, through all three acts of the default chapter (`engine/creativity_seeds.yaml` → `scene_range_default`, 1 to 20), shows whether the narration conveys each revelation where it lands. The engine before 9i gets no run: the decision is taken, and that it offers every revelation from the first scene is known from the code (Sessions with the user).

**9i.1** Where each revelation lands, decided with the user: in the act of the turning point it was seeded from, at the moment a trigger of its own fires there, at the latest at the end of that act, and only on a hit, a miss holding it to the next hit even past its act (the user's choice, for a story that follows play while keeping its shape). The three turning points are rolled one per act already (`crafters/blueprint.py` → `assemble_blueprint_seed_from_ac`), but the seeds take the first plot points of the first turning point; they take one per turning point instead, so each act has its revelation, and an act whose turning point gives no seed, or a Kishōtenketsu chapter, takes its revelation from the central conflict as the voicing does today. The trigger is the keyed scene the Adventure Crafter maps to the seed's plot point (`crafters/adventure_crafter.yaml` → `keyed_scene_mapping`), which a turning point spawns at chapter start; a plot point without one has only the act's end. `Revelation.earliest_scene` gives way to what this needs; the save format breaks.

**9i.2** On the turn a revelation lands, the narrator receives it as a mandatory element in the way it receives a `<consequence>`, worded in `prompts/blocks.yaml` and the narrator's task texts, and the engine marks it revealed in the same turn; the Director's revelation trigger reads the engine's mark.

**9i.3** What only the check used goes: `call_revelation_check`, `get_revelation_check_schema`, the role `revelation_check` and the cluster `judgment` it alone uses in `config.yaml`, its prompts in `prompts/brain.yaml`, its entries in `engine/ai_text.yaml`, and the tag `revelation_ready` in `engine/parser.yaml` if the element is renamed. `docs/ai.md` (Roles, Model assignment), ARCHITECTURE.md (What the AI still decides), and `docs/mechanics.md` follow, and the register entry "An AI call judges whether a revelation was told" leaves.

**9i.4** Tests through played turns: a revelation lands where 9i.1 places it, waits as 9i.1 decides, reaches the narrator as a mandatory element, is marked revealed, and makes the Director run that turn.

### Definition of Done

- No AI call judges the narration after the fact, and nothing that only the revelation check read remains.
- Each revelation lands where the engine places it, reaches the narrator as a mandatory element, and is marked revealed by the engine; the register entry leaves `docs/divergences.md`.
- The quality gate is green, and Elvira's run after 9i gives how often the narration conveys a revelation and in which scenes, which the CHANGELOG entry reports.

### Reference patterns

- A mandatory element for the narrator: the `<consequence>` tags (`prompt_shared.py` → `_consequence_tags`) and how the action and dialog prompts place them.
- A beat the engine schedules: keyed scenes (`gamemaster/keyed_scenes.py` → `add_keyed_scene`) and act transitions (`story_state.py` → `check_act_transition`).
- A test through the real path: `tests/_creation.py` → `create_game`, and a turn as `tests/test_integration.py` plays it with `TurnProvider` and `force_result`.

---

## Next steps

Sketches, in the order of work.

Steps 11b, 11c, 11d, and 14c take ideas from EdgeTales: reimplement them, do not port code, and credit EdgeTales in the CHANGELOG entry that lands each.

Steps 11, 14b, 25, and 26 each plan a Director tool. The Director has one tool, `query_game_state`; whether it keeps one at all is decided in 11.0, and whether a planned tool becomes a new one or part of it when its step becomes NEXT STEP. A new tool works through the Director's two calls as they stand: the first offers the tools, the second gets their results as text. A round in which the model reads its results and calls again needs what was removed: the Anthropic adapter's `tool_use` and `tool_result` blocks and a place for the schema instruction when the last message is not the user's (`ai/provider_anthropic.py` and `ai/api_client.py` before commit 0514fd6), and the id of each tool call (`ai/provider_base.py` → `ToolCall`). A tool with parameters needs the schema built from its type hints and the check of the model's arguments (`tools/registry.py` and `tools/handler.py` before release 2026.10.18.8).

### 9j — Rules conformance: classic and the Adventure Crafter

**9j.1** Which gains a marked condition blocks, per ruleset. In Starforged and Sundered Isles a meter whose condition is marked rises only through the move that clears it, while the engine checks only in Endure and the recovery moves, so Sojourn's gains still raise it. Classic's move texts ask only for the meter above 0, but its Datasworn rules text (`rules.impacts.conditions`) says a condition blocks its track; which holds is settled first. The register entries "Classic Ironsworn borrows one Starforged impact rule" and "Marked conditions block only Endure and the recovery moves" leave.

**9j.2** Classic's bonds special track, which the campaign holds since 9n.2c: Forge a Bond marks it, and Write Your Epilogue (13b) rolls it. Today classic's Forge a Bond marks nothing on a hit (`relationship/forge_a_bond` in `ruleset/move_outcomes.yaml`).

**9j.3** The Adventure Crafter's theme translation lets the adventure's tone pick a theme for the blueprint.

**9j.4** The words of the oracle and meaning tables are checked against the books.

**9j.6** Advance a Threat is rolled on its Delve table when the character gives ground to a threat through inaction, failure, or delay; which misses count, and whether the autonomous tick stays as the engine's reading of delay, is checked against Delve first. A threat a random event starts takes no category from Delve's Category table yet. Forsake Your Vow (`ruleset/tracks.py` → `forsake_vow`) costs classic's spirit by the vow's rank and takes Starforged's choice of costs as a fixed choice. The register entries "Threats advance by engine rule, not by Advance a Threat" and "Forsake Your Vow costs a fixed amount of spirit" leave.

**9j.7** The Adventure Crafter's Meta plot points take effect. A Meta result is now a hit that does nothing, and `crafters/meta_plot_points.py` → `dispatch_meta`, its seven handlers, and the Characters List template (`crafters/adventure_crafter.py` → `lookup_characters_template`) have no production caller (an orphan-symbol carve-out in `tests/test_project_rules.py` until this step). Each handler is checked against the book first; Character Returns without an exited character needs a name from the npc generator, the handlers take the turning point's random generator, and one that needs the active plotline takes it where `roll_turning_point` holds it. The register entry "Meta plot points have no effect" leaves.

**9j.8** Make a Connection's weak hit brings a complication or cost, as the move says, following the `complication` effect of Gather Information and Compel.

**9j.10** Two labels the narrator receives read wrong, found by 9p.1's tests on the real data: a marked impact reaches the consequence tags of a dialog turn, the metadata call, and the engine's memories by its key (`mark permanently_harmed`, `consequence_labels.mark_impact` in `engine/ai_text.yaml`), where the sentence an action turn gets already uses its label; and classic's Pay the Price rows end in a period, so a result made worse reads `A new danger or foe is revealed., made worse` (`ruleset/move_effects.py` → `roll_oracle_result`).

Ability effects other than adds belong to step 18; outcomes where the player would choose a cost are a recorded divergence.

### 9k — Scene challenges

The scene challenge of Starforged and Sundered Isles is configured but unreachable: Begin the Scene has no roll, so `ruleset/move_availability.py` → `available_moves` keeps it from the Brain and its `track_creating_moves` entry never fires; without the track, `ruleset/move_availability.yaml` never offers the scene-challenge Face Danger, Secure an Advantage, or Finish the Scene; the `fill_clock` effect of their misses lands in `OutcomeResult.clock_fills`, read by nothing; and no tension clock exists.

**9k.1** Begin the Scene becomes a formal move: `available_moves` lets through the roll-less moves a yaml list names, with category and outcome in the same commit. The Brain names the objective as the track's name and picks the rank the move gives: troublesome with a clear advantage, dangerous when ready to act, formidable when unprepared or outmatched.

**9k.2** A turn for a formal move without a roll: the state changes (the track and a four-segment tension clock linked to it, which spawns keyed scenes like every clock) and the narrator tells it without dice.

**9k.3** `fill_clock` fills the active tension clock; what a full one does follows the book.

**9k.5** A test plays a scene challenge from Begin the Scene to Finish the Scene through the real path and checks that misses fill the tension clock; an Elvira scenario starts one.

### 9m — Measuring the other prompts

The measuring setup captures narrator calls only. A set of captured calls per prompt, with a judge that checks each answer against its input, comes before any change to the extraction prompts (`narrator_metadata`, `opening_setup_extractor`), `blueprint_voicing`, or `recap`.

### 10 — Location and encounter generators

**10.1** The location and settlement categories weighted by location properties and the world state (no prosperous trading post in a region at war), each naming its game-state inputs as a fact type does in `gamemaster/fact_resolution.yaml`. A generated place takes its name from the setting's name tables (Starforged and Sundered Isles settlement names, classic's quick settlement names) where the player has not named it; the register entry "Places are rolled without the world state, and their names are narrated" leaves.

**10.2** An encounter category in `gamemaster/generation.yaml`, weighted by location properties, active threats, and chaos (`engine/encounter_weights.yaml`, new); oracle for structure, AI for description; its output reaches the Brain as structured data (couples to steps 12 and 25). Of the two code paths that follow a link from one oracle row to another table (`setting/cascade.py` → `roll_oracle_cascade`, `setting/oracle_rolls.py` → `roll_oracle`), the category settles on one.

**10.3** `<generated>` tags replace unstructured invention, at a net prompt cost near zero.

**10.6** The setting's own tables feed the generators: the atlas regions of classic and Sundered Isles for locations; the Datasworn NPC entries, Starforged creatures and starships, and Delve monstrosities for encounters.

**10.7** Perils and opportunities of the place. Starforged's location themes, derelicts, vaults, planets, and space, and Sundered Isles' overland, caves, ruins, and shipwrecks have peril and opportunity tables, which Starforged's Pay the Price names among its suggestions (`oracle_rollable:*/**/peril`). At a generated place a miss takes its worsening from the peril table and a result whose move text offers an opportunity takes it from the opportunity table, each told as a consequence; how a peril relates to Pay the Price is checked against the books first. Classic keeps Pay the Price; Delve's Reveal a Danger comes with step 26. A place keeps the choices its rolls made, not only their text, so a path such as `location_themes/{theme}/peril` resolves on a later turn.

**10.8** The Location Crafter (`data/location_crafter.json` holds its procedure, Special table, texts, and example regions, the last as a measure for the list templates). A generated location or settlement is a region; `generation.place_categories` gains `area`, a part of the current place the Brain names, and a move to a new area rolls a Crafter scene instead of the setting's generator, one element per category, told as structured context (10.3). The region keeps its lists, progress points, shown areas, and their connections on its PlaceRecord. Random rolls Mythic 2e's `meaning_tables` (the book's Complex Question tables are their first-edition form, not copied), its Simple Question goes to fate, and its I Dunno rule is a divergence, since the narrator tells every element. Decided with the user: the Crafter runs only where the ruleset has no procedure of its own (Delve's sites, Starforged's derelicts and vaults, and the expeditions of 25 to 27 keep theirs), and the engine builds the lists without an AI call, from a list template per region kind beside each setting's generators whose positions name a kind or a setting table (Starforged's derelict zone areas, a shared table whose columns have no roll range for some rows, which the loader leaves out, and whose second text column (`text2`) nothing reads yet, Sundered Isles' settlement details and region landmarks, classic's place tables), with what the game knows of the place (NPCs last seen there, its threats and facts) as unique elements. The region's size sets how far down Complete sits, from the setting's table where one exists (Sundered Isles' settlement size, Starforged's settlement population) and from the template otherwise. Where the book leaves striking a unique to judgement, a unique NPC stays on the list while it is alive and in play, and a unique location goes once shown. At a scene's end an NPC met or named in one of the region's areas joins its encounter list, and a move to a named area the lists hold asks fate whether it is there, taking it on a yes without a progress point.

**10.12** Tests, among them fixed-seed Crafter scenes with progress points, each Special effect, Complete, uniques, and a missing table path raising KeyError.

### 10b — Campaign launch from the setting's oracles

The opening scene and the character's start come from the setting's launch tables instead of the narrator's invention: Starforged's inciting incident and background assets, and Sundered Isles' getting-underway tables. The quest starters Datasworn carries with each truth option are candidates for the opening threads.

### 11 — NPC generation with tiers

**11.0** First, with the user: does the Director keep its tool? It takes no parameters, returns the same view whatever the model asks, and was called on every Director run, so by `docs/ai.md`'s own axis it could be prompt data, saving the first of the Director's two calls (about a quarter of its cost) and the tool registry; the design document makes tool calling central (`docs/divergences.md`, Tool calling per data type). The question is whether the Director must choose the data for 11.2, or the engine already knows the promoted NPC and hands it its threads and memories; the user is no longer sure tool calling adds much. If the tool stays, two things it hands over carry nothing yet: a thread's id, which no field of the Director's answer can name, and a clock's owner, `world` and none for every clock until step 12.

**11.1** Tier 1 (throwaway): demeanor, name, and disposition rolled without an AI call from the setting's character oracles (Starforged first look, initial disposition, role, goal, revealed aspect; classic role, goal, descriptor) and the Adventure Crafter's character tables (`crafters/character_traits.py` → `roll_character_traits`, whose `CharacterTraits` then leaves the orphan-symbol carve-out). The tables join the npc category's oracle paths beside the name tables, and the narrator receives the values as structured context.

**11.2** Tier 2 (recurring): full AIMS and a goal clock; the Director writes only the AIMS, from the tier-1 base and the active threads, with always-relevant context (location, faction state once step 14 lands) injected.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new), default three interactions in five scenes, counted from the NPC's memories; a `tier` field on NpcData as a config-key string, not a Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed rolls, AIMS generation fires only on promotion, missing oracle paths raise KeyError.

### 11b — NPC exits and retirement

**11b.1** NPCs who walk out of a scene can be pulled back next scene by the activation bonus without reason. The engine counts an NPC as in a scene only when the narration names it or it is the target (`gamemaster/npc/matching.py` → `present_in_narration`), so a passing mention of someone absent still counts. The extractor reports `exited_npc_ids` (like `deceased_npcs`); `NpcData` gets an absent-until-scene value (the save format breaks); activation scores the NPC zero while absent unless the player names them or the Brain targets them; a chapter start clears it. Tests for exit, suppression, the player-name override, and the chapter reset.

**11b.2** An active NPC with an empty connection track and no new memory for N scenes (yaml) moves to background, but not in the scene they reappear.

### 11c — NPC-to-NPC memories in the prompt

`MemoryEntry.about_npc` records what NPCs remember of each other, but the narrator never sees it, and no caller passes the present NPCs to `gamemaster/npc/memory.py` → `retrieve_memories`, so `npc.about_npc_relevance_boost` never applies. The engine picks `about_npc` memories between present NPCs (one per pair, most recent first, cap in yaml) into a block in `prompts/blocks.yaml`, and passes `present_npc_ids`, the one parameter left under "No parameters for tests", kept for this step. A stepping stone for step 24.

### 11d — Narrator direction on NPC backstory

NPCs draw on their description, agenda, arc, and earlier scenes, and keep an unestablished past vague rather than invent family or history; phrased as direction, not prohibition, and measured with Elvira before and after.

### 12 — NPC goal clocks and autonomous actions

Builds on step 11 and `check_npc_agency` (`pacing.npc_agency_interval`). No clock has an NPC owner today, so its agency tick and the owner rename in `gamemaster/npc/lifecycle.py` → `merge_npc_identity` never run; the goal clock makes `owner_id` an NPC id rather than a name. A state correction retells the session log's clock events that are not `autonomous`, so an agency tick, which the turn's narration does not tell as a clock event, is marked like the scene-end ticks.

**12.1** `goal_clock: ClockData | None` on NpcData, ticked after scene-end bookkeeping on deterministic triggers in `engine/npc_goal_clocks.yaml` (new): bond below N, health below N, scene count.

**12.3** A filled goal clock produces an `<npc_action>` tag, at most one per scene (config), prompt-injected since it is always relevant when present, bounded, and needs no AI selection, from a callable that step 13 swaps (default: meaning table plus templates in `prompts/blocks.yaml`).

**12.4** The Director sets a goal clock on promotion. Either `gamemaster/clock_keyed_scenes.yaml` gains a `goal` type (small priority, full fill only) and the callsite calls `spawn_keyed_scenes_for_clock`, or goal clocks are exempt because their fill is the `<npc_action>`; decided at implementation and recorded in the CHANGELOG.

### 13 — NPC behavior via fate

Fate plus expected behavior derived from AIMS and stance (`mythic_gme_2e.json` → `npc_behavior`): the engine derives the expected behavior, asks a fate question, and interprets the answer, with a move list with cooldown as refinement. It replaces the 12.3 callable; once per scene after scene-end bookkeeping, for NPCs with a goal clock and AIMS, at most one per scene.

### 13b — Unimplemented Datasworn mechanics

Datasworn data the engine holds but does not act on comes here when no other step names it. The Datasworn moves of the shipped settings that are neither formal moves in `ruleset/move_outcomes.yaml` nor covered elsewhere (expeditions, sites, and Sundered Isles in 25, 26, and 28; asset abilities in 18 to 20) are wired by "Datasworn mechanic naming" in `docs/mechanics.md`: a player choice with a structured outcome becomes a formal move, a consequence that fires on a condition an engine trigger.

Group A, formal moves in `ruleset/move_outcomes.yaml` and `ruleset/move_categories.yaml`, reusing the handler patterns: Forsake Your Vow as the player's choice (`quest/forsake_your_vow`, today only an engine trigger), `combat/turn_the_tide`, `adventure/aid_your_ally` and `relationship/aid_your_ally` (needs step 11's NPC-action context), `relationship/write_your_epilogue` (with the retire flow), `failure/learn_from_your_failures`, `threat/take_a_hiatus`, and the progress marks `legacy/advance`, `legacy/earn_experience`, `quest/advance`, `quest/reach_a_milestone`, and Develop Your Relationship without a bond as the player's own move (today only Test Your Relationship's follow-up; its `without_bond` effects are in `ruleset/move_outcomes.yaml`), with the divergence "Develop Your Relationship without a bond comes only from Test Your Relationship" leaving.

Group B, engine triggers at their callsites, each with a tag for the narrator (`<failure_marked>`, `<setback>`, `<defeat_faced>`) and its config (failure-track length, setback redirect) in the relevant yaml: `mark_failure_on_miss` (`failure/mark_your_failure`, in the miss resolution of `ruleset/rolls.py`; Delve's failure track, which Datasworn marks optional, joins the campaign's legacy tracks here, the user's choice), `face_setback_at_min_momentum` (`suffer/face_a_setback`, at the momentum clamp of `ruleset/meters.py` → `adjust_momentum`), and `face_defeat_on_objective_loss` (`combat/face_defeat`). `advance_menace_on_miss`, `pay_the_price`, and Out of Supply already follow this pattern. A move that creates a clock whose type has keyed scenes calls `spawn_keyed_scenes_for_clock`.

Group C, elsewhere or deliberately not wired: `legacy/continue_a_legacy` (succession), `fate/ask_the_oracle` (the game master's own), `scene_challenge/begin_the_scene` (9k), `threshold/overcome_destruction` (28), and the five session moves (a divergence).

Duels: Draw the Circle's boasts are modelled, but the duel opens no combat track, so the foe's initiative after a miss or the boast Grant first strike is narrated; wiring the duel into the combat track and position belongs here.

Tests: each formal move through the move-outcome pipeline, each trigger under its exact condition, and `advance_menace_on_miss` as regression.

### 13c — Foe actions and plot twists from oracles

What a foe does in a fight comes from the setting's combat-action oracle (classic turning point combat action, Starforged and Sundered Isles misc combat action, Delve combat event) instead of the narrator. A new track's rank in classic comes from the challenge-rank oracle when the player names none, instead of the Brain's guess. Classic's major plot twist joins the turning-point sources. Each result reaches the narrator as a structured tag.

### 14a — Faction data model

FactionData with name, goal, tenets, members, and its standing toward the other factions, which the design document places in a setting's static layer; `faction_id` on NpcData and the factions in `GameState`. The save format breaks.

### 14b — Scheme clocks and chapter-spanning factions

A scheme clock per faction that ticks on its own and queues a faction event when full (`gamemaster/clock_keyed_scenes.yaml` already covers `scheme`); factions carry over chapters through the three-place chapter pattern; faction archetypes come from the setting's Datasworn oracles through its generators (`docs/settings.md`; classic Ironsworn has none).

### 14c — Clock and threat pressure in narrative direction

The narrator learns about a clock only when it fills, while the design document names clock states and threat levels as sources of narrative intensity. A pressure tier from the fullest clock and the highest menace feeds the existing intensity derivation, with no numbers or names in the prompt; measured with Elvira before and after.

### 15 — Faction prompts and status

Faction context for activated NPCs, a `<faction_event>` tag when a scheme clock fills, and a `/factions` status command in narrative form.

### 16 — Faction reputation and NPC loyalty

Player reputation per faction, whose extremes override personal bond in the stance resolver, and NPC loyalty derived from faction bond against player bond through connection tracks.

### 18 — Asset mechanics beyond adds

Builds on the enabled abilities and the Brain's `bonus_id` (`ruleset/assets.py`, `ruleset/bonuses.py`): rerolls, extra effects on a hit, condition meters on assets, and choosing which ability an upgrade enables. Tests use real Datasworn assets with ids as character creation stores them.

### 19 — Companion and vehicle assets

Companion health and vehicle condition tracks, with Withstand Damage as a suffer move; Companion Takes a Hit and Withstand Damage roll with the asset's meter, which `ruleset/roll_sources.py` → `roll_source_without_stat` then reads beside condition meters and connection ranks; an `/assets` command; companions and vehicles in `<character_state>`. Withstand Damage at 0 integrity rolls its own table, which the move carries (Sundered Isles' inside its own move). Starforged's starship history and quirks are rolled when the command vehicle is created. Whether battered keeps integrity from recovering is checked against the book first: Datasworn's `prevents_recovery` leaves it empty, since integrity is an asset's meter, and the yaml's claim that it does was never read (found in 9n.2h).

### 20 — Asset rollout per setting

One session per setting (Starforged, classic, Delve, Sundered Isles), every Datasworn asset through the step 18 pipeline; classic's rituals bring the mystic-backlash oracle with them.

### 21 — Relationship event detection

The metadata extraction reports relationship events per NPC (a promise broken, betrayal, sacrifice, a debt owed or repaid, loyalty shown), kept on NpcData for steps 22 and 23.

### 22 — Emotional requests

The engine generates an NPC's request to the player from disposition, bond, and recent events, one per NPC, and the narrator receives it as `<emotional_request>`.

### 23 — Refusals, concessions, relationship effects

The Brain classifies the player's answer to a request; refusals and concessions move bond through the connection track and the stance matrix.

### 24 — NPC-NPC triangles involving the player

Requests and triangles between NPCs, limited to those that involve the player; emotional dynamics between factions stay out of scope (`docs/divergences.md`), since factions act through schemes (steps 14 to 16).

### 25 — Expedition moves and waypoints

An expedition object (Option C) and its moves (Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish, Set a Course), with waypoints as a generator category and as scene boundaries.

### 26 — Site exploration data model and Delve

One site model (Option C) for every setting, with Delve's 8 themes and 12 domains, its denizen matrix, its site moves, its 20 prepared sites, and its 62 rarities with Wield a Rarity. Discover a Site starts the site's track, which today no move can, so Delve the Depths and Locate Your Objective are never offered. Delve the Depths reads its move's tables (`Move.tables`): a strong hit marks progress and finds an opportunity on Find an Opportunity's table; a weak hit rolls the table of the stat it used, whose rows mark progress, find an opportunity, or reveal a danger; a miss reveals a danger. Reveal a Danger then reads the site's theme and domain cards, and the register entry "Reveal a Danger skips the site's cards" leaves.

### 27 — Sites for Starforged and Sundered Isles

Starforged's derelicts, precursor vaults, and location themes, and Sundered Isles' exploration, as site configurations without Python; Starforged's anomaly-effect oracle comes with the vaults.

### 28 — Sundered Isles specifics

Ship mechanics through the asset pipeline of steps 18 and 19, with the ship created at the start, which `creation_flow.has_ship_creation` in `data/settings/sundered_isles.yaml` announces and nothing reads yet; the cursed die, checked against the Sundered Isles rules first (Starforged's `cursed` impact is a separate mechanic), with the cursed versions of its tables, which Datasworn tags (`cursed_version_of`, `curse_behavior`); the setting's own oracle categories and misc tables.

### 29 — Crew mechanics

The Sundered Isles crew and morale system.

### 30 — Player vs PC knowledge

Mythic's four strategies for what the player knows against what the character knows (`mythic_gme_2e.json` → `player_vs_pc_knowledge`), with a knowledge status on random events and NPC secrets.

### 31 — Thread progress tracks and discovery checks

Mythic's thread progress track (Option C) with its phases and Flashpoints, discovery checks through the fate system, and a `thread_phase` keyed-scene trigger. Found in 9n.2e: every thread on Mythic's list is a vow today (only `ruleset/tracks.py` adds threads), so the chapter record's other open threads and the threads a successor keeps (`ruleset/succession.py` → `threads_for_successor`) stay empty until a step adds threads of the story's own, here or in 10b.

### 32 — Chaos factor variants

Mythic's chaos variants, each with its own fate chart, and the prepared-adventure event focus while a blueprint is active, since a blueprint is a prepared adventure.

### 33 — Themed element tables

`gamemaster/random_events.py` → `roll_meaning_table` reads only actions and descriptions; the 45 themed tables in `mythic_gme_2e.json` → `meaning_tables.elements` join random events by context, six high-use tables first.

### 34 — Remaining themed tables

The other 39 themed tables, config only.

### 35 — Detail check chains

Follow-up fate questions whose odds start from the answer before, at most three, built on fact resolution so that the chain lands in `WorldState.facts`.

### 36 — Setting authoring tooling

A command that checks a new setting package (its yaml against the Datasworn file, every oracle path it names, its inheritance) and reports what a generator category still lacks, as the design document suggests for setting authors.

---

## DONE

Finished work in its shortest form; the CHANGELOG has the details.

- **Before 9a.** The four Datasworn settings, Mythic GME 2e, the Adventure Crafter's blueprint, Blades clocks, narration streamed by sentence, strict saves and config, and Elvira.
- **9a — Fact resolution** through Mythic's fate chart (`docs/mechanics.md`, Facts).
- **9b — Chapters as Mythic adventures:** resources and clocks carry over, chaos restarts at 5, and a finished game continues only through succession.
- **9c — Soft misses:** the NPCs present withhold, and agenda, secrets, guidance, and a pending revelation stay out of the prompt.
- **9d — Generators** (`docs/mechanics.md`, Generators).
- **9e — Elvira findings:** NPC identity holds across extraction, renames, and chapters; in dialogs the NPC's fact budget governs.
- **9f — Prompt tuning on Sonnet:** every role on Sonnet 5.5 at effort medium, Elvira on Haiku 5.5 (baseline 6.41 ± 0.14); rewording the narrator stayed within the noise, so the remaining faults are for the engine.
- **9g — Tests through the real creation path** (`create_game` in `tests/_creation.py`).
- **9l — Complications as clocks** (`docs/mechanics.md`, Complication clocks).
- **9j, so far.** Suffering goes through `ruleset/suffer.py`; Endure Harm and Endure Stress are follow-up moves that mark impacts and roll their tables; a dying character has two turns to Heal, and the game ends only at Face Death or Face Desolation, whose weak hit binds an extreme vow (9j.5). A progress roll completes on a weak hit, a miss recommits at the user's choice, and Take Decisive Action counts lower in a bad spot (9j.9).
- **9h — Principle audits:** principles 2 to 5 audited (AUDIT.md, Status), the long clean-ups of principle 2 are 9o; the Brain keeps its hand-written hints, which chose moves better than the book's triggers (30 of 30 against 29 of 30). The substeps are in the CHANGELOG, and 9h.23 became 11.0.
- **9n — Four layers:** the setting, the game master, the crafters, and the ruleset each have a package, a yaml folder, and an accessor, and a scan holds their imports to the direction (ARCHITECTURE.md, The four layers); the game master asks the ruleset only its questions (`docs/mechanics.md`, Game master and ruleset). The ruleset owns what a system decides, from its Datasworn rules and its own yaml, and code outside it names none of its words; dialog and asking the oracle are the game master's own moves, and every Datasworn file is at 0.1.0, pinned to one commit (the user's choices). A setting plays the ruleset its Datasworn file names (`docs/settings.md`, Rulesets). Principle 1 is done, and the code the split wrote or rewrote had the queries of principles 2 and 3 (AUDIT.md, Status).
- **9o — Dataclass defaults and prompt markup:** no dataclass field has a default but an empty collection, held by a scan whose carve-out is the external structures (`tests/test_project_rules.py` → `_check_no_dataclass_defaults`); every tag, label, and marker of a prompt comes from `prompts/*.yaml`, and the player's words are escaped wherever a prompt shows them (SECURITY.md).
- **9p — Test audit:** every test holds what the game does, through a public function, the real creation path, or a turn; turns go through `TurnProvider` with `brain_answer` and openings through `OpeningProvider` (`tests/_creation.py`), and a loader under test reads a temporary file or folder (`tests/_helpers.py` → `change_config`). The audit found and fixed the opening prompt's unreachable crisis branch and the chapter and successor openings that skipped their extraction (9p.6).
- **9q — Elvira reaches what a scenario prepares:** a missed aim is a problem; a scenario fixes the results of its first turns through a seam in Elvira alone, or starts at its moment, such as a game over waiting for a successor, and plays in direct mode only (`docs/elvira.md`, Scenarios). Tested on the mock provider; the scenarios have not run on the real models.
