# Straightjacket — Roadmap

Internal working doc: what gets built next, and in what order. The rules every change keeps and the checks before a commit are in CONTRIBUTING.md; this document adds only the order of work and what concerns the sessions with the user.

## Always

Every substep and every session ends with both of these before its commit, whatever the step:

- **Read the whole diff back** against the list in CONTRIBUTING.md (Workflow, step 4) and fix what it finds before committing: no new default or parameter for tests, no broad except, no guard against a state that cannot occur, no dead code, nothing copied, nothing illogical, every caller and document updated, and a test that fails without each fix. A green suite does not replace it.
- **Move what is finished to DONE.** A finished step, substep, or session leaves its list and goes, cut short, under DONE at the bottom, into its step's line while the step stays open. Every session also reads DONE for what can be shorter and cuts it.

## How the roadmap works

The steps below are the order of work: NEXT STEP first, then the others in their order, and DONE at the bottom. Nothing is worked on outside a step, and a new finding becomes a substep of an existing step or a new step in the same commit. One step is one session: read the code, build, test, and delete what the step made obsolete. When reality diverges from the plan, the roadmap changes in the same commit; it never claims what the code contradicts.

Closing a step: the checks of CONTRIBUTING.md pass, the step moves to DONE at the bottom, cut to what a later session needs to understand the whole, and gets its CHANGELOG entry with the details, the next step becomes NEXT STEP with substeps, a definition of done, and reference patterns, and a decision that later steps rely on goes under Decisions. The step's area is read against the source rulebooks and, where it touches the architecture, against the design document; a departure goes to `docs/divergences.md`.

## Sessions with the user

- The user writes in Dutch and reads with a screen reader: answers are in Dutch and in plain prose, while the repository stays in English.
- A session starts by reading every md file in the root and in `docs/`, of the CHANGELOG only the entries since the last finished step, and then continues with NEXT STEP. The design document is not in the repository; README.md links it.
- The user wants as much as possible to come from the source material: where a table of the rulebooks can settle what the narrator still invents, that is the fix to reach for, ahead of new prompt wording, which on Sonnet stayed within the noise (step 9f).
- The Elvira sessions a step needs are part of the work; a twelve-turn session on Sonnet costs about 55 to 65 cents. Say what a measuring round will cost before starting it; the API spend limit is set in the Claude Console (Settings, Billing).
- Each finished release is committed and pushed to main.
- On this machine the API keys live in the Windows user environment (`ANTHROPIC_API_KEY` for the game and Elvira, `OPENAI_API_KEY` for the judges of the measuring setup); a process started by a tool may need them set in its own environment first.
- The scan script of the principle-3 audit lives outside the repository in `C:\Users\radix\Documents\straightjacket_audit`; it takes a submodule name and writes its hit-list beside itself.
- The measuring setup for prompt tuning lives outside the repository in `C:\Users\radix\Documents\mimo_probe`: captured situations, the audit, blind-reading, and Elvira comparison scripts, and a README.md that says how to use them.

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

**Tone (step 9h).** The player picks a tone at character creation, preset to the setting's `default_tone` in setting yaml. The tone decides each chapter's story structure through `story.kishotenketsu_probability` and reaches the narrator as its tone authority. Chosen with the user, as a mix of a default per setting and the player's own choice.

**When a generator fires, and how its call is typed (step 9d).** A place is generated when the Brain moves the character to a place that is neither a generated place nor in the location history: the Brain names the place's kind from the engine's list, and the engine rolls it. An NPC's name is rolled when the metadata extraction registers a new NPC. Altered and interrupt scenes get no generator, since Mythic's random events already serve them. A fact goes through `generate_fact` and an entity category through `generate_entity`, both behind the registry in `engine/generation.yaml`, and every entity category returns a `GeneratedEntity` rolled from the role tables its setting names. Later categories (encounters, waypoints, sites, NPC tiers) follow both choices.

**Config over code, and what belongs together lives together (step 9h).** The user wants the code as modular and as config-driven as it can be, with nothing hardcoded that need not be, and wants what belongs together in one place rather than spread over the codebase; CONTRIBUTING.md states both as rules, and AUDIT.md's principle 1 checks the second (step 1c). They settled the judgment calls of the principle-2 audit: the markup of prompts, the source systems' rule constants, named status groups, and patterns for the AI's words all move to yaml.

**Lean over structure (9h.15).** The user wants the code lean, KISS, YAGNI, and DRY (CONTRIBUTING.md, Lean, not defensive), and left the judgment calls of 9h.15 and of the retry's catch to the session. So parameters for tests are ruled out (CONTRIBUTING.md, No parameters for tests), and the retry's catch keeps covering the request built inside the provider's call rather than adding a request step to the provider protocol (`docs/ai.md`, Provider adapters).

**One model for every role**, the user's preference, is recorded in `docs/ai.md` (Model assignment); the prompt tuning of step 9f relied on it.

**Four layers (step 9n).** The user's decision: Mythic is the game master over whatever system is played, the Crafter books add content to it, and the ruleset and the setting are separate layers, even while every shipped setting runs on an Ironsworn ruleset, with as little as possible fixed in Python. From step 9n on, a step that adds rules (9j, 13b, 18 to 29) builds them in the ruleset, one that adds world content (10, 10b, 27) in the setting, and one that extends Mythic or a Crafter (30 to 35, and the Location Crafter of step 10) in its own layer. The order is the user's as well: the audits of principles 3 and 5 first, since they shrink what the split moves, then the split, with the audit of principle 1 on the layout it makes.

---

## NEXT STEP — 9h: Principle audits


The audits of AUDIT.md, one session per principle or submodule as it prescribes, in this order: principles 2 and 4, which are mechanical, then principles 3 and 5 per submodule; principle 1 runs in step 9n, on the layout that step makes, and the two long clean-ups of principle 2 wait in step 9o. Principles 2, 3, and 4 are done; principle 5 runs one submodule per session in AUDIT.md's order, `mechanics/` done and `npc/` next. Every finding is fixed in its session or becomes a substep here. Waiting for the audit to classify, or for the user:

**9h.5** The `.get()` scan flags only constant, non-neutral defaults, so `.get("key", variable)` passes unexamined, for example in `web/serializers.py` (pass 4b).

**9h.6** Some `strings/*.yaml` keys are built at runtime from a prefix (`time.`, `disposition.`, `story.`, `tone.`, `succession.title_`, `succession.headline_`, and `succession.legacy_track_` in `web/serializers.py`), so a strings scan needs to know those prefixes (pass 5b).

**9h.13** Findings the audits saw on the way for a later principle, each for the session of its submodule. Principle 1: `game/succession.py` → `_replace_character_identity` repeats the identity setup of `game/game_start.py` → `start_new_game`.

**9h.14** Three keyed-scene id helpers share one body with different prefixes (`mechanics/adventure_crafter.py` → `_next_keyed_scene_id`, `mechanics/random_events.py` → `_re_next_keyed_scene_id`, `mechanics/keyed_scenes.py` → `_next_clock_keyed_scene_id`), and `consolidate_threads` repeats `consolidate_characters`; `game/setup_common.py` counts NPC numbers itself beside `npc/matching.py` → `next_npc_id`, and `npc/processing.py` → `_apply_surname_update` repeats the alias handling of `npc/lifecycle.py` → `merge_npc_identity`. Clock code lives in six files: `mechanics/consequences.py` (autonomous ticks, miss ticks, purging fired clocks, NPC agency ticks), `mechanics/clock_consequences.py` (a filled clock), `mechanics/clocks.py` (naming and the emergent count), `mechanics/complications.py`, the spawners in `mechanics/random_events.py` and `mechanics/adventure_crafter.py`, and `mechanics/keyed_scenes.py` (keyed scenes for a clock). Under "What belongs together lives together" the clock behaviour gathers in `mechanics/clocks.py`, with the spawners calling it; it belongs to the principle-1 session for `mechanics/`, which looks for the same pattern in threats, tracks, and NPC naming.

**9h.16** Consequence sentences come from parsing the engine's own consequence labels back from text (`mechanics/consequences.py` → `_classify`): `mark` stands for an impact, progress, and experience, a bond is found by the word in the line, and Pay the Price rows pass through the same parser, which turns an unparsable amount into 1. A structured consequence in `OutcomeResult` instead of a string removes the parser; it touches the effect and move handlers, boasts, finalization, and the narrator's consequence block. The parser has no branch for a disposition shift (Make a Connection, Test Your Relationship), so it gets no sentence (its unused templates left `engine/consequence_templates.yaml`); a structured consequence can give it one.

**9h.17** `/advance` takes the asset id the player types (`web/handlers.py` → `handle_advance_asset`): an unknown id is added to the character's assets, and `mechanics/legacy.py` → `advance_asset` spends experience on an upgrade of an asset the character does not hold, that does not exist, or that is fully upgraded. The player hears why it was refused, from `strings/`.

**9h.18** A bond, connection-rank, or disposition effect without a target NPC does nothing (`mechanics/move_effects.py`), since the Brain's schema lets `target_npc` be null for every move; whether `call_brain` refuses such a move without a target, as it already refuses Make a Connection.

**9h.25** A connection that Forge a Bond completes is no longer active, so its bond, its aid, and Develop Your Relationship no longer see it, though in Starforged the connection stays and becomes bonded; and a miss on Forge a Bond fails the track, where the rules clear all but one box and raise the rank if the character recommits. What a bonded connection keeps (its bond for the stance and the gate, its aid) is checked against the books before the step.

**9h.28** A correction of the state narrates the turn again without the turn's random events, threat events, and filled clocks, since the turn's snapshot keeps none of them (`correction/orchestrator.py` → `_rewrite_prompt`); keeping them in `TurnSnapshot` breaks the save format.


### Definition of Done

- Principles 3 and 5 are audited as AUDIT.md prescribes, and each one's Status lists every submodule it covers; a session that stops halfway records where it stopped. Principle 1 belongs to step 9n, and the open principle-1 findings of 9h.13 and 9h.14 move there when this step closes.
- Every violation is fixed in its session or becomes a substep here, and every substep above is classified and fixed or settled with the user.
- Each session's CHANGELOG entry carries its queries and their counts, as AUDIT.md describes.
- Quality gate green, no new project-rule violations, one CHANGELOG entry per finished session.

### Reference patterns

- The method, the passes, and the carve-outs: AUDIT.md.
- The carve-out lists the audits read: `_AI_CALL_CARVE_OUT_FILES` and `_INLINE_IMPORT_WHITELIST` in `tests/test_project_rules.py`.
- A config binding without defaults: `engine_config_dataclasses.py`, read through `eng()`.

---

## Next steps

Sketches, in the order of work; a step gets its definition of done and reference patterns when it becomes NEXT STEP.

Steps 11b, 11c, 11d, and 14c take ideas from EdgeTales: reimplement them, do not port code, and credit EdgeTales in the CHANGELOG entry that lands each.

Steps 11, 14b, 25, and 26 each plan a Director tool. The Director has one tool, `query_game_state`; whether it keeps a tool at all is decided at the start of step 11 (11.0), and whether a planned tool becomes a new one or part of it when its step becomes NEXT STEP. A new tool works through the Director's two calls as it stands: the first offers the tools, and the engine hands their results to the second as text. A step that wants a round in which the model reads its results and calls again brings back what such a round needs and nothing uses now: the Anthropic adapter's conversion of tool messages into `tool_use` and `tool_result` blocks, and a place for the schema instruction when the last message is not the user's; both are in git history, in `ai/provider_anthropic.py` and `ai/api_client.py` before commit 0514fd6, and such a round also needs the id of each tool call, which `ai/provider_base.py` → `ToolCall` no longer keeps. A tool takes no parameters today; one that needs them brings back the schema built from its type hints and the check of the model's arguments, in git history in `tools/registry.py` and `tools/handler.py` before release 2026.10.18.8.

### 9n — Game master, crafters, ruleset, and setting as layers

The user's decision (Decisions, Four layers). Today one setting carries both the rules and the world: its yaml in `data/settings` and its Datasworn chain, while the rules of the Ironsworn family sit in `engine/` beside Mythic's and the engine's own, 73 yaml files in one folder; `engine/dice.yaml` alone holds Ironsworn's action and challenge dice beside Mythic's and the Adventure Crafter's. Datasworn already draws the line the engine flattens: classic Ironsworn and Starforged are `type: ruleset`, Delve and Sundered Isles `type: expansion` of one of them.

**9n.1** Four layers, each with its own package and its own yaml folder, and a project-rule scan for the direction of imports between them. The game master: Mythic's fate, chaos, scene test, random events, and lists, with the engine's own rules that hold in any system (clocks, position and effect, facts, pacing, and the NPC layer). The crafters: the Adventure Crafter, its character-crafting tables, and the Location Crafter if the user buys it. The ruleset: classic Ironsworn and Starforged, with Delve and Sundered Isles as their expansions. The setting: the world, its truths, oracles, atlas, vocabulary, tone, and generators. The game master and the crafters know of a ruleset only what a narrow interface gives them: the tier of a roll's result, which drives the chaos factor, the Director, the emotion of a memory, and what a miss withholds, and a move's category.

**9n.2** The ruleset owns what a system decides, read from its yaml instead of fixed in Python: dice and result tiers (three today, with the group of hits in `engine/dice.yaml`), meters (`models_base.py` → `Resources` holds health, spirit, supply, and momentum as fixed fields, read 25 times in 8 files), stats and their arrays, progress tracks and ranks, moves and their outcomes, impacts, legacy, and assets. Classic Ironsworn's rule differences, keyed today by the setting id under `move_outcome_overrides` in `engine/move_outcomes.yaml`, become the classic ruleset's own. The save format breaks.

**9n.3** A setting names its ruleset. A Datasworn ruleset file carries both layers, so its rules and moves load as the ruleset and its oracles, truths, and atlas as the setting of the same world; where a section such as assets belongs is settled in the step, checked against the books. `docs/settings.md` then describes adding a setting and adding a ruleset apart.

**9n.4** The audit of principle 1 (AUDIT.md) runs per layer on the new layout, with the principle-1 findings 9h.13 and 9h.14 collected, since the split is itself the largest principle-1 change and an audit before it would judge a layout about to go. Production code imports `mechanics/` both through its `__init__.py` and from its files directly; the hub now re-exports only what code outside the package imports through it, and the split settles one way per package.

**9n.5** The audits already done stand for code the split only moves. Code it writes or rewrites (the interface between the layers, the meters, the loader that splits a Datasworn file) gets the queries of principles 2 and 3 (AUDIT.md) in the same step, beside the diff reading every change gets, and AUDIT.md's Status then names the audited code by its new packages.

### 9o — Dataclass defaults and prompt markup

Two clean-ups of principle 2, formerly 9h.4 and 9h.12, one session per module or group. They depend neither on the audits of step 9h nor on the split of step 9n, so they wait until after it: the split comes sooner, and the defaults leave the state classes in the form the split gives them.

**9o.1** Dataclasses carry defaults against the rule as CONTRIBUTING.md states it ("Domain config keys raise on a miss, and dataclass fields have no defaults"): about two hundred defaults that are not empty collections, in 43 classes, concentrated in `models_story.py`, `models.py`, `models_base.py`, `datasworn/moves.py`, `mechanics/move_effects.py`, and `models_npc.py` (for example `KeyedScene.source` and `KeyedScene.bound_entity_id`), beside about seventy empty `default_factory` collections, which the rule allows. The optional fields of `AICallSpec` and the partial classes in `datasworn/settings.py` parse external structures and keep theirs. Each module loses its defaults with every constructor call updated, one module per session; when the last is done, the config-binding scan widens to every dataclass (pass 2d). Pass 2d's scan of dataclass fields with a value finds them; it counted 196.

**9o.2** The prompt markup assembled in Python moves to `prompts/*.yaml` (settled by "Config over code"): XML tags, attribute names, `key:value` labels, and markers. One session per group, each checked by rendering every prompt of the group on a created game before and after and requiring byte-identical text, since the cached prefixes and the measured tuning depend on it: `prompt_shared.py`; `prompt_action.py` and `prompt_dialog.py`; `prompt_boundary.py` and `prompt_blocks.py`; `ai/brain.py`; `ai/narrator.py` and `ai/recap.py`; `director.py`; `ai/blueprint_voicing.py`; and the small sites in `correction/`, `mechanics/bonuses.py`, `mechanics/tracks.py`, `mechanics/random_events.py`, and `game/turn.py`.

### 9i — Revelations settled by the engine

Today the blueprint's revelations reach the narrator as `<revelation_ready>`, and a separate AI call (`call_revelation_check`) judges afterwards whether the prose contained one, which is the kind of post-hoc validator `docs/divergences.md` rules out. Instead the engine decides when a revelation lands (its scene range, or a keyed scene) and hands it to the narrator as a mandatory element, like a `<consequence>`, and marks it revealed at once; the `revelation_check` role, its prompt, schema, and cluster entry go. Measure with Elvira how often the narration carries the revelation before and after.

### 9j — Rules conformance: classic and the Adventure Crafter

The register of deliberate departures is `docs/divergences.md`.

**9j.1** In classic Ironsworn, wounded and shaken no longer block recovery; classic asks only for health or spirit above 0, and the rule stays for Starforged and Sundered Isles.

**9j.2** Classic's bonds special track: Forge a Bond marks it, and Write Your Epilogue (step 13b) rolls it.

**9j.3** The Adventure Crafter's theme translation lets the adventure's tone pick a theme for the blueprint.

**9j.4** The individual words of the oracle and meaning tables are checked against the books.

**9j.5** Death through Face Death, as the rulebooks have it (the user's decision). The game no longer ends because health and spirit are both 0 (`game/finalization.py` → `_update_crisis` keeps only the crisis status). Harm or stress taken at 0 goes through Endure Harm or Endure Stress, and a miss at 0 marks an impact the move offers while one is free (a fixed choice for the register) or, when none is free, rolls the move's Datasworn table (`<setting>/oracles/moves/endure_harm` and `endure_stress`). A result that names Face Death, Face Desolation, or Forsake Your Vow starts that move through the engine, as an engine trigger. The dying result (Heal within an hour or two, or Face Death) needs a deadline, a clock or a keyed scene, decided in the step. Whether harm from Pay the Price and from miss consequences should itself be rolled through Endure Harm, as the rulebooks do, is checked against the books first. The suffer and threshold handlers of `mechanics/move_handlers.py` and their entries in `engine/move_outcomes.yaml` exist, but no turn reaches them, so no impact is marked in play; this step makes them live, checked against the books. The register entry "Game over when health and spirit are both 0" leaves `docs/divergences.md`; Elvira's `near_death` scenario follows the new path.

**9j.6** Threats and Forsake Your Vow as the books have them. Advance a Threat is rolled on its Delve table when the character gives ground to a threat through inaction, failure, or delay; which misses count, and whether the autonomous tick stays as the engine's reading of delay, is checked against Delve first. A full menace track starts Forsake Your Vow as an engine trigger, with classic's spirit cost by the vow's rank through Endure Stress, and Starforged's choice of costs as a fixed choice for the register. A menace that fills at scene end forsakes its vow without the narrator hearing of it, since `game/scene_finalization.py` drops the events of `resolve_full_menace`, while a clock that fills then reaches the next turn's prompt through `WorldState.pending_clock_fills`. The register entries "Threats advance by engine rule, not by Advance a Threat" and "A full menace track forsakes the vow at a fixed cost" leave `docs/divergences.md`.

**9j.7** The Adventure Crafter's Meta plot points take effect. A Meta result is rolled into a turning point as a hit that does nothing, and `mechanics/adventure_crafter.py` → `dispatch_meta`, its seven handlers, and the Characters List template have no production caller. Each handler is checked against the book before it is wired into the turning-point roll: Character Returns without an exited character makes a new character, which needs a name from the npc generator instead of a placeholder, and the handlers take the turning point's random generator instead of making their own. `dispatch_meta` and the Characters List template sit under an orphan-symbol carve-out in `tests/test_project_rules.py` until this step wires them, and a handler that needs the active plotline takes it where `roll_turning_point` holds it. The register entry "Meta plot points have no effect" leaves `docs/divergences.md`.

**9j.8** Make a Connection's weak hit brings a complication or cost, as the move says; today it is only narrative. The `complication` effect of Gather Information and Compel is the pattern, with its sentence from the move text in `engine/consequence_templates.yaml`.

Ability effects other than adds belong to step 18; outcomes where the player would choose a cost are a recorded divergence.

### 9k — Scene challenges

The scene challenge of Starforged and Sundered Isles is configured but unreachable. Begin the Scene has no roll, so `tools/builtins.py` → `available_moves` keeps it from the Brain and its entry in `track_creating_moves` never fires; without a scene-challenge track, `engine/move_availability.yaml` never offers the scene-challenge versions of Face Danger and Secure an Advantage or Finish the Scene; the `fill_clock` effect of their misses is computed into `OutcomeResult.clock_fills` and read by nothing; and no tension clock exists to fill.

**9k.1** Begin the Scene becomes a formal move: `available_moves` lets through the moves without a roll that a yaml list names as formal moves, with their category and outcome in the same commit, as "Categorisation follows implementation" requires. The Brain names the objective as the track's name and picks the rank the move gives for the situation: troublesome with a clear advantage, dangerous when ready to act, formidable when unprepared or outmatched.

**9k.2** A turn for a formal move without a roll: the state changes (the scene-challenge track and a four-segment tension clock linked to it, whose creation spawns keyed scenes like every clock) and the narrator tells it without dice.

**9k.3** `fill_clock` fills the tension clock of the active scene challenge; what a full tension clock does follows the book, checked first.

**9k.5** A test plays a scene challenge through the real path from Begin the Scene to Finish the Scene and checks that misses fill the tension clock; an Elvira scenario starts one.

### 9m — Measuring the other prompts

The measuring setup outside the repository captures narrator calls only; no situation set measures the extraction prompts (`narrator_metadata`, `opening_setup_extractor`), `blueprint_voicing`, or `recap`. A set of captured calls per prompt, with a judge that checks each answer against its input, comes before any change to these prompts. The revelation check is left out, since step 9i removes it.

### 10 — Location and encounter generators

**10.1** The location and settlement categories of step 9d weighted by location properties and the world state, with the setting's atlas tables (10.6): each category names the game-state inputs that weight its tables, the way a fact type names its inputs in `engine/fact_resolution.yaml` (no prosperous trading post in a region at war, as the design document puts it). A generated place also gets its name from the setting's name tables (Starforged and Sundered Isles settlement names, classic's quick settlement names) where the player has not named it, and the register entry "Places are rolled without the world state, and their names are narrated" leaves `docs/divergences.md`.

**10.2** The encounter category, registered in `engine/generation.yaml` here, weighted by location properties, active threats, and chaos; oracle for structure, AI for description. Weights in `engine/encounter_weights.yaml` (new). Two code paths follow a link from one oracle row to another table: `datasworn/cascade.py` → `roll_oracle_cascade` for threat names and `datasworn/oracle_rolls.py` → `roll_oracle` for the generators; the encounter category settles on one.

**10.3** Prompt budget: `<generated>` tags replace unstructured invention, net near zero.

**10.4** Encounter output reaches the Brain as structured data through the existing state path; couples forward to steps 12 and 25.

**10.5** Tests.

**10.6** The setting's own tables feed these generators: the atlas regions of classic and Sundered Isles for locations; the Datasworn NPC entries (classic ironlanders, firstborn, animals, beasts, horrors; Delve and Starforged entries), Starforged creatures and starships, and Delve monstrosities for encounters.

**10.7** Perils and opportunities of the place. Starforged's location themes, derelicts, vaults, planets, and space, and Sundered Isles' overland, caves, ruins, and shipwrecks each have a peril and an opportunity table. At a generated place, a miss takes its worsening from the place's peril table, and a result whose move text offers an opportunity takes it from the opportunity table; each reaches the narrator as a consequence it must tell, the way a weak hit's complication does, so the worsening comes from the place instead of the narrator. How a peril relates to Pay the Price, which the engine rolls on a miss today, is checked against the books first. Classic Ironsworn has no such tables and keeps Pay the Price; Delve's Reveal a Danger comes with its sites in step 26. A place keeps the choices its rolls made (today it keeps only their text), so a path such as `location_themes/{theme}/peril` in its generator entry resolves on a later turn.

If the user buys the Location Crafter (Word Mill Games, under the same CC BY-NC license as Mythic), its tables join step 10 as data for areas where the setting has no location tools of its own; until then step 10 uses the setting's oracles only.

### 10b — Campaign launch from the setting's oracles

The opening scene and the character's start come from the setting's launch tables instead of the narrator's invention: Starforged's inciting incident and background assets, and Sundered Isles' getting-underway tables (create your character, take command, chart your course). The quest starters of the chosen truths, which Datasworn carries with each truth option, are candidates for the opening threads, since the hand-written tensions that used to stand there are gone.

### 11 — NPC generation with tiers

**11.0** First, with the user: does the Director keep its tool. It takes no parameters and returns the same view of the state whatever the model asks, and in the Elvira session of release 2026.10.18.8 the Director called it on each of its five runs, so by `docs/ai.md`'s own axis (data nearly always relevant and bounded belongs in the prompt) it could be prompt data; the first of the Director's two calls, about a quarter of the Director's cost, would go, and with it the tool registry and its handler. Against it stands the design document, which makes tool calling central (`docs/divergences.md`, Tool calling per data type). The question waits for this step because 11.2 is the first to plan a richer Director tool, which makes it concrete: must the Director choose the data itself, or does the engine already know the promoted NPC and hand it its threads and memories? The user expected tool calling to add much when the project began and is no longer sure it will, as the engine takes over the choices.

**11.1** Tier 1 (throwaway): demeanor, name, and disposition rolled from oracles, no AI call, with the setting's character oracles (Starforged first look, initial disposition, role, goal, revealed aspect; classic role, goal, descriptor), and identity and descriptors from the Adventure Crafter's character-crafting tables (`mechanics/adventure_crafter.py` → `roll_character_traits`, whose `CharacterTraits` then leaves the orphan-symbol carve-out). The demeanor and disposition tables join the npc category's entry in the per-category oracle-path mapping of step 9d.3, beside the name tables; a missing path raises KeyError. The narrator receives the rolled values as structured prompt context.

**11.2** Tier 2 (recurring): full AIMS plus a goal clock, the AI writing only the AIMS. The Director generates them: it reads the tier-1 base and the active threads through its game-state tool, then writes the AIMS through its JSON schema; always-relevant context (current location, faction state once step 14 lands) is prompt-injected.

**11.3** Promotion trigger in `engine/npc_promotion.yaml` (new), default three interactions in five scenes, counted from the NPC's memories.

**11.4** A `tier` field on NpcData as a config-key string, not a Python enum.

**11.5** Tests: tier-1 NPCs spawn deterministically from fixed-seed rolls; AIMS generation fires only on promotion; missing tier-1 oracle paths raise KeyError.

### 11b — NPC exits and retirement

**11b.1** Exit tracking. NPCs who walk out of a scene can be pulled back next scene by the activation bonus without narrative reason. The narrator_metadata extractor reports `exited_npc_ids` (the same pattern as `deceased_npcs`); `NpcData` gets an absent-until-scene value (the save format breaks); activation scores the NPC zero while absent unless the player names them or the Brain targets them; chapter start clears the value. Tests for exit, suppression, the player-name override, and the chapter reset.

**11b.2** Stale retirement. An active NPC with an empty connection track and no new memory for N scenes (yaml) moves to background; reactivation already exists. Guard against retiring an NPC in the scene they reappear.

### 11c — NPC-to-NPC memories in the prompt

`MemoryEntry.about_npc` records what NPCs remember about each other, but the narrator never sees it, and no caller passes the present NPCs to `npc/memory.py` → `retrieve_memories`, so its boost for memories about them (`npc.about_npc_relevance_boost`) never applies. The engine selects `about_npc` memories between NPCs present in the scene (one per pair, most recent first, cap in yaml) and injects them as a block whose template lives in `prompts/blocks.yaml`. The present NPCs then reach `retrieve_memories` too; its `present_npc_ids`, which production never sets, is the one parameter left under "No parameters for tests", kept for this step. Stepping stone for step 24.

### 11d — Narrator direction on NPC backstory

NPCs draw on their description, agenda, arc, and earlier scenes; where their past is not established, they keep it vague rather than invent family or history. Phrase it as direction, not prohibition, and measure with Elvira before and after, because prompt wording has caused regressions before.

### 12 — NPC goal clocks and autonomous actions

Builds on step 11 and extends `check_npc_agency` (`pacing.npc_agency_interval`). Today no clock has an NPC owner, so its agency tick and the owner rename in `npc/lifecycle.py` → `merge_npc_identity` never run; the goal clock decides what `owner_id` holds, an NPC id rather than the name it is matched against now.

**12.1** `goal_clock: ClockData | None` on NpcData, persisted with the NPC.

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

### 13c — Foe actions and plot twists from oracles

What a foe does in a fight comes from the setting's combat-action oracle (classic turning point combat action, Starforged and Sundered Isles misc combat action, Delve combat event) instead of the narrator. A new track's rank in classic comes from the challenge-rank oracle when the player names none, instead of the Brain's guess. Classic's major plot twist joins the turning-point sources. Each result reaches the narrator as a structured tag.

### 14a — Faction data model

FactionData with name, goal, tenets, members, and its standing toward the other factions, which the design document places in a setting's static layer; `faction_id` on NpcData and the factions in `GameState`. The save format breaks.

### 14b — Scheme clocks and chapter-spanning factions

A scheme clock per faction that ticks on its own and queues a faction event when full (`engine/clock_keyed_scenes.yaml` already covers `scheme`); factions carry over chapters through the three-place chapter pattern; faction archetypes come from the setting's Datasworn oracles through the per-category oracle-path mapping of 9d.3 (classic Ironsworn has none).

### 14c — Clock and threat pressure in narrative direction

The narrator learns about a clock only when it fills, while the design document names clock states and threat levels as sources of narrative intensity. A pressure tier from the fullest clock and the highest menace feeds the existing intensity derivation, with no numbers or names in the prompt; measured with Elvira before and after.

### 15 — Faction prompts and status

Faction context for activated NPCs, a `<faction_event>` tag when a scheme clock fills, and a `/factions` status command in narrative form.

### 16 — Faction reputation and NPC loyalty

Player reputation per faction, whose extremes override personal bond in the stance resolver, and NPC loyalty derived from faction bond against player bond through connection tracks.

### 18 — Asset mechanics beyond adds

Builds on the enabled abilities and the Brain's `bonus_id` (`mechanics/assets.py`, `mechanics/bonuses.py`): rerolls, extra effects on a hit, condition meters on assets, and choosing which ability an upgrade enables. Tests use real Datasworn assets with ids as character creation stores them.

### 19 — Companion and vehicle assets

Companion health and vehicle condition tracks, with Withstand Damage as a suffer move; Companion Takes a Hit and Withstand Damage roll with the asset's meter, which `mechanics/roll_sources.py` → `roll_source_without_stat` then reads beside condition meters and connection ranks; an `/assets` command; companions and vehicles in `<character_state>`. Starforged's starship history and quirks are rolled when the command vehicle is created.

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

An expedition object (Option C) and its moves (Undertake an Expedition, Explore a Waypoint, Make a Discovery, Confront Chaos, Finish, Set a Course), with waypoints as a step 9d category and as scene boundaries. Set a Course rolls +supply, which the Brain's stat choice cannot name, so today it is played as dialog (9h.1).

### 26 — Site exploration data model and Delve

One site model (Option C) for every setting, with Delve's 8 themes and 12 domains, its denizen matrix, its site moves, its 20 prepared sites, and its 62 rarities with Wield a Rarity.

### 27 — Sites for Starforged and Sundered Isles

Starforged's derelicts, precursor vaults, and location themes, and Sundered Isles' exploration, as site configurations without Python; Starforged's anomaly-effect oracle comes with the vaults.

### 28 — Sundered Isles specifics

Ship mechanics through the asset pipeline of steps 18 and 19; the cursed die, checked against the Sundered Isles rules first (the `cursed` impact in `engine/impacts.yaml` is a separate mechanic); the setting's own oracle categories and misc tables.

### 29 — Crew mechanics

The Sundered Isles crew and morale system.

### 30 — Player vs PC knowledge

Mythic's four strategies for what the player knows against what the character knows (`mythic_gme_2e.json` → `player_vs_pc_knowledge`), with a knowledge status on random events and NPC secrets.

### 31 — Thread progress tracks and discovery checks

Mythic's thread progress track (Option C) with its phases and Flashpoints, discovery checks through the fate system, and a `thread_phase` keyed-scene trigger.

### 32 — Chaos factor variants

Mythic's chaos variants, each with its own fate chart, and the prepared-adventure event focus while a blueprint is active, since a blueprint is a prepared adventure.

### 33 — Themed element tables

`mechanics/random_events.py` → `roll_meaning_table` reads only actions and descriptions; the 45 themed tables in `mythic_gme_2e.json` → `meaning_tables.elements` join random events by context, six high-use tables first.

### 34 — Remaining themed tables

The other 39 themed tables, config only.

### 35 — Detail check chains

Follow-up fate questions whose odds start from the answer before, at most three, built on fact resolution so that the chain lands in `WorldState.facts`.

### 36 — Setting authoring tooling

A command that checks a new setting package (its yaml against the Datasworn file, every oracle path it names, its inheritance) and reports what a generator category still lacks, as the design document suggests for setting authors.

---

## DONE

Finished work in its shortest form; the CHANGELOG has the details.

- **Before step 9a.** The four Datasworn settings (moves and outcomes, Pay the Price, chained moves, roll bonuses, legacy, impacts), Mythic GME 2e (lists, fate, meaning tables, random events), the Adventure Crafter's blueprint, Blades clocks, narration streamed by sentence, strict saves and config, and Elvira.
- **9a — Fact resolution.** The Brain names the facts an action turns on, and Mythic's fate chart settles them (`docs/mechanics.md`, Facts).
- **9b — Chapters as Mythic adventures.** Resources and clocks carry over, chaos restarts at 5, and a game that is over continues only through succession.
- **9c — Soft misses.** On a miss the NPCs present withhold, and agenda, secrets, guidance, and a pending revelation stay out of the prompt.
- **9d — Generators.** NPCs, locations, and settlements roll the tables each setting names (`docs/mechanics.md`, Generators).
- **9e — Elvira findings.** NPC identity holds across extraction, renames, and chapter openings, and in dialogs the NPC's fact budget governs, at the user's choice.
- **9f — Prompt tuning on Sonnet.** Every role on Claude Sonnet 5.5 at effort medium, Elvira on Haiku 5.5 (baseline 6.41 ± 0.14). Rewording the narrator prompt stayed within the noise, so the faults that remain are for the engine; the measuring setup keeps every variant.
- **9g — Tests through the real creation path** (`create_game` in `tests/_creation.py`).
- **9l — Complications as clocks** (`docs/mechanics.md`, Complication clocks).
- **9h, so far (the step is still open).** The campaign tone is chosen at creation. Principles 2 and 4 are audited and fixed apart from step 9o: text, thresholds, dice, and groupings live in yaml, and saves, snapshots, and config refuse what they do not know. Principle 3 is audited for `mechanics/`, `npc/`, `game/`, `ai/`, `datasworn/`, `tools/`, `correction/`, the files directly under `engine/`, and `web/`: impossible states raise; redundant guards, dead code, write-only data, parameters only tests set (9h.15), and the database copy of the game state are gone; oracle tables and moves come from the loaded setting chain; the AI calls catch only the call and its answer; a complete narration is kept whole (9h.19); chapters no longer copy what carries over (9h.3); a move that rolls or marks a track is offered only while its track exists, a fight being its combat track and a classic journey started by Undertake a Journey (9h.13); and a correction names NPCs by id, reports what it cannot apply, and no longer reaches back past a chapter or a succession. Principle 5 is audited for `mechanics/`: result fields and return values only tests read (9h.8), config no code reads, and re-exports nobody imports are gone. A connection made in play is its NPC's and is made only on a hit, and two NPCs merged into one leave nothing behind that points at the one that went (9h.24). The Brain is asked again for a missing or wrong stat (9h.1), threads gain weight when a scene invokes them (9h.20), moves that roll with a meter or a connection's rank are rolled (9h.21), and the scene-challenge rule for the ordinary moves left early (9k.4). Prompts are filled strictly, the Director catches only its two calls, the parser cleans up only what the current prompts can leak, and a correction of the state tells the turn again with its own scene, position, and effect. Every AI-call carve-out is classified (9h.7): a web handler catches only the call that reaches the AI, a new chapter or succession runs on a copy of the game, and any other fault in a handler reaches the player as an unexpected error.
