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
- A session starts by reading every md file in the root and in `docs/`, of the CHANGELOG only the entries since the last finished step, and continues with NEXT STEP. The design document is not in the repository; README.md links it, and the user's repository `aradix85/narrative-rpg-engine` holds it as a pdf (version 2.4), which `pdftotext` reads. It is theory, and the engine is its practice, which may depart from it (the user's words).
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
- New yaml-backed config section: an entry in its layer's `config.py` `_SIMPLE_SECTIONS` (`gamemaster/config.py`, `ruleset/config.py`, or `engine_config.py` for `engine/`), with its dataclass in `gamemaster/config_types.py`, `ruleset/config_types.py`, or `engine_config_dataclasses.py` (required fields, no defaults); the crafters bind their few sections in `crafters/config.py` itself.
- New template text: `prompts/*.yaml` for AI-facing text, with narrator-facing blocks in `prompts/blocks.yaml`; `strings/*.yaml` for user-facing text; the layer's own yaml folder (`gamemaster/`, `crafters/`, `ruleset/`) for a rule's values, `engine/*.yaml` for engine-internal values that are no rule.
- Subpackage with a public API through its `__init__.py`: `engine/correction/`.
- Large container split: `gamemaster/config.py` beside `gamemaster/config_types.py`.
- No post-hoc validators of AI output: "No narration validator" in `docs/divergences.md`.

## Decisions referenced by later steps

**Bound to the rules (9h).** The user wants the game bound to the engine and its rules as tightly as it can be: what the rules, the source data, or the story already know is read and acted on or told. A field without a reader is first a missing reader (AUDIT.md, principle 5). Every step that brings source data into play (9j, 9k, 10, 10b, 13b, 13c, 18 to 29) first reads what Datasworn carries for its mechanic (roll instructions, named results, texts) and builds on that rather than on rules of its own; data the engine holds and does not yet read is named in the step it belongs to, or in 13b when no step names it.

**Four layers (9n).** Mythic is the game master over whatever system is played, the Crafter books add content to it, and the ruleset and the setting are separate layers, even while every shipped setting runs on an Ironsworn ruleset, with as little as possible fixed in Python. From 9n on, a step that adds rules (9j, 13b, 18 to 29) builds them in the ruleset, one that adds world content (10, 10b, 27) in the setting, and one that extends Mythic or a Crafter (30 to 35, the Location Crafter of step 10) in its own layer. The user's order: the audits of principles 3 and 5 first, since they shrink what the split moves, then the split, with the audit of principle 1 on the layout it makes. Dependencies point up from the setting, the content every layer reads: the game master builds on it, the crafters on the game master, and the ruleset on both, so another system replaces only the ruleset; the AI calls, prompts, Director, and orchestration sit above all four. Where the game master needs to know something of the system, the system's own rules leave it first, and what remains it asks in its own coarse words, which each ruleset answers from its yaml: how an action went, what kind of action it was, how close an NPC is to the character, how hard pressed the character is and whether in crisis, whether the last action gained an advantage, whether an action gathers information, and how far a danger has advanced; a value the turn already hands along stays a parameter. Threats belong to the ruleset (Delve's menace, ranks, and Forsake Your Vow): the game master and the crafters ask for a new danger in their own words, and each ruleset decides what it becomes, which keeps the most room for other systems. Each layer reads its yaml through its own accessor, so reading against the direction is importing against it, rather than one merged configuration watched by a scan. The user's choices, 9n.

**Config over code (9h).** CONTRIBUTING.md states the rules (config-driven, what belongs together lives together, lean); the user settled the judgment calls of the principle-2 audit: the markup of prompts, the source systems' rule constants, named status groups, and patterns for the AI's words move to yaml.

**When a generator fires (9d).** A place is generated when the Brain moves the character to a place that is neither a generated place nor in the location history: the Brain names the place's kind from the engine's list, and the engine rolls it. An NPC's name is rolled when the metadata extraction registers a new NPC. Altered and interrupt scenes get no generator, since Mythic's random events serve them. Facts go through `generate_fact`, which returns a `ResolvedFact` from Mythic's fate, and entity categories through `generate_entity`, which returns a `GeneratedEntity` from the role tables its setting names, both behind the registry in `gamemaster/generation.yaml`. Later categories (encounters, waypoints, sites, NPC tiers) follow both choices.

**Each spawn source names its own entities** from what it naturally has, as threats and clocks do (`docs/mechanics.md`, Threats and clocks).

**Track-type composition (Option C).** Domain objects that own a progress track (expeditions, sites, thread tracks: steps 25, 26, 31) hold a `progress: ProgressTrack` field plus their own. Rejected: inheriting from ProgressTrack, which would push domain concerns onto a primitive used everywhere, and a registry with a `kind` discriminator, which adds a lookup at every callsite.

**Categorisation follows implementation.** `available_moves` keeps `no_roll` and `special_track` moves from the Brain, so `test_every_implemented_move_has_real_category` checks implemented moves only; a filter change that brings such moves back gives them their category and outcomes in the same commit (9k, 13b).

**Tone (9h).** The player picks a tone at character creation, preset to the setting's `default_tone`; it is the narrator's tone authority. Since 9i it no longer picks a chapter's structure.

**Other systems later (9i).** The user wants to play other systems later under the same game master, Mythic, with the Adventure Crafter and later the Location Crafter, so that the engine and not the AI decides whatever system is played. What a step builds above the ruleset speaks the game master's words (an action's outcome, not Ironsworn's hit and miss), and step 37 tests the split with a ruleset that is not Ironsworn.

**Each ruleset by its own books (9j).** The user keeps the systems apart, so that another one can take a ruleset's place later: a ruleset's rules come from its own books and their expansions, not from another ruleset's. Threats with a menace track are Delve's, an expansion of classic, so classic advances them by Delve's Advance a Threat; Starforged and Sundered Isles, whose books keep their dangers on campaign clocks, play threats by step 9v. A rule a ruleset lacks, such as a classic bond's closeness, is set per ruleset in its yaml. The user's choice.

**Revelations and Kishōtenketsu (9i).** Kishōtenketsu came from EdgeTales, where an AI wrote the whole blueprint, and skipped the Adventure Crafter; it is gone, so every chapter's plan comes from the Adventure Crafter, flexible and unpredictable as the user wants it. Each act has one revelation from its own turning point, which lands when its keyed scene fires, at the latest at its act's end, on a turn that does not fail, a dialog included (`docs/mechanics.md`, Revelations). The user's choices.

**From EdgeTales to the sources (9r).** The user wants the engine to move as far as it can from what came with EdgeTales to its own systems and the sources. Every rule that decides facts, pacing, or behaviour in the fiction has an origin: a source, an engine rule with its register entry, or EdgeTales without a source, and a rule of the last kind goes to the step whose source replaces it. Technique that decides nothing in the fiction, such as the activation search, saves, streaming, and the correction, stays whatever its origin. A system from EdgeTales does something in play, so it never just goes: in the same step it is replaced, or its work is routed to a system the engine already has (Mythic's tables, lists, fate, and scene test, the Adventure Crafter, the ruleset and its Datasworn data, the engine's facts and time), and it leaves only once that does the work; only what never worked, such as the off-screen death vote, goes without one (the user's words). The user's choice; 9r made the list, and AUDIT.md's principle 6 keeps it.

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
- 32b: the 9j candidates #5 Combining Mythic With The Adventure Crafter and #64 Adventure Crafting Mythic, where Mythic 2e and the Adventure Crafter leave open when an adventure ends.
- 33 and 34: #18 Specialized Meaning Tables, #22 MORE Specialized Meaning Tables!, #40 Meaning Table Collections, beyond the 45 tables of Mythic 2e.
- 35: #56 Detail Check Revisited, #61 Degrees of Fate.

---

## NEXT STEP — 9j: Rules conformance: classic and the Adventure Crafter

Each substep starts by reading its rule in the book (the Datasworn texts, Delve, the Adventure Crafter) and builds what the reading settles; where the engine already follows the book, the CHANGELOG says so and nothing changes. Ability effects other than adds belong to step 18; outcomes where the player would choose a cost are a recorded divergence.

**9j.3** The Adventure Crafter's theme translation lets the adventure's tone pick a theme for the blueprint. Since 9i every chapter's blueprint comes from the Adventure Crafter, so the tone (`story.tones` in `gamemaster/story.yaml`) reaches each one.

**9j.4** The words of the oracle and meaning tables are checked against the books.

**9j.6** What remains of Delve's threats: a threat a random event starts takes no category from Delve's Category table in Delve; a random event aims at a threat half the time; and a vow fulfilled against a threat at half its menace or more gives 2 experience in every setting (`ruleset/legacy.yaml` → `threat_overcome_bonus`, `threat_overcome_threshold`), which may be a Delve rule Datasworn does not hold, so the Delve book is read first. The register entry "Threats meet their end by engine rule" leaves.

**9j.7** The Adventure Crafter's Meta plot points take effect. A Meta result is now a hit that does nothing, and `crafters/meta_plot_points.py` → `dispatch_meta`, its seven handlers, and the Characters List template (`crafters/adventure_crafter.py` → `lookup_characters_template`) have no production caller (an orphan-symbol carve-out in `tests/test_project_rules.py` until this step). Each handler is checked against the book first; Character Returns without an exited character needs a name from the npc generator, the handlers take the turning point's random generator, and one that needs the active plotline takes it where `roll_turning_point` holds it. The register entry "Meta plot points have no effect" leaves.

**9j.11** What remains of classic's outcomes that 9r found departing from its moves: a vow forsaken that was made to a bonded person makes Test Your Bond when they next meet (register "Forsake Your Vow takes fixed costs"); and a classic character starts with three assets of any category (`ruleset/creation.yaml` → `max_paths`, `max_starting_assets`, and `creation_flow.starting_asset_categories` in `data/settings/classic.yaml`). Each is read in the book first.

**9j.12** The Adventure Crafter's procedure as the book gives it: whether its five themes are ranked once each, where the engine's theme roll can repeat one (`crafters/adventure_crafter.py` → `assign_themes`); Choose Most Logical and the plotline list's lines; and the consolidation of a full list in Mythic and the Adventure Crafter, which the engine starts at 25 entries rather than lines (`gamemaster/random_events.yaml` → `consolidation_threshold`). The register entry "The engine chooses the Adventure Crafter's plotline" leaves, or becomes Permanent where the book leaves the choice to the player.

### Definition of Done

- Each substep follows its source as the reading settles it, and the CHANGELOG entry names what each reading found.
- The register entries the substeps name leave `docs/divergences.md`; one stays only where the book leaves the player a choice the engine fixes, then as a Permanent entry with its reason.
- `dispatch_meta` and the Characters List template leave the orphan-symbol carve-out.
- Each rule is tested through the real path, and the quality gate is green. An Elvira run only where a substep changes what the narrator is told (9j.11), with its cost named first.

### Reference patterns

- A special track a move marks: `ruleset/legacy.py` → `mark_legacy`.
- A table a move rolls: `ruleset/move_effects.py` → `roll_move_table`, with the rows `move_table_rows` in `ruleset/move_outcomes.yaml` names.
- A weak hit's complication: the `complication` effect of Gather Information and Compel in `ruleset/move_outcomes.yaml`.
- A test through the real path: `tests/_creation.py` → `create_game`, and a turn with `TurnProvider` and `force_result`.

---

## Next steps

Sketches, in the order of work.

Steps 11b, 11c, 11d, and 14c take ideas from EdgeTales: reimplement them, do not port code, and credit EdgeTales in the CHANGELOG entry that lands each.

The Director has one tool, `query_game_state`; whether it keeps one at all is decided in 11.0, and a step that wants another decides whether it becomes a new tool or part of that one. A new tool works through the Director's two calls as they stand: the first offers the tools, the second gets their results as text. A round in which the model reads its results and calls again needs what was removed: the Anthropic adapter's `tool_use` and `tool_result` blocks and a place for the schema instruction when the last message is not the user's (`ai/provider_anthropic.py` and `ai/api_client.py` before commit 0514fd6), and the id of each tool call (`ai/provider_base.py` → `ToolCall`). A tool with parameters needs the schema built from its type hints and the check of the model's arguments (`tools/registry.py` and `tools/handler.py` before release 2026.10.18.8).

### 9t — Rules conformance: Mythic and Starforged

As in 9j, each substep starts by reading its rule in the book and builds what the reading settles; all were found in 9r.

**9t.1** Mythic: an adventure starts at chaos 5, so the background vow's words stop moving a new game's start (`ruleset/creation.yaml` → `chaos_vow_modifiers`, `game/game_start.py` → `_compute_chaos_start`, the engine's own since 0.36.0); a New NPC event brings a new character, named by the setting's generator, instead of rolling the Characters List (register "A New NPC event draws a known character" leaves).

**9t.2** Starforged's recover moves: Resupply's weak hit costs no momentum but meets a cost or complication first (`recover/resupply` in `ruleset/move_outcomes.yaml`); Sojourn makes two recover moves, one on a weak hit, as automatic strong hits instead of its fixed gains; Test Your Relationship's miss loses the connection, and its strong hit's disposition shift, which came from EdgeTales, is read against the book (register "Make a Connection shifts the NPC's disposition").

**9t.3** Continue a Legacy: each legacy track's roll gives one of the options the move offers, instead of a share of its boxes, and what the successor keeps of the world follows from them (register "A successor inherits by engine rule" leaves). Step 13b's Group C names the move.

**9t.4** A move whose text names its time takes it, such as classic Make Camp's several hours (register "Time of day is the engine's").

### 9u — What the narrator still decides

Rules of the narrator's prompt that came from EdgeTales and decide something in the fiction (9r). Each leaves only with what the engine puts in its place, in the same substep (Decisions, From EdgeTales to the sources), measured with Elvira before and after, since rewording the narrator on Sonnet stayed within the noise (9f).

**9u.1** Emotional carry-through: earlier emotional beats stay in the character's body and perception, a feeling the narrator picks for the player character, against PLAYER AGENCY, INNER LIFE. What the engine holds takes its place: the meters and impacts of `<character_state>`, which the narrator shows in body and perception, and what a beat left behind in the state.

**9u.2** The narrator's time rule (time moves forward, minutes to hours) gives way to the engine's `<time>`, which the narrator follows (register "Time of day is the engine's").

**9u.3** The flags: the final scene's "character falls", which also stands on a despair ending, where the move's own outcome text already reaches the narrator; the crisis flag at health or spirit 0 (`ruleset/meters.yaml` → `crisis_at_zero`), from EdgeTales and with no source; and the meters' zero flags WOUNDED, BROKEN, and DEPLETED, where the Datasworn impacts reach the narrator. Each gives way to what the engine already sends: the move's outcome text for the final scene, and the impacts and the strain the ruleset answers for the crisis and the zero flags. The meter level texts of `engine/narrator_status_descriptions.yaml` are read with them.

**9u.4** The player's wishes appear at most one a scene and never in the opening, as the narrator picks; the engine schedules them instead, as threads on Mythic's list or as keyed scenes.

**9u.5** What the player declares about the world: the `world_shaping` move, an EdgeTales move rolled with wits, heart, or shadow, with +1 momentum on a strong hit and no Datasworn move behind it (`ruleset/engine_moves.yaml`), and the Brain's `world_addition`. A declared fact is settled by Mythic's fate, as the facts of 9a are.

**9u.6** The consequence sentences tell only what the engine decided: `health_heavy` tells of a broken bone or bleeding that no meter or impact tracks (`engine/consequence_templates.yaml`).

**9u.7** Genre physics (nothing outside the genre exists, objects never act) is read against the setting's truths, which can allow what it forbids, such as classic's mysticism and Starforged's precursor vaults.

**9u.8** The one unexplained background detail each scene comes from Mythic's element tables (sounds, smells, objects) with step 33.

### 9v — Threats in Starforged and Sundered Isles by their own books

Starforged has no menace track: its book keeps a looming danger on a campaign clock, by guidelines that Datasworn does not carry (the book's campaign clocks, which a faction's project names), and a scene's danger on a tension clock (9k). The threats the engine starts and advances there by Delve's rules (`ruleset/threats.py`, register entry "Starforged and Sundered Isles play Delve's threats") give way to Starforged's campaign clocks, read in the book first: what starts one, what advances it, and what a full one does. Sundered Isles follows Starforged unless its book says otherwise (Decisions, Each ruleset by its own books).

### 9k — Scene challenges

The scene challenge of Starforged and Sundered Isles is configured but unreachable: Begin the Scene has no roll, so `ruleset/move_availability.py` → `available_moves` keeps it from the Brain and its `track_creating_moves` entry never fires; without the track, `ruleset/move_availability.yaml` never offers the scene-challenge Face Danger, Secure an Advantage, or Finish the Scene; the `fill_clock` effect of their misses and of Face Danger's weak hit lands in `OutcomeResult.clock_fills`, read by nothing; and no tension clock exists.

**9k.1** Begin the Scene becomes a formal move: `available_moves` lets through the roll-less moves a yaml list names, with category and outcome in the same commit. The Brain names the objective as the track's name and picks the rank the move gives: troublesome with a clear advantage, dangerous when ready to act, formidable when unprepared or outmatched.

**9k.2** A turn for a formal move without a roll: the state changes (the track and a four-segment tension clock linked to it, which spawns keyed scenes like every clock) and the narrator tells it without dice.

**9k.3** `fill_clock` fills the active tension clock; what a full one does follows the book.

**9k.5** A test plays a scene challenge from Begin the Scene to Finish the Scene through the real path and checks that misses fill the tension clock; an Elvira scenario starts one.

### 9m — Measuring the other prompts

The measuring setup captures narrator calls only. A set of captured calls per prompt, with a judge that checks each answer against its input, comes before any change to the extraction prompts (`narrator_metadata`, `opening_setup_extractor`), `blueprint_voicing`, or `recap`.

### 10 — Location and encounter generators

**10.1** The location and settlement categories weighted by location properties and the world state (no prosperous trading post in a region at war), each naming its game-state inputs as a fact type does in `gamemaster/fact_resolution.yaml`. A generated place takes its name from the setting's name tables (Starforged and Sundered Isles settlement names, classic's quick settlement names) where the player has not named it; the register entry "Places are rolled without the world state, and their names are narrated" leaves.

**10.2** An encounter category in `gamemaster/generation.yaml`, weighted by location properties, active threats, and chaos (`engine/encounter_weights.yaml`, new); oracle for structure, AI for description; its output reaches the Brain as structured data (couples to steps 12 and 25). Of the two code paths that follow a link from one oracle row to another table (`setting/cascade.py` → `roll_oracle_cascade`, `setting/oracle_rolls.py` → `roll_oracle`), the category settles on one. The narrator's rule that an NPC seen elsewhere is absent until shown arriving lets the narrator bring one in (9r); an arrival becomes the encounter generator's, or a random event's.

**10.3** `<generated>` tags replace unstructured invention, at a net prompt cost near zero.

**10.6** The setting's own tables feed the generators: the atlas regions of classic and Sundered Isles for locations; the Datasworn NPC entries, Starforged creatures and starships, and Delve monstrosities for encounters.

**10.7** Perils and opportunities of the place. Starforged's location themes, derelicts, vaults, planets, and space, and Sundered Isles' overland, caves, ruins, and shipwrecks have peril and opportunity tables, which Starforged's Pay the Price names among its suggestions (`oracle_rollable:*/**/peril`), and Sundered Isles' seafaring has a pair as well. At a generated place a miss takes its worsening from the peril table and a result whose move text offers an opportunity takes it from the opportunity table, each told as a consequence; how a peril relates to Pay the Price is checked against the books first. Classic keeps Pay the Price; Delve's Reveal a Danger comes with step 26. A place keeps the choices its rolls made, not only their text, so a path such as `location_theme/{theme}/peril` resolves on a later turn.

**10.8** The Location Crafter (`data/location_crafter.json` holds its procedure, Special table, texts, and example regions, the last as a measure for the list templates). A generated location or settlement is a region; `generation.place_categories` gains `area`, a part of the current place the Brain names, and a move to a new area rolls a Crafter scene instead of the setting's generator, one element per category, told as structured context (10.3). The region keeps its lists, progress points, shown areas, and their connections on its PlaceRecord. Random rolls Mythic 2e's `meaning_tables` (the book's Complex Question tables are their first-edition form, not copied), its Simple Question goes to fate, and its I Dunno rule is a divergence, since the narrator tells every element. Decided with the user: the Crafter runs only where the ruleset has no procedure of its own (Delve's sites, Starforged's derelicts and vaults, and the expeditions of 25 to 27 keep theirs), and the engine builds the lists without an AI call, from a list template per region kind beside each setting's generators whose positions name a kind or a setting table (Starforged's derelict zone areas, a shared table whose columns have no roll range for some rows, which the loader leaves out, Sundered Isles' settlement details and region landmarks, classic's place tables), with what the game knows of the place (NPCs last seen there, its threats and facts) as unique elements. The region's size sets how far down Complete sits, from the setting's table where one exists (Sundered Isles' settlement size, Starforged's settlement population) and from the template otherwise. Where the book leaves striking a unique to judgement, a unique NPC stays on the list while it is alive and in play, and a unique location goes once shown. At a scene's end an NPC met or named in one of the region's areas joins its encounter list, and a move to a named area the lists hold asks fate whether it is there, taking it on a yes without a progress point.

**10.12** Tests, among them fixed-seed Crafter scenes with progress points, each Special effect, Complete, uniques, and a missing table path raising KeyError.

### 10b — Campaign launch from the setting's oracles

The opening scene and the character's start come from the setting's launch tables instead of the narrator's invention: Starforged's inciting incident and background assets, and Sundered Isles' getting-underway tables. The quest starters Datasworn carries with each truth option are candidates for the opening threads. Found in 9r: today the narrator invents the opening from a task of the fork period (one thing out of place, one NPC present and a second glimpsed, `task_opening` in `prompts/tasks.yaml`), which starts in the morning and gets a threat clock named after the background vow at 1 of 6 (`gamemaster/opening.yaml`, from EdgeTales' opening extraction); the launch tables replace these, the clock with what they give the opening's danger.

### 11 — NPC generation with tiers

**11.0** First, with the user: does the Director keep its tool? It takes no parameters, returns the same view whatever the model asks, and was called on every Director run, so by `docs/ai.md`'s own axis it could be prompt data, saving the first of the Director's two calls (about a quarter of its cost) and the tool registry; the design document makes tool calling central (`docs/divergences.md`, Tool calling per data type). The question is whether the Director must choose the data for 11.2, or the engine already knows the promoted NPC and hands it its threads and memories; the user is no longer sure tool calling adds much. If the tool stays, two things it hands over carry nothing yet: a thread's id, which no field of the Director's answer can name, and a clock's owner, `world` and none for every clock until step 12. 9r widens the question: the Director, from EdgeTales, also decides what happens next (`narrator_guidance`, which the narrator follows), what an NPC should do or feel (`npc_guidance`), and how an NPC sees the player (reflections, with its agenda, instinct, arc, and description), all of which the design document leaves to systems (register "An AI Director steers the story and the NPCs"). Which of these stay with an AI, when the Director runs (every three scenes and on EdgeTales' list of triggers), and when a reflection falls due, which EdgeTales' importance scores time (`emotions/importance.yaml`, `npc.reflection_threshold`; only 18 of their 168 words can be reached by the labels the engine writes), is decided here with the user.

**11.1** Tier 1 (throwaway): demeanor, name, and disposition rolled without an AI call from the setting's character oracles (Starforged first look, initial disposition, role, goal, revealed aspect; classic role, goal, descriptor) and the Adventure Crafter's character tables (`crafters/character_traits.py` → `roll_character_traits`, which then leaves the orphan-symbol carve-out). The tables join the npc category's oracle paths beside the name tables, and the narrator receives the values as structured context. They also replace what EdgeTales gave a new NPC: the default disposition and a first memory by disposition (`npc.default_new_npc_disposition`, `disposition_to_seed_emotion`), with Starforged's initial disposition where the setting has one; the opening extraction's agendas, instincts, and secrets go to 11.2. Found reading the docs against the code: a rename the extraction reports by id renames even an NPC whose name the engine rolled (`gamemaster/npc/processing.py` → `process_npc_renames`), and a full name sharing a word with the narrator's first label, which every rolled NPC keeps as an alias, replaces the rolled name; both are read with the tier-1 names.

**11.2** Tier 2 (recurring): full AIMS and a goal clock; the Director writes only the AIMS, from the tier-1 base and the active threads, with always-relevant context (location, faction state once step 14 lands) injected.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new), default three interactions in five scenes, counted from the NPC's memories; a `tier` field on NpcData as a config-key string, not a Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed rolls, AIMS generation fires only on promotion, missing oracle paths raise KeyError.

### 11b — NPC exits and retirement

**11b.1** NPCs who walk out of a scene can be pulled back next scene by the activation bonus without reason. The engine counts an NPC as in a scene only when the narration names it or it is the target (`gamemaster/npc/matching.py` → `present_in_narration`), so a passing mention of someone absent still counts. The extractor reports `exited_npc_ids` (like `deceased_npcs`); `NpcData` gets an absent-until-scene value (the save format breaks); activation scores the NPC zero while absent unless the player names them or the Brain targets them; a chapter start clears it. Tests for exit, suppression, the player-name override, and the chapter reset. Elvira's check for NPCs that change place unseen (`tests/elvira/elvira_bot/quality_checks.py`) still counts an NPC as named only by a part of its name, not by the engine's `named_in` of 9s, so an NPC the narration names by a whole alias is reported as moved without being shown.

**11b.2** An active NPC with an empty connection track and no new memory for N scenes (yaml) moves to background, but not in the scene they reappear. Found in 9r, all from EdgeTales: retirement above `npc.max_active` (12) weighs closeness three times (`description_dedup.bond_multiplier`), set for EdgeTales' bond of 0 to 4 where closeness now counts 0 to 10 boxes, and the chapter boundary moves an NPC with no bond, at most one memory, and no agenda to background and keeps five memories of every NPC (`gamemaster/chapter.yaml`).

**11b.3** An NPC who dies off screen. The engine records a death only when the narration shows it and the NPC was in the scene (`ai/metadata.py` → `process_deceased_npcs_with_presence_check`), so a death the narration tells as news leaves the NPC alive in the state. EdgeTales' vote for such deaths, from the NPCs' memories, could never fire and went in 9r with the user's consent. An off-screen death comes from an engine source instead, not from the AI: a random event aimed at the NPC, a threat that achieves its goal (Delve's last menace box, 9j.6), a plot point, or the NPC's own goal clock (12); the narrator is told it as a consequence, and an NPC the state holds alive stays alive in the telling (register "The narration decides who dies").

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

Fate plus expected behavior derived from AIMS and stance (`mythic_gme_2e.json` → `npc_behavior`): the engine derives the expected behavior, asks a fate question, and interprets the answer, with a move list with cooldown as refinement. It replaces the 12.3 callable; once per scene after scene-end bookkeeping, for NPCs with a goal clock and AIMS, at most one per scene. Found in 9r: the stance matrix and the information gate are the engine's own since 0.39.0 and stay as engine rules (register "The narrator gets less than the full relational context"), but their closeness bands (`gamemaster/stance_bond_buckets.yaml`, the bond thresholds of `gamemaster/information_gate.yaml`) were set for EdgeTales' bond of 0 to 4 and now read 0 to 10 boxes; the gate filters only the target, so an activated NPC's reflections reach the narrator at any gate, and consolidation can lower a gate, since scenes known count from the oldest memory left. The narrator's rule of an NPC's full emotional range and the Director's `npc_guidance`, both from EdgeTales, are what fate and expected behaviour replace. Found in 9i's Elvira run: a revelation told in a dialog drew a fact of the NPC's own beside it (a ring), past her fact budget; once, so only watched.

### 13b — Unimplemented Datasworn mechanics

Datasworn data the engine holds but does not act on comes here when no other step names it. The Datasworn moves of the shipped settings that are neither formal moves in `ruleset/move_outcomes.yaml` nor covered elsewhere (expeditions, sites, and Sundered Isles in 25, 26, and 28; asset abilities in 18 to 20) are wired by "Datasworn mechanic naming" in `docs/mechanics.md`: a player choice with a structured outcome becomes a formal move, a consequence that fires on a condition an engine trigger.

Group A, formal moves in `ruleset/move_outcomes.yaml` and `ruleset/move_categories.yaml`, reusing the handler patterns: Forsake Your Vow as the player's choice (`quest/forsake_your_vow`, today only an engine trigger), `combat/turn_the_tide`, `adventure/aid_your_ally` and `relationship/aid_your_ally` (needs step 11's NPC-action context), `relationship/write_your_epilogue` (with the retire flow), `failure/learn_from_your_failures`, `threat/take_a_hiatus`, and the progress marks `legacy/advance`, `legacy/earn_experience`, `quest/advance`, `quest/reach_a_milestone`, and Develop Your Relationship without a bond as the player's own move (today only Test Your Relationship's follow-up; its `without_bond` effects are in `ruleset/move_outcomes.yaml`), with the divergence "Develop Your Relationship without a bond comes only from Test Your Relationship" leaving.

Group B, engine triggers at their callsites, each with a tag for the narrator (`<failure_marked>`, `<setback>`, `<defeat_faced>`) and its config (failure-track length, setback redirect) in the relevant yaml: `mark_failure_on_miss` (`failure/mark_your_failure`, at the miss in `game/action_resolution.py`, beside `advance_menace_on_miss`; Delve's failure track, which Datasworn marks optional, joins the campaign's legacy tracks here, the user's choice), `face_setback_at_min_momentum` (`suffer/face_a_setback`, at the momentum clamp of `ruleset/meters.py` → `adjust_momentum`), and `face_defeat_on_objective_loss` (`combat/face_defeat`). `advance_menace_on_miss`, `pay_the_price`, and Out of Supply already follow this pattern. A move that creates a clock whose type has keyed scenes calls `spawn_keyed_scenes_for_clock`.

Group C, elsewhere or deliberately not wired: `legacy/continue_a_legacy` (succession, its options in 9t.3), `fate/ask_the_oracle` (the game master's own), `scene_challenge/begin_the_scene` (9k), `threshold/overcome_destruction` (28), and the five session moves (a divergence).

Duels: Draw the Circle's boasts are modelled, but the duel opens no combat track, so the foe's initiative after a miss or the boast Grant first strike is narrated; wiring the duel into the combat track and position belongs here.

Tests: each formal move through the move-outcome pipeline, each trigger under its exact condition, and `advance_menace_on_miss` as regression.

### 13c — Foe actions and plot twists from oracles

What a foe does in a fight comes from the setting's combat-action oracle (classic turning point combat action, Starforged and Sundered Isles misc combat action, Delve combat event) instead of the narrator. A new track's rank in classic comes from the challenge-rank oracle when the player names none, instead of the Brain's guess. Classic's major plot twist joins the turning-point sources. Each result reaches the narrator as a structured tag. The match hints, an escalation, twist, or boon the narrator invents on a match (`result_match_hint_*` in `prompts/blocks.yaml`, from EdgeTales), take classic's major plot twist and Mythic's plot-twist table (9r). Whether a foe dies at a fight's end follows End the Fight's outcome, where the narration decides it now (register "The narration decides who dies").

### 14a — Faction data model

FactionData with name, goal, tenets, members, and its standing toward the other factions, which the design document places in a setting's static layer; `faction_id` on NpcData and the factions in `GameState`. The save format breaks.

### 14b — Scheme clocks and chapter-spanning factions

A scheme clock per faction that ticks on its own and queues a faction event when full (`gamemaster/clock_keyed_scenes.yaml` already covers `scheme`); factions carry over chapters through the three-place chapter pattern; faction archetypes come from the setting's Datasworn oracles through its generators (`docs/settings.md`; classic Ironsworn has none). Found in 9r, it also settles the clocks that tick by themselves: every world-owned threat clock but a complication ticks with the chance `pacing.autonomous_clock_tick_chance` at each scene's end, from EdgeTales, where the design document asks for every N scenes or for triggers and Blades for downtime; and every clock random events and plot points start has six segments (`clocks.default_segments`), where Blades sizes a clock by how complex its danger is (register "Random events and plot points start dangers and clocks"). Found reading the docs against the code: nothing ticks the progress clock a Move Toward event starts, its name, a Mythic pair, matches no progress track, and its keyed scene at full would hold back what its fill does (`gamemaster/clocks.py` → `resolve_clock_fill`), so `ruleset/tracks.py` → `complete_track_of_clock` never acts; no code makes a scheme clock.

### 14c — Clock and threat pressure in narrative direction

The narrator learns about a clock only when it fills, while the design document names clock states and threat levels as sources of narrative intensity. A pressure tier from the fullest clock and the highest menace feeds the existing intensity derivation, with no numbers or names in the prompt; measured with Elvira before and after. Found in 9r (register "Narrative direction reads the meters and the outcome"): intensity reads health and spirit, tempo the outcome, the player's relation is always caused, and the narrative position comes from EdgeTales' pacing hint (a breather after three intense scenes, action after two calm ones, `gamemaster/pacing.yaml`), never as climax; Mythic's chaos factor and scene type could give tempo and position, and the act's phase the climax. A miss or a weak hit ticks the first threat clock in the list, from EdgeTales, not the clock the consequence concerns; and the Director's rule to work a half-full clock into its guidance becomes the engine's pressure tier.

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

One site model (Option C) for every setting, with Delve's 8 themes and 12 domains, its denizen matrix, its site moves, its 20 prepared sites, and its 62 rarities with Wield a Rarity. Discover a Site starts the site's track, which today no move can, so Delve the Depths and Locate Your Objective are never offered. Delve the Depths reads its move's tables (`Move.tables`): a strong hit marks progress and finds an opportunity on Find an Opportunity's table; a weak hit rolls the table of the stat it used, whose rows mark progress, find an opportunity, or reveal a danger; a miss reveals a danger. Reveal a Danger then reads the site's theme and domain cards, Escape the Depths' weak hit takes its costs, and a miss on Locate Your Objective lets the player go on, so the register entry "Delve's site moves play without a site" leaves.

### 27 — Sites for Starforged and Sundered Isles

Starforged's derelicts, precursor vaults, and location themes, and Sundered Isles' exploration, as site configurations without Python; Starforged's anomaly-effect oracle comes with the vaults.

### 28 — Sundered Isles specifics

Ship mechanics through the asset pipeline of steps 18 and 19, with the ship created at the start, which `creation_flow.has_ship_creation` in `data/settings/sundered_isles.yaml` announces and nothing reads yet; the cursed die, checked against the Sundered Isles rules first (Starforged's `cursed` impact is a separate mechanic), with the cursed versions of its tables, which Datasworn tags (`cursed_version_of`, `curse_behavior`); the setting's own oracle categories and misc tables.

### 29 — Crew mechanics

The Sundered Isles crew and morale system.

### 30 — Player vs PC knowledge

Mythic's four strategies for what the player knows against what the character knows (`mythic_gme_2e.json` → `player_vs_pc_knowledge`), with a knowledge status on random events and NPC secrets. An NPC's secret now comes out at the narrator's pace, never directly and over three or more scenes (`secrets_label` in `prompts/blocks.yaml`, the fork period's rule); like a revelation (9i), it could land by engine rule (9r).

### 31 — Thread progress tracks and discovery checks

Mythic's thread progress track (Option C) with its phases and Flashpoints, discovery checks through the fate system, and a `thread_phase` keyed-scene trigger. Found in 9n.2e: every thread on Mythic's list is a vow today (only `ruleset/tracks.py` adds threads), so the chapter record's other open threads and the threads a successor keeps (`ruleset/succession.py` → `threads_for_successor`) stay empty until a step adds threads of the story's own, here or in 10b. Found in 9r: the thread of the highest weight reaches every action and dialog prompt as `<active_thread>`, with no rule that reads it, and the keyed scenes a threat or scheme clock gets at half are the nearest the engine comes to the Flashpoints.

### 32 — Chaos factor variants

Mythic's chaos variants, each with its own fate chart, and the prepared-adventure event focus while a blueprint is active, since a blueprint is a prepared adventure.

### 32b — A chapter's structure from Mythic and the Adventure Crafter

A chapter's three acts of about twenty scenes (`engine/creativity_seeds.yaml` → `scene_range_default`, `blueprint.act_phases` in `crafters/adventure_crafter.yaml`), with one turning point rolled for each at chapter start, came from EdgeTales, not from a source. Read against Mythic 2e and the Adventure Crafter first: when the books roll a turning point and when an adventure ends; the chapter then follows them, its revelations (9i) staying bound to its turning points, and a departure the reading finds goes to the register. Read beside the register entry "Chaos factor per turn" and step 32. Found in 9i's Elvira run: both revelations landed at their act's end, since their keyed scenes were bond thresholds (6 and 7), which classic then reached only through a bond, which nothing sealed yet; fifteen of the 33 plot points of `keyed_scene_mapping` wait for a bond, at thresholds the engine chose, not the book (register "Keyed scenes are the engine's"). Found in 9r, all from EdgeTales without a source: the act progress shares (`story_state.act_early_share`, `act_mid_share`) and the "nearing conclusion" signal, the completion at the latest `story_state.completion_overrun_scenes` past the last act, which only a blueprint of one act can reach, the aftermath act after a dismissed epilogue, three possible endings, the story-ending blocks of `prompts/blocks.yaml`, the act mood and the story arc the blueprint voicing writes (conflict, antagonist, theme, act titles, goals, moods, and triggers, the last shown to the Director but ending no act), the entity a keyed scene binds when it fires (`KeyedScene.bound_entity_id`, read by nothing, since the fired scene leaves the list), the Director's run at the climax, and the chapter opening's time skip with a new threat that has no ThreatData and one or two new NPCs (`task_chapter_opening`); the epilogue's source is Write Your Epilogue (13b).

### 33 — Themed element tables

`gamemaster/random_events.py` → `roll_meaning_table` reads only actions and descriptions; the 45 themed tables in `mythic_gme_2e.json` → `meaning_tables.elements` join random events by context, six high-use tables first. They also take the place of the creativity seeds, thirty words from EdgeTales' fallback list that the opening and chapter tasks get (`engine/creativity_seeds.yaml`), with the names, locations, and characters tables (9r).

### 34 — Remaining themed tables

The other 39 themed tables, config only.

### 35 — Detail check chains

Follow-up fate questions whose odds start from the answer before, at most three, built on fact resolution so that the chain lands in `WorldState.facts`.

### 36 — Setting authoring tooling

A command that checks a new setting package (its yaml against the Datasworn file, every oracle path it names, its inheritance) and reports what a generator category still lacks, as the design document suggests for setting authors.

### 37 — A ruleset that is not Ironsworn

The user's aim (Decisions, Other systems later): a system that is no Ironsworn plays under the same game master, the Adventure Crafter, and the Location Crafter (10.8). A ruleset package of its own beside the shared layers (`docs/settings.md`, Adding a new ruleset) answers the game master's questions (`gamemaster/questions.py` → `RulesetAnswers`), and what the step finds bound to Ironsworn outside `ruleset/` moves there. Which system, and with which setting, is decided with the user when the step becomes NEXT STEP.

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
- **9j, so far.** Suffering goes through `ruleset/suffer.py`; Endure Harm and Endure Stress are follow-up moves that mark impacts and roll their tables; a dying character has two turns to Heal, and the game ends only at Face Death or Face Desolation, whose weak hit binds an extreme vow (9j.5). A progress roll completes on a weak hit, a miss recommits at the user's choice, and Take Decisive Action counts lower in a bad spot (9j.9). A marked condition keeps its meter from rising outside the move that clears it, as both rulesets' rules texts say (9j.1). A marked impact reaches the narrator by its label, and a result made worse reads `made worse: ` before the row (9j.10). Make a Connection's weak hit and classic Compel's bring a complication or a demand, as Gather Information's does (9j.8). Classic's Forge a Bond seals a bond as a bonded connection at full closeness, marks the bonds legacy track, and aids by classic's +1 (9j.2, the user's choice). In classic every threat advance rolls Delve's Advance a Threat, a threat no vow faces achieves its goal when its menace fills, and a forsaken vow costs spirit by its rank (9j.6, Delve being classic's expansion). Classic's Strike and Clash inflict 1 harm as a mark (the user's choice), a missed vow meets its obstacle and classic's presses on at -2 momentum, and classic's Test Your Bond, offered only with a bond, asks loyalty on a weak hit and clears the bond on a miss; classic Sojourn takes its picks in a fixed order, with one more and +1 on its second roll for a bond that aided it (9j.11, so far, the user's choices).
- **9h — Principle audits:** principles 2 to 5 audited (AUDIT.md, Status), the long clean-ups of principle 2 are 9o; the Brain keeps its hand-written hints, which chose moves better than the book's triggers (30 of 30 against 29 of 30). The substeps are in the CHANGELOG, and 9h.23 became 11.0.
- **9n — Four layers:** the setting, the game master, the crafters, and the ruleset each have a package, a yaml folder, and an accessor, and a scan holds their imports to the direction (ARCHITECTURE.md, The four layers); the game master asks the ruleset only its questions (`docs/mechanics.md`, Game master and ruleset). The ruleset owns what a system decides, from its Datasworn rules and its own yaml, and code outside it names none of its words; dialog and asking the oracle are the game master's own moves, and every Datasworn file is at 0.1.0, pinned to one commit (the user's choices). A setting plays the ruleset its Datasworn file names (`docs/settings.md`, Rulesets). Principle 1 is done, and the code the split wrote or rewrote had the queries of principles 2 and 3 (AUDIT.md, Status).
- **9o — Dataclass defaults and prompt markup:** no dataclass field has a default but an empty collection, held by a scan whose carve-out is the external structures (`tests/test_project_rules.py` → `_check_no_dataclass_defaults`); every tag, label, and marker of a prompt comes from yaml (`prompts/*.yaml`, the engine's texts in `engine/`), and the player's words are escaped wherever a prompt shows them (SECURITY.md).
- **9p — Test audit:** every test holds what the game does, through a public function, the real creation path, or a turn; turns go through `TurnProvider` with `brain_answer` and openings through `OpeningProvider` (`tests/_creation.py`), and a loader under test reads a temporary file or folder (`tests/_helpers.py` → `change_config`). The audit found and fixed the opening prompt's unreachable crisis branch and the chapter and successor openings that skipped their extraction (9p.6).
- **9i — Revelations settled by the engine:** one revelation per act, seeded from its own turning point, lands when its keyed scene fires or at its act's end, on a turn that does not fail, and reaches the narrator as a `<revelation>` it must tell (`docs/mechanics.md`, Revelations); the revelation check, its cluster, and Kishōtenketsu are gone, and a chapter drops the old chapter's Adventure Crafter keyed scenes. Elvira, twenty turns of classic: the revelations of acts 1 and 2 landed at their act's end, in scenes 7 and 14, and both came across; the third act was not reached.
- **9q — Elvira reaches what a scenario prepares:** a missed aim is a problem; a scenario fixes the results of its first turns through a seam in Elvira alone, or starts at its moment, such as a game over waiting for a successor, and plays in direct mode only (`docs/elvira.md`, Scenarios). Tested on the mock provider; the scenarios have not run on the real models.
- **9s — NPCs named by whole names:** a text names an NPC by its name or an alias as whole words, or by a given name that keeps its capital, never by one word of a descriptive alias, which in 9i's Elvira run moved two NPCs along with the player (`docs/mechanics.md`, Memory and activation). Presence, introduction, moving along, opening memories, and activation use the one test.
- **9r — Where each rule comes from:** every rule that decides facts, pacing, or behaviour in the fiction was read against the first commit, EdgeTales of 31 March, the design document, and the books; what came from EdgeTales or the engine without a source went to the step that replaces it (9j, 9t, 9u, 10, 10b, 11, 11b, 13, 13b, 13c, 14b, 14c, 30, 31, 32b, 33) and to the register, and AUDIT.md's principle 6 keeps it so. The design document is theory that gives a rule its aim, not its form (the user's words). Fixed on the way: a lore figure who appears becomes active, an overcome threat is told once, only threat clocks press the position, and the caps on spawned threats and clocks count the open ones; the off-screen death vote from EdgeTales, which could never fire, is gone with its two yaml files (the user's consent).
