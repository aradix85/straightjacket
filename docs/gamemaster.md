# The game master

How the engine plays Mythic GME 2e as the game master, with Blades in the Dark's position, effect, and clocks: the questions it asks the ruleset, its own moves, what a miss withholds, position and effect, NPCs, scenes and chaos, random events, fate and facts, generators, and clocks. It lives in `gamemaster/` and its yaml, with no AI; Replaying a turn describes how `game/` and `correction/` play a turn again. Deliberate departures from the books are in `docs/divergences.md`.

## Questions to the ruleset

The game master (`gamemaster/`) never reads the ruleset. It asks the questions of `gamemaster/questions.py` → `RulesetAnswers` in its own words; the ruleset answers them in `ruleset/answers.py` from its yaml (`ruleset/answers.yaml`), and the game package installs those answers when it loads (`game/__init__.py`).

What it asks:

- **How an action went**: an outcome, success, partial, or failure (`result_outcomes`). Beside these stand the engine's own labels for a turn without a roll (`outcomes.unrolled` in `gamemaster/outcomes.yaml`: dialog, oracle, opening, and a move without a roll). `gamemaster/questions.py` → `outcome_of` turns a result the session log holds into an outcome.
- **What kind of action** it was: a move category (`ruleset/move_categories.yaml`).
- **How close an NPC is** to the character: a number from 0 to 10, a connection's filled boxes in Ironsworn. The game master bands it by its own thresholds (the stance, the information gate, position and effect, keyed scenes).
- **How hard pressed** the character is: a level per meter, critical, low, or steady (`strain`). Whether the character is in crisis it reads from `GameState.crisis_mode`, which the game package sets from the ruleset's `in_crisis` (`game/finalization.py` → `update_crisis`).
- Whether the previous action **gained an advantage** (`advantage_moves`), whether an action **gathers information**, which counts toward the information gate on a hit (`information_moves`), and the **bonus an action adds to its effect** (`effect_bonus_moves`).
- **How long** an action takes (`ruleset/time_progression_map.yaml`); a change of place takes `location.change_time` in `gamemaster/location.yaml`.
- **How an action reads in a memory** (`action_phrases`).
- **How far each danger has advanced**: a threat's filled menace boxes in Ironsworn.

What it tells the ruleset: that it needs a new danger (`docs/ruleset.md`, Threats); that two NPCs were one person, so the ruleset merges their connections; and that a clock filled, so a filled progress clock completes the progress track of its name. A value the turn already hands along, such as the outcome that moves the chaos factor or settles the facts, comes as a parameter in the game master's words.

**Results outside the ruleset.** Code outside the ruleset (the game package, prompt assembly, the Director, and the server) decides on a roll only by its outcome (`gained` when the outcome is one of `outcomes.gained`). Otherwise it passes the ruleset's result on as it is:

- to the ruleset;
- to the narrator, as the type of its `<result>` tag; the outcome chooses the tag's text and narrative direction, and the narrator's rules name results by the ruleset's own names (`ruleset/answers.py` → `results_by_outcome`);
- to the player, in a momentum burn's offer, under its label in `strings/result.yaml`.

## The game master's moves

Dialog and asking the oracle are the game master's own moves in any system, with no roll, in `gamemaster/moves.yaml` with the time each takes. `gamemaster/moves.py` says whether a turn plays as dialog (`is_dialog_branch`) and whether it asks the oracle (Ask the Oracle below).

## Replaying a turn

Normal turns, corrections of a misread input, and momentum burns run the turn's own code in `game/turn.py`. Each turn keeps the snapshot taken right after its scene test, with the scene type, as `GameState.last_turn_snapshot`.

**A correction of a misread input** restores that snapshot and plays the turn again with the corrected input (`game/turn.py` → `replay_turn`). It keeps the scene type, the facts already settled at that place, and the dice already rolled, rescored with the new stat. So it rolls only dice the turn did not roll: all of them when a dialog is corrected into a roll, the action die when a progress roll is corrected into an action roll.

**A correction of the state** edits the state and narrates the turn again (`correction/orchestrator.py` → `_rewrite_prompt`) with what the turn told the narrator: its random events, threat events, filled clocks, and NPC agency, which the snapshot keeps (`TurnSnapshot.random_events`, `threat_events`, `clock_fill_results`, `npc_agency`). Nothing is drawn or ticked a second time.

- The analysis names NPCs by their id from the engine's list.
- An operation the engine cannot apply (no NPC named, a time of day that does not exist) is skipped with a warning, and so is an empty name in an NPC's edit, whose other fields apply.
- A split that names no second figure rolls its name like any new NPC.

**Nothing to correct.** A new game, a new chapter, or a succession leaves nothing to correct, since its opening is not a turn: `process_correction` raises, and the server refuses a correction before it starts (`correction.no_snapshot` in `strings/correction.yaml`). A game that is over is not corrected either: the server answers with the burn that still stands, or with its succession.

**A momentum burn** restores a second snapshot, taken right after the roll, resets momentum, and runs `resolve_and_narrate_action` with the better result (`game/momentum_burn.py` → `process_momentum_burn`). On a turn that ended the game, the restore also takes back the succession the server prepared; the server prepares it again if the better result still ends the game.

Every turn's narration, a correction's included, goes through `narrate_scene` and `apply_post_narration`; the openings and the epilogue call the narrator themselves.

## What a miss withholds

A narrator asked to hold back on a miss still handed out clues, so the engine decides what it has (`prompt_action.py` → `build_action_prompt`). On a miss:

- Every NPC present takes `information_gate.miss_stance` (withholding) instead of its matrix stance.
- The target NPC's gate falls to that stance's cap (`stance_caps.withholding`, 1), so it keeps only its description, with fact budget 0.
- Bystanders lose their memory hint.
- The previous Director guidance waits for a hit, and no revelation lands (`docs/story.md`, Revelations).
- A miss on a move that gathers information (`information_moves` in `ruleset/answers.yaml`: Gather Information) settles the place facts in `fact_resolution.information_miss_settles`, today `useful` no (`gamemaster/facts.py` → `settle_facts_by_miss`).
- A miss with a match rolls the story-complication oracle instead of Pay the Price where the setting has it (Starforged, Sundered Isles), as Datasworn describes that table.

A hit grants in the same way. A target NPC whose matrix stance would refuse or deceive (`information_gate.refusing_stances`: a hostile NPC's hostile, stonewalling, confrontational, and misleading) takes `information_gate.hit_stance` instead, yielding. So a hostile NPC compelled or questioned on a hit gives what the roll won and keeps its hostility only in how (`gamemaster/stance_gate.py` → `resolve_npc_stance`). Bystanders and turns without a roll keep the matrix's stance.

## Position and effect

Blades in the Dark's position (controlled, risky, desperate) and effect (limited, standard, great) are computed by the engine for every roll, before its consequences (`gamemaster/resolvers.py` → `resolve_position`, `resolve_effect`). The weights are in `gamemaster/position_resolver.yaml` and `gamemaster/effect_resolver.yaml`, the chaos, streak, and clock thresholds in `chaos_resolver` of `gamemaster/chaos.yaml`.

- **Position** adds up a score from the strain on the character's meters, the target NPC's disposition and closeness, the chaos factor, a streak of failures or successes, threat clocks close to full, an advantage the previous turn gained, and a baseline per kind of action. Two overrides cap it at risky (an advantage gained while a meter is critical) or raise it to risky (a recovery in crisis).
- **Effect** starts from position and adds closeness, the advantage, and the bonus the ruleset gives the action itself (Strike's, in `ruleset/answers.yaml`).
- Strain, closeness, the advantage, the kind of action, and how earlier actions went are the ruleset's answers (Questions to the ruleset above).
- Position decides how many segments a miss ticks a threat clock (`gamemaster/clocks.yaml` → `miss_ticks_by_position`) and whether a weak hit ticks one: always when desperate, never when controlled, otherwise at the chance `pacing.weak_hit_clock_tick_chance`.
- Both reach the narrator as a `<position>` tag; effect changes nothing else.

## NPCs

### Memory and activation

`gamemaster/npc/memory.py` scores memories for importance (`emotions/importance.yaml`, with keyword boosts from `emotions/keyword_boosts.yaml`), retrieves them, and consolidates them. A memory's emotional weight is derived from the kind of action, its outcome, and the disposition through `gamemaster/memory.yaml` (`gamemaster/engine_memories.py` → `derive_memory_emotion`).

`gamemaster/npc/activation.py` scores NPCs against the scene with TF-IDF and decides which get full context in the prompt. That decides only whom the narrator's prompt holds.

**Present in the scene.** An NPC counts as having been in the scene when the activation picked it or found it mentioned, and it is the action's target or the narration names it (`gamemaster/npc/matching.py` → `present_in_narration`). Presence decides the engine memory of the turn, the scene context, the Mythic characters list, and a reported death; a reported death also counts for an NPC with a memory of this scene (`ai/metadata.py`). An NPC that only stands in the prompt's list of known NPCs does not count; otherwise an NPC who had left would be remembered into every later scene, and the scene context naming it would activate it again.

**Named in a text.** A text names an NPC when its name or one of its aliases stands there as whole words, or when a word of its proper name does (`gamemaster/npc/matching.py` → `proper_name_words`, `named_in`). A word of the proper name is a word of the capitalised run that opens the name, unless a longer lowercase word follows that run, as in a descriptive name; it is no title (`name_titles`), no stopword, and at least `fuzzy_match.named_in_min_word_length` letters long.

- A proper name keeps its capital, so an NPC called Hope or Wolf is not named by "hope" or "a wolf".
- A short name inside a longer word names nobody.
- A descriptive name or alias such as "the gate guard" names its NPC only as a whole, never by "gate" or "with" alone.
- Activation reads the player's own words without regard to case, since a player may type a name in lower case, and reads the Brain's and the scene's words the way it reads the narration (`gamemaster/npc/activation.py` → `activate_npcs_for_prompt`).

The same test decides when the narration introduces an NPC (`parser.py` → `_mark_introduced_npcs`), which NPC an opening memory belongs to when `find_npc` finds none by id or name (`game/setup_common.py` → `seed_opening_memories`), and whether an NPC moves along to the player's location (`game/finalization.py` → `apply_engine_memories`).

### Stance

The engine computes each NPC's stance from disposition, bond, and move category through `gamemaster/stance_matrix.yaml` (`gamemaster/stance_gate.py` → `resolve_npc_stance`). The target NPC and the activated NPCs reach the narrator with a behaviour, such as `stance="evasive" constraint="Answers in as few words as possible, then goes silent."`, instead of raw disposition values; the list of the other known NPCs names each with its disposition.

### Information gating

A gate level from 0 (name and description, a stranger) to 4 (full secrets) decides what of the target NPC enters the narrator prompt (`gamemaster/stance_gate.py` → `compute_npc_gate`; points, caps, and budgets in `gamemaster/information_gate.yaml`; what each level shows in `prompt_shared.py` → `_npc_block`). An activated NPC shows its stance, arc, and a memory whatever its gate.

The gate rises with scenes known, successful information gathering, and bond. The stance caps it (`stance_caps`), so a hostile NPC opens no further than its agenda and a few memories, at gate 2, whatever the bond. The narrator cannot reveal what it does not have. The gate also sets how many new facts an NPC may volunteer in a reply.

### Names, lifecycle, agency

New NPCs get oracle-rolled names from the setting's npc generator (Generators below), and `NpcData.name_rolled` records it.

**Names the extraction reports:**

- A full name reported for an NPC whose name the engine rolled, sharing no word with its name or aliases (the narrator's first label among them), becomes a new figure.
- For a figure the narration named, such as an opening NPC or a lore figure, the revealed name replaces the label, which stays as an alias (`gamemaster/npc/processing.py` → `_apply_name_update`).
- A new figure that matches a known NPC by its description is that NPC seen again: it keeps its name and gains the new label as an alias. So does a figure named by whole words of a known NPC's name, such as a first name for a full name (`gamemaster/npc/description_match.py`, `gamemaster/npc/processing.py`).
- An NPC whose name the engine rolled is matched by its own name and its earlier labels only. A figure that merely shares a word with such a label, such as "Second deckhand" beside "Lunging deckhand", is a new figure. No figure's label replaces the rolled name, but a rename the extraction reports for its id does (`process_npc_renames`, roadmap step 11).
- The extraction names known NPCs for renames and details by id, from the ids its schema offers, and a death by a reference the engine looks up (`find_npc`).
- A chapter or succession opening registers no NPC that the name matcher finds among the known ones (`game/setup_common.py` → `register_extracted_npcs`).

`gamemaster/npc/processing.py` applies the extracted metadata, `gamemaster/npc/matching.py` matches names, and `gamemaster/npc/lifecycle.py` merges identities, retires, and reactivates NPCs.

**Agency.** `gamemaster/clocks.py` → `check_npc_agency` tells the narrator every `pacing.npc_agency_interval` scenes that each active NPC with an agenda pursues it, and the narrator writes what the NPC does. The opening extraction gives the NPCs of an opening their agendas, instincts, and secrets; the Director's reflections set them and the arcs later (`docs/ai.md`).

## Scenes, chaos, and random events

**Scene test.** Every turn starts with a scene test, before the Brain call (`gamemaster/scene.py` → `check_scene`).

1. The keyed branch runs first: if a `KeyedScene` on `narrative.keyed_scenes` has its trigger fire, the highest-priority match consumes itself and sets the scene type `keyed`, and its hint reaches the narrator as `<keyed_scene>`.
2. Otherwise a d10 against the chaos factor decides: expected above it, altered at or below it on an odd roll, interrupt on an even one. Altered scenes roll on the Scene Adjustment Table; interrupt scenes generate a random event.

The chaos factor moves per turn (`gamemaster/chaos.yaml`). Pacing is computed from the recent scene intensity (`gamemaster/pacing.py` → `get_pacing_hint`), not asked of the AI.

**Keyed scenes** are the engine's pre-scheduled beats. Trigger types are registered in `gamemaster/keyed_scenes.yaml` and evaluated through `gamemaster/keyed_scenes.py` → `_EVALUATORS`: `clock_fills`, `threat_menace_phase`, `bond_threshold`, `chaos_extreme`, `scene_count`.

- Every source adds a keyed scene through `gamemaster/keyed_scenes.py` → `add_keyed_scene`, under the next free id (`has_keyed_scene_from` tells a source whether it already added one). It validates the trigger type and, for the three pattern triggers (`bond_threshold`, `threat_menace_phase`, `clock_fills`), the value against the grammar in `pattern_grammars`: an NPC id, a threat's name, or a clock's name with `:N`, `any:N`, and for bonds `disposition_<value>:N`, each with a matcher strategy (`highest_bond`, `highest_menace`, `highest_filled`).
- When a pattern fires, `evaluate_keyed_scenes` binds the entity in `KeyedScene.bound_entity_id`, which nothing reads yet, since the fired scene leaves the list at once.
- Three sources spawn keyed scenes:
  - the Adventure Crafter at chapter start: its `keyed_scene_mapping` maps 33 plot points to triggers, at most one per plot point per chapter, capped by `max_keyed_scenes_per_chapter`; a new chapter drops the ones the last chapter's turning points left;
  - random events when they fire, from the event's target;
  - the opening clock and the clocks random events and plot points start, by the per-type fractions in `gamemaster/clock_keyed_scenes.yaml` (`gamemaster/clocks.py` → `spawn_keyed_scenes_for_clock`). Complication clocks and the dying clock get none.

**Random events.** A four-step pipeline in `gamemaster/random_events.py`:

1. the event focus, a d100 over the focus categories (`roll_event_focus`);
2. a target from the weighted Mythic lists, or for a PC Negative or Move Away event, at `threat_target_probability`, an open danger;
3. a meaning-table roll on actions or descriptions (`roll_meaning_table`);
4. a structured `RandomEvent` (`generate_random_event`).

Events fire on interrupt scenes and on fate doublets. They reach the narrator as `<random_event>` and `<interrupt_scene>` tags; an interrupt scene's own event appears only as `<interrupt_scene>`.

**Mythic lists.** Both live on `NarrativeState`. The threads list starts with the background vow; the characters list with the vow's subject, if any, and the opening scene's NPCs.

- Present NPCs gain weight. New NPCs join the characters list as the NPC the engine named.
- A thread gains one weight in a scene that invokes it, which the engine reads from what it can see (`game/scene_finalization.py` → `invoked_threads`): a random event aimed at the thread, a move that acts on its vow (Fulfill Your Vow and Reach a Milestone), and a threat linked to its vow that the scene advances or a random event aims at.
- Once `consolidation_threshold` entries of a list are active, every scene resets their weights (`gamemaster/random_events.py` → `add_thread_weight`, `add_character_weight`, `consolidate_lists`).

## Fate

Yes/no questions about the fiction are rolled by the engine with odds the engine sets (`gamemaster/fate.py`). The player never picks the odds; a player's own question reaches fate only as a fact (Ask the Oracle below).

- **Two methods**: the fate chart (a 9×9 odds and chaos matrix, d100) and the fate check (2d10 plus modifiers). `fate.default_method` in `gamemaster/fate.yaml` picks one. Both read Mythic's own tables in `data/mythic_gme_2e.json`: the chart's cells, and the check's odds, chaos modifiers, and answer ranges.
- **Four answers**: yes, no, exceptional yes, exceptional no. Doubles whose digit is at most the chaos factor generate a random event, as Mythic's rule says.
- The chaos factor enters only as the chart's column or the check's modifier, as Mythic intends.
- `gamemaster/fate.py` → `score_to_odds` turns a score into one of the nine odds through `fate.likelihood_rules.score_to_odds`, the single odds scale.

## Facts

A fact is something the fiction depends on that the game state does not hold, such as whether a door is locked or a guard alert.

**Fact types** live in `gamemaster/fact_resolution.yaml`. Each names its subject (`place`, the current location, which the Brain writes as `here`, or `npc`, an NPC id from the Brain's list), a description the Brain and the narrator both read, a base score, the game-state inputs that shift it with their weight, and whether a hit on an action that depended on it clears it. There are five today: `locked`, `useful`, and `occupied` about the place, `present` and `alert` about an NPC.

- `alert` weighs the NPC's disposition from `fate.likelihood_rules.disposition_scores` negatively, so a hostile guard is likely on guard and a friendly one unlikely.
- A `present` fact answered no about the NPC the action targets releases that target for the turn (`no_releases_target`, `gamemaster/facts.py` → `release_absent_target`), so the scene never holds the NPC both out of reach and as the action's target.

**Resolving.** The Brain names the undetermined facts an action or question turns on, at most `max_per_turn`, from the types and subjects its schema offers (`ai/schemas.py` → `get_brain_output_schema`). After the Brain's move to another place is applied, `gamemaster/generation.py` → `resolve_turn_facts` sends each through `generate_fact`, behind the categories registered in `gamemaster/generation.yaml`. `gamemaster/facts.py` → `resolve_fact` reuses a fact already settled at this place, or scores the fact type, converts the score to odds, asks `resolve_fate`, and stores the answer with its place in `WorldState.facts`. The narrator receives the turn's facts as a `<facts>` block (`prompt_shared.py` → `_facts_block`, templates in `prompts/blocks.yaml`).

**Lifetime.** A fact belongs to the place where it was resolved.

- `gamemaster/world.py` → `clear_facts` empties the list when the player moves, when a correction changes the location, at a chapter start, and at a succession.
- After a roll, `gamemaster/facts.py` → `clear_facts_settled_by_hit` removes this turn's facts that were answered yes and whose type says a hit settles them, so a door the player just forced is not reported locked again. The narrator still hears the fact this turn.
- A no stays after a hit, so searching the same place again does not roll it again. The exception is a fact type that a miss on a search settles (`fact_resolution.information_miss_settles`, today `useful` no): a hit on an action that turned on it overrules it (`overrule_facts_by_hit`), so the narrator is not told that nothing useful is here while the result says the search succeeds, and the place no longer holds that no.
- A momentum burn keeps the turn's facts and clears them by the better result. A correction of a misread input brings back the turn's facts of the same place (`remember_facts`) instead of rolling them again.

**Ask the Oracle.** The game master's move `ask_the_oracle` is the player's question about the fiction. A yes/no question that a fact type covers is answered by that fact, the oracle table is not rolled, and the narrator gets the `task_oracle_facts` task. A question for which the Brain names no fact, an open question or a yes/no question no fact type covers, rolls the setting's action and theme oracle (`gamemaster/moves.py` → `roll_oracle_answer`) and reaches the narrator as `<oracle_answer>`.

## Generators

An entity category rolls the setting's own tables (`gamemaster/generation.py` → `generate_entity`). The categories are registered in `gamemaster/generation.yaml`, and each setting names under `generators` the table that every role of a category rolls (`docs/settings.md`). A category the active setting chain does not name raises.

**Rolling a table.** A table rolls a die as large as its highest row (`setting/loader.py` → `OracleTable.roll`). A row of a shared table that has no roll range in its column, such as an atmosphere a furnace planet cannot have, is left out; Sundered Isles' highlands landmarks, ten rows that cover 1 to 50 of a d100, roll a d50. The roller follows Datasworn's own instructions on a row (`setting/oracle_rolls.py` → `roll_generator_tables`):

- An automatic roll replaces its link with what it rolled (an Action and Theme pair).
- A row that rolls its own table again rolls it as often as it says and treats a repeated row by its `duplicates` rule: rolled again, kept, or made worse, as in classic's Pay the Price (`setting/oracle_rolls.py` → `roll_rows`, which Pay the Price, the chained oracle moves, and the names of complication clocks roll through as well).
- A role's path may name an earlier role, which stands for the table that role's row points to or for its text. So Starforged's location theme picks the feature table of that theme, and Sundered Isles' settlement location picks its focus table.

**The categories.** Besides `fact`, three exist:

- `npc` rolls the name of a new NPC when the metadata extraction registers one (`gamemaster/npc/naming.py` → `roll_oracle_name`): a given and a family name, one of classic's two hundred Ironlander names, or in Starforged the callsign at `naming.callsign_probability`.
- `location` and `settlement` are places. The Brain names the kind of every place it moves the character to, from `generation.place_categories`. When the place is neither a generated place nor in the location history, `generate_place_on_arrival` rolls that category and keeps it as a `PlaceRecord` in `WorldState.places`: a theme and a feature in Starforged, a descriptor and a kind of place in classic Ironsworn, a region and a landmark in Sundered Isles, and for a settlement its setting's settlement tables (in classic only its trouble).

**A generated place.** While the character is there, the action and dialog prompts carry its rolls as a `<generated>` block (`prompt_shared.py` → `_generated_place_block`), and a return finds the same place. The name stays the Brain's. Places stay with the world across chapters and successions, and a correction of a misread input that goes to the same place keeps the place it generated. The rolled text already uses the setting's words, and the vocabulary instructions cover it like any other text, so no word is replaced in place. Nothing weights the tables by the world state yet (roadmap step 10).

## Clocks

Every clock's code lives in `gamemaster/clocks.py`: making, ticking, and filling it. Two exceptions: the dying clock, a timer of the ruleset's Endure Harm that `ruleset/suffer.py` keeps (`docs/ruleset.md`, Harm, stress, and death), and what a filled progress clock does to a track, which the ruleset answers (`ruleset/tracks.py` → `complete_track_of_clock`). The spawn-source prefixes are constants in `gamemaster/spawn_sources.py`.

**The opening clock.** A new game starts with one threat clock named after the background vow, sized and filled from `gamemaster/opening.yaml` (`gamemaster/clocks.py` → `start_opening_clock`). Every opening (new game, chapter, succession) starts at the time of day that file names; the AI's opening extraction sets neither.

**Spawned clocks** come from the same sources as threats (`docs/ruleset.md`, Threats):

- A random event whose focus is in `gamemaster/random_events.yaml` → `clock_creation_mapping` (currently `pc_negative` and `move_away_from_thread` to a threat clock, `move_toward_thread` to a progress clock) names the clock after its Mythic pair.
- An Adventure Crafter plot point in `crafters/adventure_crafter.yaml` → `clock_creation_mapping` (Time Limit, A Crucial Life Support System Begins To Fail, A Needed Resource Runs Out, Impending Doom) names it after the plot point.
- Size and owner come from `gamemaster/clocks.yaml` (`default_segments`, `default_owner_kind`).
- These spawners and the complication clocks below spawn a clock only while fewer than `max_open_emergent` of the clocks they made are still unfired. Every new clock from the two spawners gets its keyed scenes at once (`gamemaster/clocks.py` → `spawn_emergent_clock`, which also skips a source whose clock is still listed). A fired clock leaves the list after `pacing.fired_clock_keep_scenes` scenes.

**Ticking.** Only threat clocks tick: a miss ticks the first open one in the list, the scene end each world-owned one by chance, and NPC agency only a clock an NPC owns, which no clock does until step 12. Nothing ticks a progress clock yet, and no scheme clock is made (step 14b).

### Complication clocks

The user's idea, after Blades in the Dark, which turns a complication into a clock: a complication that begins now and strikes only if the player leaves it (`gamemaster/clocks.py` → `spawn_complication_clock`).

- **Start.** A weak hit with a `complication` effect starts a world-owned threat clock of `clocks.complication.segments` (4), unless `max_open` (1) complication clocks are open or the cap on open spawned clocks is reached. It is named by a roll on `name_oracle_path` (the story-complication table where the setting has it), or else by a Mythic action pair. The narrator gets the danger as a consequence to show as a first sign.
- **Filling.** It fills one segment at every scene end, the scene that started it included (`tick_chance` 1.0 in `gamemaster/clocks.py` → `tick_autonomous_clocks`), and a miss's tick reaches it once every threat clock before it in the list is full. So it fills within four scenes and strikes through the threat fill tag, which a fill at scene end brings to the next turn. It has no keyed scenes, so the tag that the danger has arrived is what the narrator tells.
- **Heading it off.** The Brain sees open complication clocks as `<dangers>` and names one in `target_clock` when the action works to stop, undo, or escape it. A hit on that action removes the clock and tells the narrator it was headed off (`game/action_resolution.py` → `_maybe_avert_complication`).

### A filled clock

`gamemaster/clocks.py` → `resolve_clock_fill` emits a `<clock_filled>` tag from the per-type templates in `gamemaster/clocks.yaml` → `fill_consequences` (`threat`, `scheme`, `progress`), and the ruleset completes the active progress track of a filled progress clock's name. A keyed scene from that clock that is still pending takes precedence over both. Since every clock that random events and plot points start gets a keyed scene at its full mark, in play only complication clocks emit the tag. Filled threat and scheme clocks do not advance menace.

Fills from the ticks of a miss reach the same turn's narrator prompt. Fills from the autonomous ticks after narration queue on `WorldState.pending_clock_fills` and open the next turn's prompt.
