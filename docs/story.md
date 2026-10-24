# Story structure

How a chapter gets its plan from the Adventure Crafter, how its revelations land, and how chapters and successions carry a campaign on. The crafters live in `crafters/` and its yaml, the acts in `story_state.py`, and chapters and succession in `game/`, with succession's mechanics in `ruleset/succession.py`. Deliberate departures from the books are in `docs/divergences.md`.

## Blueprint

At the start of a chapter `crafters/blueprint.py` → `assemble_blueprint_seed_from_ac` rolls one Adventure Crafter turning point for each act of `blueprint.act_phases` (`crafters/adventure_crafter.py` → `roll_turning_point`) into a frozen `BlueprintSeed`.

- **Voicing.** `ai/blueprint_voicing.py` → `call_blueprint_voicing` turns the seed into a setting-specific `StoryBlueprint` in one structured call. It asks for a fixed number of acts, of revelations (one per act), and of possible endings, and asks once more when the answer's counts are wrong (`docs/ai.md`). When the voicing fails, the chapter plays without a blueprint, so without acts, revelations, or an end.
- **What the voicing gets.** Each act's turning point, with its beats, its plotline, and whether it opens, advances, or concludes that plotline, as the Adventure Crafter rolled it (`TurningPoint.plotline`, `opens_plotline`, `concludes_plotline`).
- **Spawns.** After each turning point, `crafters/turning_point_spawns.py` adds its keyed scenes, dangers, and clocks.
- **Tone.** The player picks a tone at character creation, from `story.tones` and preset to the setting's `default_tone`; the narrator receives it as its tone authority.
- **Mid-chapter.** The Adventure Crafter is not consulted in the middle of a chapter. Pacing there runs on random events, the pacing hint, clocks, threats, the scene structure, and the Director's reflections.

## Revelations

**Seeding.** Each act has one revelation, seeded from a plot point of its own turning point: the first that has a keyed scene once the chapter's turning points have spawned theirs, else the first that is no special result (Conclusion, None, Meta). With neither, the voicing takes it from the central conflict.

**Landing.** The engine decides when a revelation lands (`story_state.py` → `land_revelation`):

- in its act, when its keyed scene fires; a keyed scene that fired in an earlier act makes it ready at once;
- at the latest on the last scene of its act;
- only on a turn whose outcome `story_state.revelation_outcomes` in `gamemaster/story.yaml` names, today every outcome but failure. A failure holds it to the next turn that does not fail, even past its act.
- One lands per turn, the oldest first.

**Telling.** The narrator receives it as a `<revelation>` tag beside the consequences, which it must tell; the engine marks it revealed in the same turn, and the Director runs after it (`docs/ai.md`). A momentum burn decides again with the better result, a correction of a misread input plays the turn again, and a state correction tells the same revelation again (`TurnSnapshot.revelation`).

## Act transitions

Act transitions are computed by the engine at the end of every turn, whether or not the Director runs. An act ends at the last scene of its range (`story_state.py` → `check_act_transition`, called in the scene-end bookkeeping), so the Director after that turn and the next turn's prompts already see the next act (`get_current_act`). `check_story_completion` then decides whether the story is complete (Chapters below).

## Adventure Crafter tables

The primitives are in `crafters/adventure_crafter.py`, with engine config in `crafters/adventure_crafter.yaml` and data in `data/adventure_crafter.json`:

- five themes from a d10 table; the yaml `theme_die_table` is checked against the JSON's `random_themes` on first load;
- plot points looked up by theme and roll, with the special ranges Conclusion (1 to 8), None (9 to 24), and Meta (96 to 100);
- the handlers of the seven meta plot points, in `crafters/meta_plot_points.py`.

**A turning point.** `roll_turning_point` combines two to five plot points. A roll on `plotlines_list_template` opens a new plotline on New Plotline or when no plotline advances; otherwise it takes the advancing plotline with the fewest turning points (`docs/divergences.md`). Then, per plot point, it rolls a theme by `plot_point_theme_priority` (alternating for the fourth and fifth) and 2d10 for the lookup. A Conclusion flips the plotline from advancement to conclusion, and counts as None on a plotline the turning point just opened.

**The lists.** `NarrativeState` holds the `characters_list`, shared with Mythic's random events and extended with `ac_status`, and the Adventure Crafter's own `plotlines_list`. The meta handlers change both in place, but no turning point calls them yet, so a Meta result has no effect (`docs/divergences.md`). `dispatch_meta` and the Characters List template wait under an orphan-symbol carve-out for roadmap step 9j.7.

**Character crafting.** The character-crafting tables are pure helpers (`roll_character_traits`, whose `CharacterTraits` holds one or two identities and descriptors), under the same carve-out until roadmap step 11.

## Chapters

A chapter is what Mythic and the Adventure Crafter call an adventure within a campaign: one blueprint.

**The end.** A chapter ends by scene count, not when its plotlines are resolved. The story is complete once the scene count reaches the end of the last act's range; an earlier act that has not ended yet ends then too. Once the story is complete, the player is offered the epilogue and a new chapter (`story_state.py` → `check_story_completion`; roadmap step 32b reads this against the books). The fallback of `story_state.completion_overrun_scenes` scenes past that end matters only for a blueprint of one act.

**Closing.** `game/chapters.py` → `start_new_chapter` closes the old chapter into a `ChapterSummary`, a record the engine writes from its own data. It opens with the blueprint's central conflict, then lists the vows fulfilled, forsaken, and still sworn; the plotlines concluded; the open threads; the people with disposition and bond; the dead; the threats with their menace and those overcome; and where the chapter ended. The title is the chapter's number.

**What starts fresh** (`_reset_chapter_mechanics`): the scene count, the chaos factor at Mythic's starting value of 5, the session log and narration history, the blueprint and the keyed scenes its turning points spawned, the time of day, the location history, the facts, and the Director's guidance.

**What carries over** as it stands: progress tracks, threats, impacts, assets, threads, the characters and plotlines lists, health, spirit, supply, momentum, and clocks, since Ironsworn and Starforged recover only through moves. Experience and legacy tracks span the whole campaign, and the generated places stay with the world. NPCs and their connection tracks carry over through `game.npcs` and `_prepare_npcs_for_new_chapter`.

A game that is over continues through succession, never a new chapter.

## Succession

When the protagonist dies (on a miss at Face Death or Face Desolation, or in classic on a miss on the vow sworn there; `docs/ruleset.md`, Harm, stress, and death) or retires, the game records it as its `end_reason` (death, despair, or retire); the game is over while it is set. The campaign then continues with a new protagonist in the same world, in two steps gated by `CampaignState.pending_succession`.

1. **Preparing.** `game/succession.py` → `prepare_succession`, which the server calls as soon as a turn ends the game or the player retires, archives the predecessor into `campaign.predecessors` and locks the inheritance rolls onto that record, which keeps the inheritance the same across a reload.
2. **Starting.** `start_succession_with_character` reads those rolls and closes the chapter.
   - **Kept:** the NPCs per `ruleset/succession.yaml`, with a share of their connection tracks in Starforged and without their bonds in classic (`connections_kept`); every threat; the threads that were not the character's vows or creation; and, of the characters list, the NPCs who stay.
   - **Gone:** resources, impacts, assets, and the other progress tracks leave with the character; every clock is cleared with its keyed scenes, unlike at a chapter start; the keyed scenes of the old chapter's turning points go, as at a chapter start; a fight ends with its combat position; the scene count, chaos factor, time of day, and facts restart.
   - It then seeds the successor's legacy, replaces the character, writes the opening, and clears the flag.

The mechanics live in `ruleset/succession.py` → `build_predecessor_record`, `run_inheritance_rolls`, `seed_successor_legacy`, `apply_npc_carryover`. Unknown roll outcomes and NPC statuses raise.
