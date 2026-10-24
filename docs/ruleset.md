# The ruleset

How the engine plays the Ironsworn rules: moves, tracks and bonds, stats and meters, impacts, harm and death, legacy, boasts, assets, and threats. The ruleset lives in `ruleset/` and its yaml; the game master reaches it only through its questions (`docs/gamemaster.md`, Questions to the ruleset). Deliberate departures from the books are in `docs/divergences.md`.

## Moves

### Moves on offer

Move definitions (stats, roll types, trigger conditions) load from the ruleset's Datasworn files (`ruleset/moves.py` → `get_moves`; `docs/settings.md`, Rulesets). A later file's move replaces an earlier one's, as Sundered Isles replaces some of Starforged's.

The Brain chooses only from three groups (`ai/brain.py` → `_offered_moves`):

- the Datasworn moves the game state allows: `ruleset/move_availability.py` → `available_moves`, with the rules in `ruleset/move_availability.yaml`;
- the game master's own moves, dialog and asking the oracle (`docs/gamemaster.md`, The game master's moves);
- world shaping, an action roll with the ruleset's stats, the ruleset's own move in `ruleset/engine_moves.yaml`.

The availability rules:

- A move that rolls or marks a track is offered only while a track of its type is active (`active_track`), unless the move starts that track, as Undertake an Expedition and Undertake a Journey do.
- Enter the Fray and Battle are offered only outside a fight (`no_active_track`).
- Strike, Clash, Gain Ground, and React Under Fire also depend on the combat position (`combat_pos_in`).
- A move whose roll type the Brain is not offered (`unoffered_roll_types`: no roll, a special track) stays away from it, unless `offered_without_roll` names it (Moves without a roll below).
- Every Datasworn move the Brain can be offered has an entry in `ruleset/move_availability.yaml`, or `available_moves` raises. A rule naming a track type that `track_types_by_category` does not know stops loading.

### Rolling a move

A turn makes its move through `ruleset/make_move.py`, so the game package names neither a Datasworn roll type nor a Datasworn move. `roll_move` rolls it: a progress roll on its track, or an action roll with its stat, bonus, and adds. `resolve_move` resolves its outcome with any chained move and boasts.

- **Action roll.** `ruleset/rolls.py` → `roll_action`: one d6 plus the stat, at most 10, against two d10. `roll_progress` rolls a progress track.
- **Momentum burn.** After a roll the player is offered a burn when the move's Datasworn data allows it (`allow_momentum_burn`: every action roll, no progress roll) and momentum would better the result (`ruleset/rolls.py` → `can_burn_momentum`).
- **Rolls without a stat.** A move whose Datasworn roll options name no stat rolls with what they name, whatever stat the Brain gives: a condition meter, such as supply for Check Your Gear, Set a Course, and Make Camp, or the targeted connection's rank (Develop Your Relationship). See `ruleset/roll_sources.py` → `roll_source_without_stat`.
- **Ways to roll.** A move's Datasworn conditions are its ways to roll, each with the book's words for when it applies, and the Brain sees them that way (`ai/brain.py` → `_ways`). A way whose method picks among stats, as Heal's "Mend your own wounds" rolls the lower of iron and wits, is answered with the method's name, and the engine rolls with the stat it picks (`ruleset/roll_sources.py` → `roll_by_method`). A roll the engine makes itself, such as a follow-up move, takes what each way's method picks and, where the player would choose, the highest (`best_roll_option`).
- **Dice.** Each layer keeps its dice in its own `dice.yaml`. `ruleset/dice.yaml` holds the action and challenge dice, the score cap, and the result for each number of challenge dice beaten (`results_by_dice_beaten`, which a momentum burn and a downgrade in a bad spot also read). Mythic's are in `gamemaster/dice.yaml`, the Adventure Crafter's in `crafters/dice.yaml`. The ticks per box of a track are in `ruleset/progress.yaml`.

### Outcomes and effects

`ruleset/move_outcome.py` → `resolve_move_outcome` reads a list of effects per move and result from `ruleset/move_outcomes.yaml`. A result that changes nothing has an empty list.

- **Simple effects** (momentum, resources, progress, the combat position in `WorldState.combat_position`) are pure data. Adding a simple move is yaml only: its outcomes, its category in `ruleset/move_categories.yaml`, its availability, and, when it marks progress, its track's category in `ruleset/track_moves.yaml` (Progress tracks below).
- **Complications.** Where a weak hit costs a complication rather than a resource, the outcome carries a `complication` effect: Gather Information (a complication or a new danger), Compel in both rulesets (a demand in return), and Make a Connection (a complication or cost). The narrator receives it as a consequence it must tell, worded from the move text in `engine/consequence_templates.yaml`. It may also start a complication clock (`docs/gamemaster.md`, Complication clocks).
- **Complex outcomes** (suffer, threshold, recovery) use named handlers in `ruleset/move_handlers.py`; classic Sojourn has its own in `ruleset/sojourn.py` (Sojourn below). The suffer and threshold handlers serve Endure Harm, Endure Stress, Face Death, and Face Desolation, which the engine makes as follow-up moves (Harm, stress, and death below), and the companion moves and Withstand Damage, which no turn reaches yet (roadmap step 19).
- `ruleset/move_effects.py` parses and dispatches the effects, Pay the Price included (`ruleset/pay_the_price.yaml`).
- **Classic's outcomes** are the classic ruleset's (`move_outcome_overrides`, keyed by ruleset), so Delve, which plays classic, endures harm and faces death as classic does (`ruleset/outcome_result.py` → `move_outcome_config`).

### Tables a move rolls

- **Its own tables.** A move rolls the tables Datasworn carries inside it (`ruleset/moves.py` → `Move.tables`), keyed by their Datasworn names: Pay the Price, the tables of Endure Harm and Endure Stress, the oracle moves Make a Discovery, Confront Chaos, and Reveal a Danger (`oracle_moves`), and Take Decisive Action's table.
- **Suggested tables.** A move also offers the tables it suggests where the setting chain holds them (`Move.suggestions`, `ruleset/moves.py` → `move_table`, `offers_table`): Starforged's Pay the Price suggests Story Complication and its Gather Information Story Clue, which Sundered Isles takes from Starforged.
- **The `table` effect** rolls one of them: Story Clue on a hit on Gather Information, and Take Decisive Action's table on its weak hit, whose cost row costs a suffer move (`move_table_rows` in `ruleset/move_outcomes.yaml`, `ruleset/move_effects.py` → `roll_move_table`).
- **No site yet.** A miss on Delve's Escape the Depths reveals a danger, and the danger rerolls the rows that send to a site's theme or domain card, since no site exists (`reroll_prefixes`).
- **Oracle results for the narrator** (Pay the Price, a story complication, a row of Endure Harm or Endure Stress) reach it under the table's Datasworn name (`ruleset/move_effects.py` → `roll_oracle_result`). Classic's row that says to roll again and make it worse, which Datasworn leaves as text, is matched by `worse_reroll_prefixes` in `ruleset/pay_the_price.yaml` and told as the next result made worse.
- **The move's text.** The narrator also receives the move's own text for the result as `<move_outcome>` (`ruleset/moves.py` → `outcome_text`); the engine has already applied its choices and numbers.

### Consequences

Every effect but the combat position records what it did as a structured consequence (`models_base.py` → `Consequence`): a kind, which is the key of its label in `consequence_labels` in `engine/ai_text.yaml`, and the values the label is filled with, such as the meter and amount or the NPC's name. The narrator's result, the metadata call, and the engine's memories read the label.

`ruleset/consequences.py` → `generate_consequence_sentences` picks the narrator's sentence from `engine/consequence_templates.yaml` by kind and values, never by reading the label back:

- a loss of health or spirit is light or heavy by `meters.heavy_loss_amount` in `ruleset/meters.yaml`;
- a bond's progress, a sealed or cleared bond, and a disposition shift are told about their NPC;
- a marked or cleared impact is told by its label;
- a kind with no sentence (progress, experience, a legacy reward, a follow-up move, an oracle row, a companion's meter) reaches the narrator only as its label.

### Datasworn mechanic naming

Datasworn is the spec for mechanical behaviour, not for the shape of the Python.

- A Datasworn move becomes a formal move in `ruleset/move_outcomes.yaml` when it is a player choice the Brain can classify, with a structured outcome (for a move without a roll, a list of effects under `no_roll`), or a move the engine makes as a follow-up, such as the suffer and threshold moves, which the Brain is never offered (`never` in `ruleset/move_availability.yaml`).
- A `no_roll` or `special_track` move that fires by itself when a mechanical condition becomes true becomes an engine trigger named for what the code does, such as `advance_menace_on_miss`. It reaches the mechanic directly, not through the move-outcome pipeline.

### Moves without a roll

A move named in `offered_without_roll` in `ruleset/move_availability.yaml` is offered by its availability rule like any other. A turn that names it makes it without dice (`ruleset/make_move.py` → `plays_without_roll`, `make_move_without_roll`):

- Its `no_roll` effects apply, progress on its track included. There is no momentum burn, position, or effect.
- The turn then goes on as a dialog turn does (ARCHITECTURE.md, Turn pipeline).
- The narrator gets the consequences as `<consequence>` tags, under the scene type `unrolled_move` with the task `task_unrolled_move` in `prompts/tasks.yaml`.
- For the game master the outcome is `unrolled_move`, one of `outcomes.unrolled` in `gamemaster/outcomes.yaml`: chaos stays, a revelation lands (`story_state.revelation_outcomes`), and the engine's memories and the scene context tell the move by its action phrase (`action_phrases` in `ruleset/answers.yaml`).
- The NPCs in the prompt take their stance from the move's category, as in an action prompt; a dialog takes the social one.
- A dialog turn whose Brain names such a move with `dialog_only` plays as dialog.

Reach a Milestone is the one such move today (Progress tracks below).

## Progress tracks

`ProgressTrack` holds rank, ticks, and status (active, completed, failed, and bonded for a connection). Ticks per mark by rank are under `ticks_per_mark` in `ruleset/progress.yaml`.

**Starting a track.** The background vow becomes a track at creation. The moves that create tracks are listed in `ruleset/track_moves.yaml` (`track_creating_moves`) and start them after the roll (`ruleset/tracks.py` → `start_track`): a vow, a fight, an expedition, or a journey whatever the result; a connection only on a hit (`tracks_started_on_a_hit`), as Make a Connection says. Undertake an Expedition and classic Undertake a Journey both start a track and mark it: they continue the track the Brain names in `target_track`, and start one only when it names none, which then takes the move's progress (`ruleset/tracks.py` → `apply_progress_and_legacy`).

**Which track a move works on.** A move's Datasworn track category maps to a track type through `ruleset/track_moves.yaml` → `track_types_by_category`. Where several tracks of that type are active, the Brain names one by its track id (`target_track`). Availability offers such a move only while its track exists, so `find_progress_track` raises when it finds none. Datasworn gives a track category only to progress rolls, so an action move that marks progress (Strike, Clash, Gain Ground, Undertake an Expedition, Undertake a Journey, Delve the Depths, and the scene-challenge moves) names its track's category in `progress_mark_categories` in the same file, taken from the progress roll of its own move category.

**Lifecycle.** `ruleset/tracks.py` → `find_progress_track` and `complete_track` handle it: completing a combat track clears the combat position, and completing a vow resolves its linked threat (`ThreatData.linked_vow_id`).

**Reach a Milestone.** Both rulesets make it without a roll when the character makes significant progress on a quest. It marks progress once on the vow the Brain names, by that vow's rank (`ticks_per_mark`), as the move says. The books set no limit on how often, so the Brain may name it whenever the player claims such headway (`brain_trigger_hints` in `engine/ai_text.yaml`, with the milestones both books name). The narrator is told the milestone (`milestone` in `engine/consequence_templates.yaml`). Fulfill Your Vow rolls against these marks, so a vow is fulfilled in play.

**Progress rolls.**

- A hit, strong or weak, completes the track, as the moves have it (`ruleset/tracks.py` → `resolve_progress_roll`), except a connection, which Forge a Bond's hit bonds instead (`tracks_bonded_on_a_hit` in `ruleset/track_moves.yaml`).
- On a miss a fight is lost (End the Fight, Take Decisive Action). Fulfill Your Vow, Starforged's Forge a Bond, Finish an Expedition, and Reach Your Destination recommit: the track keeps one box in classic and loses as many boxes as the lower challenge die in Starforged, and its rank rises by one below epic (`recommit_on_miss` in the move's entry in `ruleset/move_outcomes.yaml`, `ruleset/tracks.py` → `recommit_track`).
- Take Decisive Action in a bad spot counts a strong hit without a match as a weak hit, and a weak hit as a miss (`downgrade_in`, `ruleset/rolls.py` → `downgrade_in_position`).

**Fights.** A fight is its combat track. Enter the Fray sets who is in control on every result, completing the track ends the fight, and a successor starts outside it. Classic counts the progress its Strike and Clash mark as harm: they inflict 1 harm as one mark and +1 harm as a second, so classic's Strike marks once on a weak hit where Starforged's marks twice (`move_outcome_overrides` in `ruleset/move_outcomes.yaml`). A deadly weapon's 2 harm is not modelled.

**Swear an Iron Vow.** A miss tells the narrator the significant obstacle before the quest (`obstacle`); classic's also takes -2 momentum, its option to press on.

**Scene challenges** (Starforged, Sundered Isles) are configured but not playable yet. Begin the Scene has no roll and never reaches the Brain, so no scene-challenge track exists, the moves that need one are never offered, and the tension clock their misses should fill does not exist (roadmap step 9k).

### Bonds and connections

A connection's track carries an NPC's bond and has the NPC's id (`ruleset/bond.py` → `connection_track_id`), so Make a Connection needs the NPC as its target. `get_npc_bond` reads that track's filled boxes; `NpcData` has no bond field.

- **Forge a Bond.** Its hit bonds the connection; its weak hit seals the bond at once and tells the narrator that they ask something more first (the `bond_request` effect).
- **A bonded connection stays**, as Starforged has it. It keeps its progress, so the NPC's bond holds; it aids with `bonded_add` instead of `add` (`ruleset/roll_bonuses.yaml`, the book's Bolster their influence); Make a Connection does not make it again (`ruleset/bond.py` → `connection_track` finds an active or bonded one); and `/tracks` names it (`bonded_tracks`).
- **Develop Your Relationship** has two branches. With a bond it rolls +the connection's rank for the bonds legacy track; the Brain is offered it only while a bonded connection exists (`bonded_track` in `ruleset/move_availability.yaml`) and is refused it for an NPC without a bond, since `ruleset/roll_sources.py` → `roll_source_without_stat` rolls a rank only for a bonded connection. Without a bond it marks progress by the connection's rank without a roll (`without_bond` in its entry in `ruleset/move_outcomes.yaml`); the engine makes this branch when Test Your Relationship's hit makes the move as a follow-up (`ruleset/make_move.py` → `_chain_without_bond`).
- **Classic Ironsworn** has no connection tracks. Its Forge a Bond is an action roll on the target NPC. A hit seals a bond as a bonded connection at full progress (`ruleset/bond.py` → `seal_bond`), so the NPC's closeness is 10. The hit also marks a tick on the bonds legacy track, and a strong hit takes +1 spirit. The weak hit tells what they ask first, as Starforged's does.
- **Classic Test Your Bond** is offered only while a bond exists (`bonded_track`). Its weak hit tells that they ask proof of loyalty (`loyalty_test`). Its miss clears the bond and pays the price (`clear_bond`): the connection is removed, so the NPC's closeness is 0, and a later Forge a Bond seals a new one.
- **No connection, no move.** The Brain is refused a move that marks, raises, or clears a connection for an NPC without one (`ruleset/move_outcome.py` → `needs_a_connection`).
- **Aid.** A connection aids by its ruleset's rule (`connection_aid` in `ruleset/roll_bonuses.yaml`): in Starforged +1 and +1 momentum on a hit, +2 once bonded; in classic +1 where the move adds it for a shared bond.
- **Two NPCs found to be one person**, through a correction's merge or a duplicate absorbed after a rename (`gamemaster/npc/lifecycle.py` → `absorb_npc`), become one. The NPC that stays keeps the connection with the most progress and takes over the other's memories, clocks, place on the characters list, and the vows sworn with its bond's aid.

### The ruleset's words

Track types, track statuses, and ranks are the ruleset's words. Code outside the ruleset names none of them and asks instead:

- `ruleset/tracks.py`: the active tracks, the chapter record's vows (`vow_record`), whether a thread follows a vow (`is_vow_thread`), the background vow a new character swears (`swear_background_vow`), and the end of a progress roll (`resolve_progress_roll`);
- `ruleset/bond.py`: a bonded connection, and whether a move starts one;
- `ruleset/move_availability.py`: the moves a situation offers;
- `ruleset/progress.py` → `ranks`: the ranks in order, which every table keyed by rank in the ruleset's yaml follows.

## Stats

A character's stats are the ruleset's. Their names and descriptions come from the ruleset's Datasworn rules (`rules.stats`; Delve plays classic's, Sundered Isles Starforged's), read by `ruleset/stats.py` → `stat_descriptions`. A new character arranges the numbers of `creation_array` in `ruleset/stats.yaml` among them (`validate_stats`); the creation form derives its total and range from that array. The Brain sees each stat with its description and the character's values by the abbreviations in the same file, and answers `ai_text.no_stat` in `engine/ai_text.yaml` for a move that rolls no stat.

## Meters

A character's meters are the ruleset's. The condition meters come from its Datasworn rules (`rules.condition_meters`, each with its range and starting value; Sundered Isles plays Starforged's, Delve classic's), and momentum from `ruleset/momentum.yaml`. `Resources` holds them by name (`Resources.meters`), with no meter as a field of its own.

`ruleset/meters.py` does their arithmetic:

- `lose` and `gain` keep a condition meter within its range;
- `adjust_momentum` keeps momentum between its floor and its max; every marked impact lowers the max by one (`max_momentum`), and a gain stops at the lowered max;
- `reset_momentum` burns momentum to its starting value less one per impact, never below `reset_floor`;
- `in_crisis` reads the meters that `meters.crisis_at_zero` in `ruleset/meters.yaml` names.

A move's effect, a suffer move, or a recovery acts on a meter by its name. A suffer or recovery move whose meter is no condition meter of the ruleset, such as a companion's health, changes only momentum, and a move effect naming such a meter raises; no move the Brain is offered names one yet (roadmap step 19).

What the narrator and the player are told of a meter is keyed by its name: its descriptions and the flag the narrator gets while it stands at 0 in `engine/narrator_status_descriptions.yaml`, the player's in `status_descriptions.meters` in `engine/status_descriptions.yaml`, and the sentences of a gain or a loss in `engine/consequence_templates.yaml`. A meter without a sentence reaches the narrator only as its label.

## Impacts

Impacts (wounded, shaken, and the rest) are the ruleset's own, read from its Datasworn rules with their label, the meters they keep from recovering, whether they are permanent, and their description (`ruleset/impacts.py` → `get_impacts`). `ruleset/impacts.py` → `apply_impact`, `clear_impact`, and `blocks_recovery` apply them. The narrator receives each marked impact with its description as `<impact>` in `<character_state>` (`prompt_shared.py` → `_impacts_block`). Every marked impact lowers max momentum by one (Meters above).

- **Marked by** Endure Harm and Endure Stress, Face Death and Face Desolation, and supply running out (Harm, stress, and death below).
- **Cleared by** Heal on a hit (wounded), Starforged's Hearten and Resupply on a hit (shaken, unprepared), classic Sojourn, marked conditions among its picks (Sojourn below), and, for a burden, completing its vow.
- **A marked condition keeps its meter from rising**, as the rules of classic and Starforged both say: Endure's exchange takes momentum instead; a recovery move clears the condition first and gains its smaller amount; any other gain of that meter, such as Starforged Sojourn's, is dropped (`ruleset/move_effects.py`).
- The consequence of a marked or cleared impact carries the impact's label (`ruleset/impacts.py` → `impact_consequence`).

### Sojourn

Classic's Sojourn lets the player choose two of its recover actions on a strong hit and one on a weak hit, one more with a shared bond, and roll +heart again for one of them. The engine chooses for the player (`ruleset/sojourn.py`, the `sojourn` handler; its actions and amounts in `relationship/sojourn` in `ruleset/move_outcomes.yaml`):

1. Clear a Condition, for each marked condition in the order they were marked (Mend, Hearten, Equip: clear it and +1 of its meter).
2. Recover, for the condition meters below their maximum, the lowest first (+2).
3. Plan's +2 momentum last. It never takes a quest.

A shared bond is the bond whose aid the Brain gave the roll (`ruleset/bonuses.py` → `bond_of_bonus`); it also adds +1 to the second roll. That roll is for the first pick: a strong hit takes +2 more for it, a weak hit +1 more, and a miss loses its benefit, so a condition it would have cleared stays and keeps its meter from the later picks. Starforged's Sojourn still takes fixed gains (roadmap 9t.2).

## Harm, stress, and death

**Suffering.** Every loss of health, spirit, or supply goes through `ruleset/suffer.py` → `suffer`, except the extra loss of Endure's own miss, which its handler takes. What the meter cannot take past 0 costs momentum, and supply reaching 0 marks unprepared (`ruleset/suffer.yaml` → `exhausted_impacts`).

**Enduring.** Lost health or spirit is then endured: in classic every time, as its Endure Harm and Endure Stress begin with the loss; in Starforged and Sundered Isles when the meter stands at 0 (`endure_always` in the moves' params in `ruleset/move_outcomes.yaml`). Enduring is a follow-up move: `suffer` lists it in `OutcomeResult.follow_up_moves`, and `ruleset/move_outcome.py` → `make_follow_up_moves` rolls it with the higher of its stat and its meter and resolves it through the suffer handler. It comes after the turn's move, its chained move, its boasts, and any full menace track.

**A miss at 0** marks the first unmarked impact the move offers. When both are marked, the handler rolls the move's Datasworn table, tells its row, and acts on the rows `ruleset/suffer.yaml` → `table_rows` names:

- mortal harm and being overwhelmed make Face Death or Face Desolation;
- unconsciousness makes Face Death while a combat track is open;
- giving up forsakes the newest active vow (`ruleset/tracks.py` → `forsake_vow`);
- dying starts a two-segment clock of type `dying`. It fills once per turn after the turn's move, whether the turn rolls or not, ends when health is above 0, and makes Face Death when full (`suffer.py` → `tick_dying_clock`).

**Face Death and Face Desolation** roll +heart through the threshold handler. A strong hit returns; a miss ends the game; a weak hit makes Swear an Iron Vow, whose outcome applies. In classic a miss on that vow ends the game too. Otherwise the character returns bound to an extreme vow (`start_bound_vow`) and marks its burden (cursed or tormented in classic, doomed or tormented in Starforged), which clears when the vow is completed.

**Crisis.** Health and spirit at 0 bring only the crisis status (`game/finalization.py` → `update_crisis`).

**Turns without a roll.** A bond test a forsaken vow asks, the dying clock, a full menace track, and their follow-up moves resolve before the narrator writes. The narrator receives each consequence as a `<consequence>` tag, its sentence or, for a kind without one, its label (`ruleset/consequences.py` → `consequence_texts`), and the status flags the action prompt has.

The fixed choices this takes are in `docs/divergences.md`.

## Legacy and experience

A ruleset's legacy tracks are the special tracks its Datasworn rules name and do not call optional. They are kept by name on the campaign (`CampaignState.legacy`, built by `ruleset/legacy.py` → `new_campaign`):

- Starforged: quests, which Fulfill Your Vow marks by the vow's rank, one rank lower on a weak hit; bonds; discoveries.
- Classic: bonds, which Forge a Bond marks.
- Delve's optional failure track waits for step 13b, which marks it.

Their numbers and experience are in `ruleset/legacy.yaml`, applied by `ruleset/legacy.py` → `mark_legacy`, `apply_threat_overcome_bonus`, and `advance_asset`. A legacy track earns experience as its boxes fill only where its Datasworn rules tag it so (`experience_tag`), as Starforged's three are. Classic's bonds earn none: classic earns experience by its own rule, Fulfill Your Vow marking experience by the vow's rank, one rank lower on a weak hit (`experience_by_rank` in `ruleset/legacy.yaml`, applied by `ruleset/tracks.py` → `apply_progress_and_legacy`).

The player spends experience with `/advance new <asset>` or `/advance upgrade <asset>`. `advance_asset` refuses an asset the setting lacks, a new asset already held, an upgrade of an asset not held or with every ability enabled, and an advance the experience does not cover; the player hears which from `strings/advance.yaml`.

## Boasts

Draw the Circle takes the boasts the player declares, which the Brain reads into its `boasts` field: up to two on a strong hit, one on a weak hit, none on a miss. Each gives +1 momentum and has its cost from `ruleset/boasts.yaml` (`ruleset/boasts.py` → `apply_boasts`).

## Assets

A path or asset has the abilities Datasworn enables by default, until an upgrade enables the next in order; `GameState.asset_abilities` records them (`ruleset/assets.py`). `ruleset/bonuses.py` offers, in a `<bonuses>` block of the Brain's prompt, every enabled ability whose text grants an add and the aid of every active or bonded connection (from `ruleset/roll_bonuses.yaml`). The Brain names at most one by id in `bonus_id` when the action clearly meets its condition. The engine checks the id and takes the number from the rule text, counting momentum on a hit only when the text ties it to the same add. Only adds are modelled (`docs/divergences.md`).

## Threats

A threat has a menace track, as Delve, classic's expansion, gives one (`ruleset/threats.yaml`). The departures from the books are in `docs/divergences.md`.

**Advancing.** A threat advances:

- on a miss, when a vow is sworn against it (`ruleset/threats.py` → `advance_menace_on_miss`);
- when a random event aims at it;
- by chance each scene, for delay (`tick_autonomous_threats`).

In classic every advance makes Delve's Advance a Threat: a roll on its table, read from Delve's file whatever the setting (`threats.advance_a_threat`), marks menace once or twice and tells its development, and a match also exposes a surprising aspect. In Starforged and Sundered Isles an advance marks one menace, until step 9v gives them their book's campaign clocks. Where the setting has a table for the threat's category (Delve's nine, under `threats.category_oracle_collection`), the advance carries a roll on it as what the threat does.

**Telling.** Every advance reaches the narrator as `<threat_advance>`: an advance on a miss in the same turn, one a random event aims at before that turn's roll, and an autonomous tick, which comes after narration, in the next turn, marked as off screen (`WorldState.pending_threat_events`, `take_pending_threat_events`).

**A full track.** When the last box fills, `resolve_full_menace` makes the player forsake a vow sworn against the threat (`ruleset/tracks.py` → `forsake_vow`), which costs spirit by the vow's rank in classic and `suffer.forsake_vow.cost` in Starforged. A threat no vow is sworn against achieves its goal, which the narrator is told (`threats.goal_achieved`). A full track is handled while a turn resolves, with or without a roll, before the narrator writes, so the narrator tells the forsaken vow; a track that its own tick fills at scene end waits for the next turn.

**A forsaken vow and a bond.** A classic vow that a bond aided when it was sworn (the bond the Brain gave the Swear an Iron Vow roll, kept as `ProgressTrack.vowed_to`) asks Test Your Bond once it is forsaken. The first later turn aimed at that NPC, with or without a roll, rolls it +heart on them before the turn's other follow-up moves, and the narrator is told why (`ruleset/move_outcome.py` → `make_due_bond_test`, `suffer.forsake_vow.bond_test` in `ruleset/suffer.yaml`). This does not happen when the turn's own roll is that test or the bond is gone by then.

**A vow against a threat.** A threat gets its vow as Delve has it, once the threat is introduced and the player swears a vow to see its goal undone. The Brain sees the active threats in `<dangers>`, each with its menace and the vow sworn against it, and names in `target_threat` the one a vow it swears is against, from those without one. `ruleset/tracks.py` → `start_track` links the new vow to it (`ruleset/threats.py` → `vow_against`). A threat no vow is sworn against does not advance on a miss, but it ticks on its own and can fire `threat_menace_phase` keyed scenes.

**Spawning.** New threats come from two sources, which ask the ruleset for a new danger (`docs/gamemaster.md`, Questions to the ruleset):

- A random event whose focus is in `gamemaster/random_events.yaml` → `danger_foci` (currently `pc_negative` and `npc_negative`) names the danger after the event's Mythic action and subject (`gamemaster/random_events.py` → `spawn_danger_from_random_event`).
- An Adventure Crafter plot point in `crafters/adventure_crafter.yaml` → `danger_plot_points` (A New Enemy, Hidden Threat, Enemies, Hunted, A Problem Returns), rolled in the turning points a chapter's blueprint rolls at its start, leaves the name to the ruleset, which rolls a Datasworn cascade on the setting's `oracle_paths.threats` (`ruleset/threats.py` → `add_threat`).

The cascade (`setting/cascade.py` → `roll_oracle_cascade`) rolls each table with its rows' own roll instructions (a "Roll twice" row gives both results) and follows the first markdown-link id onward. Delve's `threat/category` leads into nine sub-tables, and the one it reaches is the threat's category. Starforged, classic, and Sundered Isles take the category that `threats.by_origin` in `ruleset/threats.yaml` gives the plot point, beside the rank of every origin. The ruleset dedupes on `ThreatData.creation_source` and lets the two sources spawn a threat only while fewer than `threats.max_open_emergent` of the threats they spawned are active.
