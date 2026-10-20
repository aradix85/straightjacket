# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log starts at 2026.09.24.0, the restart after a four-month pause. Earlier releases, back to the fork from EdgeTales, and the longer text of entries that were later shortened are in git history (`git log -p CHANGELOG.md`).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

## [2026.10.20.28] — 2026-10-20

Step 9r: where each rule comes from (roadmap Decisions, From EdgeTales to the sources, the user's aim). Every rule and structure that decides facts, pacing, or behaviour in the fiction was listed with its origin, by AUDIT.md's working method, in four hit-lists: the NPC rules (75 rows), scene, story, and world (141), the ruleset (167), and the engine's values, the prompts, and the AI calls (146). They cover every section of the 36 yaml files of `gamemaster/`, 2 of `crafters/`, 20 of `ruleset/`, 16 of `engine/`, and 2 of `emotions/`, the rules held in Python in those packages, `game/`, and the Director, and every rule of `prompts/*.yaml`; a few items stand in two lists. Each was read at its consumer, dated with `git log -S` here and in EdgeTales, grepped in the repository's first commit (a3b263f, 0.31.0, the code of the fork) and in EdgeTales as of 31 March 2026 with its history to the fork date, read against the books' data in `data/`, and against the design document (version 2.4, from the user's repository `aradix85/narrative-rpg-engine`), which is theory that gives a rule its aim and not its form (the user's words). About 130 rows came from EdgeTales without a source and about 70 were the engine's own rules without a register entry; the rest follow a source, are registered, are technique, or are prose craft. The design document holds none of Kishōtenketsu, the three acts, the epilogue, the revelations, the Director, memory importance and reflection, the creativity seeds, or the stance matrix; narrative direction from the game state and a bond out of four with a disposition are its ideas.

Where the findings went. 9j is NEXT STEP again, with 9j.11 (classic outcomes that depart from their moves: harm on Strike and Clash, the miss of Swear an Iron Vow and of Test Your Bond, Compel's price, Sojourn's picks, three starting assets), 9j.12 (the Adventure Crafter's themes, plotline choice, and list consolidation), and findings in 9j.2 (classic and Delve have no connection track, so every NPC's closeness stays 0 there, and no bond-keyed scene can fire) and 9j.6. Two new steps follow it: 9t, rules conformance for Mythic and Starforged (the chaos start from the vow's words, the New NPC event, Resupply, Sojourn, Test Your Relationship, Continue a Legacy, times a move's text names), and 9u, what the narrator still decides (emotional carry-through, the time rule, the final-scene, crisis, and zero flags, the player's wishes, `world_shaping` and world additions, the consequence sentences, genre physics, the background detail, the death vote). Findings also went to 10.2, 10b, 11.0 (what the Director decides at all, and when a reflection falls due), 11.1, 11b.2, 13, 13b, 13c, 14b, 14c, 30, 31, 32b, and 33. The register gains "Threats meet their end by engine rule", "Keyed scenes are the engine's", "Random events and plot points start dangers and clocks", "A New NPC event draws a known character", "The engine chooses the Adventure Crafter's plotline", "A successor inherits by engine rule", "Time of day is the engine's", "Revelations land by engine rule", "An AI Director steers the story and the NPCs", "The narrator gets less than the full relational context", "Narrative direction reads the meters and the outcome", and "The narration decides who dies"; "Fixed choices where the player would choose" and "Suffering takes fixed choices" name the fixed choices they missed, and four more entries widen to what they left out. "Chaos factor per turn" no longer claims that every start is Mythic's 5. AUDIT.md gains principle 6, every rule has a source, with its three passes and its Status line. The roadmap says where the design document is for later sessions.

Found by the lists and fixed, each with a test: a lore figure who appears in person stayed lore, since `reactivate_npc` promoted only background NPCs while `npc_status_groups.reactivatable` names lore too (`gamemaster/npc/lifecycle.py`); a threat overcome at three quarters of its menace or more was told to the narrator as overcome on every action turn after, and is now told once, from the vow that overcomes it (`ruleset/tracks.py` → `complete_track`, `overcome_under_pressure` gone); a nearly full progress or scheme clock pressed the position like a threat clock, and only threat clocks do now (`gamemaster/resolvers.py` → `_score_threat_clocks`); and the caps on the threats and clocks that random events, plot points, and complications spawn counted every spawned threat ever made, so after three a campaign never got another, and every spawned clock still listed, a fired one included, while they now count the open ones (`threats.max_open_emergent`, `clocks.max_open_emergent`, renamed from `max_per_chapter` and `max_clocks_per_chapter`). Renamed for what they do, without a change: `chapter.open_threads_max`, which keeps NPC memories, to `npc_memories_kept`, and `story_state.crisis_scene_offset` to `completion_overrun_scenes`. `docs/mechanics.md` now says that a chapter ends by scene count, not when its plotlines resolve, and gives the stance example as the yaml has it.

Waiting for the user: whether the death vote and its two yaml files may go (9u.9), and the questions of 11.0.

Quality gate: 1770 tests, coverage 95.06%. Save format unchanged. No Elvira run: the four fixes are held by their tests, and the rest changes no play.

## [2026.10.20.27] — 2026-10-20

Step 9s: NPCs are named by whole names. In 9i's Elvira run two NPCs moved along with the player without being in the scene: Morell's alias "The gate guard" counted as named by "gate", and Shona's "The young woman with the bucket" by "with" or "woman" in nearly every narration, so both gained memories of scenes they were not in, joined the Mythic characters list and the scene context, and came back through activation the next turn. A text now names an NPC when its name or an alias stands there as whole words, or a given name does: a capitalised word at the start of the name that is no title and no stopword, at least `fuzzy_match.named_in_min_word_length` letters long. A proper name keeps its capital, so an NPC called Hope or Wolf is not named by "hope" or "a wolf", and a short name inside a longer word names nobody (`gamemaster/npc/matching.py` → `stands_in`, `proper_name_words`, `named_in`). Every place that asked the question in its own way now asks this one: presence and moving along, which shared `named_in` already; the narration introducing an NPC (`parser.py` → `_mark_introduced_npcs`), which took any word of four letters inside any other word; an opening memory finding its NPC (`game/setup_common.py` → `seed_opening_memories`), which took the first NPC whose name held any word of the reference, a title included, and now asks `find_npc` and then `named_in`; the recursive activation through agendas and secrets; and activation's scores for a name, a given name, and an alias, which matched any substring. Activation reads the player's own words without regard to case, since a player may type a name in lower case. Gone with the old matching: `parser.min_line_length`, and `setup_common.part_name_min_length` with `SetupCommonConfig` and `engine/setup_common.yaml` (the user's consent). The project rule against orphan yaml keys no longer counts a module import as a reader, which had hidden that last key. The roadmap gains the decision "From EdgeTales to the sources" and step 9r, which is NEXT STEP, with 9j after it.

Quality gate: 1767 tests, coverage 95.02% to 95.07% by the random paths a run takes. Save format unchanged. No Elvira run: the tests hold the matching on the run's own names, and nothing else of a turn changes.

## [2026.10.20.26] — 2026-10-20

Step 9i: the engine settles a chapter's revelations, and Kishōtenketsu is gone (the user's choices, roadmap Decisions). Each act has one revelation, seeded from a plot point of its own Adventure Crafter turning point: the first that has a keyed scene, else the first that is no special result, else the voicing takes it from the central conflict (`crafters/blueprint.py`, `Revelation.act_number` and `keyed_scene_source` in place of `earliest_scene`). The engine lands it (`story_state.py` → `land_revelation`): when its keyed scene fires, at once when its act begins if that happened earlier, and at the latest on its act's last scene, but only on a turn whose outcome `story_state.revelation_outcomes` names (every one but failure, in the game master's words, so another ruleset keeps the rule), so a failure holds it to the next turn that does not fail; one per turn, the oldest first. The narrator gets it as a `<revelation>` tag beside the consequences, with one sentence in its rules that it must tell it; the engine marks it revealed and the Director runs that turn. A momentum burn decides again with the better result, a misread correction plays the turn again, and a state correction tells it again (`TurnSnapshot.revelation`). Gone: the revelation check (`call_revelation_check`, its schema and schema texts, its prompts, the role `revelation_check`, the cluster `judgment`), `get_pending_revelations`, `mark_revelation_used`, and the register entry "An AI call judges whether a revelation was told". Kishōtenketsu, which came from EdgeTales and skipped the Adventure Crafter, went with `gamemaster/story.py`, `assemble_blueprint_seed_kishotenketsu`, its phases and labels, `story.kishotenketsu_probability` (the tones are now `story.tones`), `StoryBlueprint.structure_type`, and the Director phases `ten_twist`, `ketsu_resolution`, and `resolution`, the last of which no act had; the blueprint keeps `act_phases`, rolls one turning point per act, and asks one revelation per act. Found and fixed: the Adventure Crafter's keyed scenes carried over chapters, so the cap per chapter counted the old ones and a later chapter could spawn none; a chapter and a succession now drop them, and a succession also drops the keyed scenes of the clocks it clears. The roadmap gains steps 32b (a chapter's structure from the books) and 37 (a ruleset that is not Ironsworn) and the decisions behind them; NEXT STEP is 9j.

Elvira, twenty turns of classic in the aggressor style on Sonnet, about $1.46 at full input price: the revelation of act 1 landed in scene 7 and that of act 2 in scene 14, each at its act's end, since their keyed scenes were bond thresholds (6 and 7) the run did not reach, and the judge found both conveyed (2 of 2); the third act was not reached, because two correction tests replayed a scene each. The audit scored 6.9 of 10. Its four problems are of kinds earlier runs found and none touches revelations: the Brain named iron for classic's Enter the Fray and was asked again, as designed; two NPCs changed place without being shown; one miss was told only in part.

Quality gate: 1757 tests, coverage 95.00% to 95.01% by the random paths a run takes, so `fail_under` stays at 94. The save format breaks.

## [2026.10.20.25] — 2026-10-20

Elvira runs only when a run makes a real difference to the work, and no more runs or turns than that needs (Sessions with the user). The twelve-turn run of the engine before 9i that 2026.10.20.24 announced is dropped: the decision does not hang on it, and the engine's behaviour before 9i is known from the code. It was stopped during its opening. Roadmap 9i.0 and the definition of done keep only the run after 9i.

Quality gate: 1758 tests, no code changed. Save format unchanged.

## [2026.10.20.24] — 2026-10-20

Step 9i begins with the user's decision and 9i.0. Decided: a revelation lands in the act of the turning point it was seeded from, when a trigger of its own fires there and at the latest at the act's end, and only on a hit, a miss holding it to the next hit (roadmap 9i.1). Elvira now measures whether the narration conveys a revelation: her token meter keeps the narrator's prompt of each turn, a revelation found in it reaches her judge, whose verdict gains `revelation_conveyed`, and her report gains a section with how many turns had one, how often it came across, and in which scene each first did (`docs/elvira.md`). Elvira runs on the real models again, only those a change truly needs (Sessions with the user); the runs earlier releases left open are not caught up. Play does not change.

Quality gate: 1758 tests, coverage 95.00%. Save format unchanged. No Elvira session yet; the twelve-turn run that measures the engine before 9i follows this release.

## [2026.10.20.23] — 2026-10-20

Step 9p closes with 9p.5, the 18 test files of the core, the server, and Elvira, and `tests/conftest.py`. The queries: private names imported on one line, 23 hits (`_parse_config` nine times, `_parse_move_availability_rule`, `_resolve_stance_category`, `_safe_name`, `_check_origin` four times, `_require_str` four times, `_send`, and `_session` twice); private calls through a module, 23, of which two reach code under test (`config_loader._parse_config`, Elvira's `runner._save_and_verify`) and the rest a test class's own methods; on lines of their own, 0; names in capitals, 59, of which the conftest's four `_CONFIG_DIR` and the rest the tests' own; patched private names, 5 (`i18n._strings` three times, Elvira's `_try_save`, and the retry's sleep, which stays); `parse_*_yaml`, 4, and `install_config`, 3, all in the conftest's configuration but a second `load_engine` in `test_web.py`; `stub_engine`, `stub_emotions`, and `stub_all`, the conftest's three fixtures and two users, none needing their values; imports from another test file, 0. Rebuilt on what the code does: `config.yaml` is read from a temporary file through `cfg()` and the role functions, the strings and the users through their own loaders and folders, a refused configuration of the game master or the ruleset through its accessor on a copied folder with one changed value (`change_config` in `tests/_helpers.py`, now also the fact-resolution refusals), the origin check through the WebSocket endpoint with the request's own host, the handlers' name check and quiet send through `handle_create_player` and a closed connection, the stance buckets and position baselines of every move through `action_kind`, a save's every field through one exact round trip, which a blueprint, an arc, and a combat position now join, and Elvira's turn record, spatial check, and failed load-back through `record_turn`, `check_npc_spatial_consistency`, and a short `run_session`. Joined: the config loader's refusals into one test, its typed reads into one, the narrative status's seven tests into two, the creation options' four into one, the session's chat helpers into one test per helper, the two highlight tests into the exact one, the two snapshot restores, the two round trips, and the user names' four refusal groups. Removed: `test_elvira_imports.py`, which checked that names are callable; a test of the helper's own default, three field round trips the exact one covers, two of the loader's caching, one of a class's base class, and one of a target NPC that `call_brain` already refuses. `stub_engine`, `stub_emotions`, and `stub_all` are gone, and `load_engine` installs what the accessors load. Three handler tests passed a key the handler never reads (`save_name`), and two of them asserted nothing; they pass `name` and assert the silence their names promise. Elvira's own event capture, report lines, and prompt lookup stay as unit tests of her tooling, which has no public route to them. Coverage now runs from 95.00% to 95.04% by the random paths a run takes, so `fail_under` stays at 94: at 95 some runs would fail a gate that may not be lowered. The roadmap's NEXT STEP is 9i. Play does not change.

Quality gate: 1757 tests, coverage 95.00% to 95.04%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.22] — 2026-10-20

Step 9p, 9p.6: the NPCs who return at a chapter are the ones the game keeps, so the copies the chapter made of them are gone, and with them two faults they hid. The chapter copied every active, background, and dead NPC before its opening and merged the copies back after it, under a fresh id where no NPC had the name; since the game keeps those NPCs, every name was there, and the merge added nothing (`game/chapters.py` → `_merge_returning_npcs`). But the opening skipped its extraction whenever an NPC was not among the copies, taking it for one the parser had registered, and the parser registers none: every chapter after the narration named a lore figure kept its old place and scene context and registered none of its new people. A successor's opening skipped the same extraction whenever an NPC who stayed had been introduced, which in play is nearly always. Both now extract like a new game's opening, as `docs/ai.md` describes, each shown by a test that failed before the fix. An opening finds a known NPC by name as the lore figures do (`find_npc`, then the fuzzy match, which leaves exact names to it), so the names the copies held are no longer needed; `apply_opening_setup` loses `returning_npcs`, `register_extracted_npcs` its `skip_names` and `reserved_ids`, `next_npc_id` its `reserved`, and the status group `chapter_returning` goes from `gamemaster/enums.yaml`. A chapter whose opening names no place no longer puts the place it opens at into the location history, which holds the places left, as at a succession. The two register tests of `test_setup_common.py` are one test through `apply_opening_setup`. Play changes at these two openings.

Quality gate: 1797 tests, coverage 94.94%. Save format unchanged. An Elvira session would have been needed for the changed openings (`--scenario chapter_end` and `--scenario succession`); none ran, the user's choice (Sessions with the user), so it waits to be caught up.

## [2026.10.20.21] — 2026-10-20

Step 9p, 9p.4, the 16 test files of the AI calls and the prompts. The queries: private names imported on one line, 11 hits (`_process_lore_npcs`, `_check_death_corroboration`, `_build_voicing_user_msg`, `_npc_block`, `_activated_npcs_block`, `_clock_filled_block`); private calls through a module, 2 (`config_loader._parse_config`, `server._dispatch_one_message`); on lines of their own, 0; names in capitals, 65, of which one the engine's (`server._HANDLERS`) and the rest the tests' own fakes; patched private names, 5, of which the retry's sleep and the reset of the prompt store's cache stay as seams; `parse_*_yaml` and `install_config`, 0; a config value set with `setattr`, 1 (`leaked_prompt_tags`); `stub_engine`, `stub_emotions`, and `stub_all`, 29 lines in four files, none needing their values; imports from another test file, 0. Rebuilt on what the game does: lore figures and off-screen deaths go through `apply_narrator_metadata`, filled clocks and activated NPCs through the dialog prompt, the target NPC's escaped memories through `build_dialog_prompt`, and blueprint voicing's request through `call_blueprint_voicing`, read from `OpeningProvider`, which now keeps its calls; the routing provider's configuration and the prompt store load from a temporary file through their own loaders (`config_loader._CONFIG_PATH`, `prompt_loader.PROJECT_ROOT`), where a store was installed by hand; the leaked prompt tags come from the parser's real configuration; a handler's unexpected error goes through the WebSocket endpoint, now in `test_web.py`; and the recap is checked for the story it asks with, where three tests checked only that the mock's answer came back. Joined: `test_schema_in_system.py` into `test_api_client.py`, `test_retry_and_refusal.py` and the stream fallback of `test_sentence_stream.py` into `test_provider_retry.py`, the strictness check of each schema into one over every schema, and in their files the parser's two tag tests, the cases of lore figures and of off-screen deaths, the dropped and the refused stream, and a connection error and a timeout. Removed: a test that an NPC already dead stays dead, which could not fail, the crisis test of the opening prompt, and a patch of the narration stream that no test needed. Found by the audit and fixed: `prompt_boundary.py` → `build_new_game_prompt` rendered a crisis block and guarded the vow for states no opening has, since a new character and a successor both start without crisis and creation refuses an empty vow; the branch, the `block_crisis` prompt, and its placeholder are gone, and every opening renders as before. `test_extract_title.py`, named after a function that no longer exists, is `test_datasworn_titles.py`. Play does not change.

Quality gate: 1796 tests, coverage 94.87%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since every prompt renders as before.

## [2026.10.20.20] — 2026-10-20

Step 9p, 9p.3 closes: every turn the tests play goes through one provider. `TurnProvider` in `tests/_creation.py` answers every role of a turn by its schema, the Director and streaming included, keeps every call in `calls`, and records only the narrator's prompts and narrations; a test that needs another correction sets its `correction`, which `correction_answer` builds as `brain_answer` builds a Brain answer. Eleven providers joined it: the `MockProvider`s of `test_integration.py` and `test_correction_flow.py`, `_ScriptedBrain` and two providers patched by hand for a dialog in `test_integration.py`, `_NarratorCapture` in `test_prompt_xml.py`, `BrainAnswers` and `_BrainSequence`, which played `call_brain` alone, and two providers of `test_succession.py` whose signature no call could reach, now an empty `TurnProvider` whose calls stay empty; `_SmartMockProvider` of `test_game_start.py` is `OpeningProvider`, and its creation data `creation_data`. `BRAIN_FIELDS`, whose empty track name and rank the Brain's schema does not allow, is gone into `brain_answer`. Both `MockProvider`s also answered the schema of a narration validator the engine no longer has. The game `test_integration.py` built, which two other files imported, is `library_game`, whose Mira now carries the description a test of description matching reads, and its forced roll is `fixed_roll`, which `force_result` now uses. Removed: a `__main__` runner with a broad except in `test_integration.py`, and a test that rebuilt the id remap of `game/chapters.py` → `_merge_returning_npcs` in its own code instead of running it (roadmap 9p.6). `test_prompt_xml.py` forces each result instead of seeding `random` until all three came up, and the settlement test of `test_generation.py`, which failed whenever its free focus roll landed on the row that rolls Action and Theme, fixes that die too. Play does not change.

Quality gate: 1811 tests, coverage 94.83%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.19] — 2026-10-20

Step 9p, 9p.3, the 16 test files of the game and the correction, all but the turn providers. The queries: private names imported on one line, 21 hits; on lines of their own, 3, of which 2 the engine's (`_replace_character_identity`, `_reset_for_successor`); private calls through a module, 7, of which 5 forced the prompt store to load (`prompt_loader._ensure_loaded`), which it does by itself; names in capitals, 2 of the engine's (`_OP_HANDLERS`) among the tests' own; patched private names, 1 (`handlers._narration_stream`, not needed); config values set with `setattr`, 2; `stub_engine`, `stub_emotions`, and `stub_all`, 80 lines in nine files, none needing their values; imports from another test file, 1. Rebuilt on what the game does: every chapter test runs `start_new_chapter` on a created game, joined into what a chapter restarts, what it carries over, how its NPCs step back, and a chapter whose blueprint cannot be voiced; the chapter record is read from the campaign history after a chapter; the successor's fresh character, its characters list, and its refused creations go through `prepare_succession` and `start_succession_with_character`, with `OpeningProvider` and `creation_data` in place of a provider and creation of the file's own; the Director's NPC notes reach the dialog prompt and its reflection memories the Director's prompt; the correction ops are held to the ops the analysis is offered through the test that applies each; a menace that fills at scene end has its tick forced through the dice, not the configuration; the information moves are read from the ruleset as it is. The two tests that hand a wrong fact-resolution value to the game master's parser are one, in `test_fact_resolution.py`. Removed: a test of a dataclass's required argument, which the project rules hold, a succession legacy test that asserted nothing, and the chapter tests `test_chapter_summary.py` had twice. Three Director tests that lost their configuration fixture in the change got it back, found by running each touched file alone. One finding, roadmap 9p.6: `game/chapters.py` → `_merge_returning_npcs` has a branch no chapter reaches. Play does not change.

Quality gate: 1810 tests, coverage 94.84%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.18] — 2026-10-20

Step 9p, 9p.2, the 22 test files of the game master and the crafters. The queries: private names imported on one line, 23 hits; on lines of their own, 5; names in capitals, 31, of which 7 are the engine's (`_INPUTS`, `_CONFIG_DIR`, `_META_HANDLERS`) and the rest the tests' own constants and classes; private calls through a module, 4, all a test provider's own `_json`; patched private names, 0; `parse_*_yaml`, 1; `install_config`, 0; config values set with `setattr`, 2; `stub_engine`, `stub_emotions`, and `stub_all`, 75 lines in five files, none of which needed their hand-built values; imports from another test file, 2; and by reading, a hand-built Datasworn setting and two hand-built oracle tables in `test_generation.py` and hand-written Adventure Crafter data. Rebuilt on what the game does: the facts a chapter, a succession, and a location correction clear go through `start_new_chapter`, `prepare_succession` with `start_succession_with_character`, and `apply_correction_ops`; every fact type's odds through `fact_odds`; a keyed scene and a threat's advance through the dialog prompt (`dialog_prompt` in `tests/_helpers.py`, which both files share); a random event's target through `generate_random_event` with the focus die fixed; the fate doublets through `resolve_fate_chart` and `resolve_fate_check` with the dice fixed; an altered scene's adjustments through `check_scene`; what a turn rolls with or plays as dialog, and a hit that heads off a complication, through played turns; a position for every move that rolls, in the four settings, where a test removed a baseline from the configuration; the oracle rolls (an automatic roll replacing its link, roll twice, a role following an earlier one, kept and worsened repeats) on real Datasworn tables with the dice fixed; the Meta plot points through `dispatch_meta`; and the Adventure Crafter's data check through `load_ac_data` on a temporary file. Joined: the two fate-doublet tests with the flag test, the single adjustments with their types, the Meta handler names with the dispatch of every roll, and the turn providers of `test_fact_resolution.py` and `test_correction_replay.py` with `TurnProvider`, which now takes a Brain answer per turn and answers a correction. Removed: two tests that mirrored the Adventure Crafter's yaml, one that loaded its data a second time, one of Python's own argument check, one of a duplicates rule no pinned Datasworn file holds, and two of states `call_brain` already refuses (an unknown move, an action move without a stat). `force_miss` is `force_result`, which forces any result, and the library game four files imported from `test_momentum_burn.py` is `library_game` in `tests/_creation.py`, beside `creation_data`, which a successor's creation now shares with `create_game`. Play does not change.

Quality gate: 1827 tests, coverage 94.93%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.17] — 2026-10-20

Step 9p, 9p.1, the ruleset's 22 test files. The roadmap's queries: private names imported on one line, 21 hits, 20 of them private (one was the public `find_progress_track` under an underscore alias, now plain); private calls through a module, 0; `parse_*_yaml` and `install_config`, 0. Three queries the roadmap's missed, now named in it: private names imported on lines of their own, 2 (`_load_moves`, `_parse_move` in `test_moves.py`); private names in capitals, 2 (`_TABLE_TRIGGERS`, and `packages._SETTINGS_DIR`, which stays as the seam that points the loader at a temporary folder); private names patched by `setattr`, 8. By hand: the handler parameters two files built where the code reads `ruleset/move_outcomes.yaml` (14 calls), one config value overridden (`menace_on_random_event`), and 72 uses of `stub_engine` in four files, which needed none of its hand-built values. Rebuilt on what the game does: what the Brain is offered goes through `call_brain`, a new game's chaos factor through `create_game`, the vow subject through `take_up_character`, the setting yaml's refusals through `load_package` on a temporary folder (moved to `test_ruleset_datasworn.py`), the character state and a threat's advance through the opening and dialog prompts, a rolled stat through `roll_move`, a meter move without a stat through a played turn, the narrator's result names through the rendered system prompt with the ruleset's names swapped, the handlers' outcomes through `resolve_move_outcome`, the moves through `get_moves` (the expansions now by what they add and replace), and Pay the Price through its Datasworn tables with the dice fixed, where a stand-in table stood. Joined: Endure Harm's strong hit, Face Death, Heal's strong hit, a recovery's miss, and a miss at 0 marking the next impact each had two tests; Pay the Price's official table had two; an active vow offering Fulfill Your Vow had two; the chapter's carrying over experience and legacy joined the created game's chapter test. Removed: the cache tests of `get_moves`, the parser tests on hand-written Datasworn (the dedup of a stat two ways share is now held on Heal), a chaos case for an empty vow that creation refuses, and the check that every table rule of `ruleset/suffer.yaml` names a trigger, which read the handler's private table; each of the four triggers is played from its table row by a test of its own in `test_suffer.py`. The Brain answers and the turn provider several files shared by importing them from another test file now live in `tests/_creation.py` (`BRAIN_FIELDS`, `BrainAnswers`, `brain_answer`, `TurnProvider`). Two things the real data showed, which play keeps until roadmap 9j.10: a marked impact reaches the narrator's consequence tags as its key (`mark permanently_harmed`), and classic's Pay the Price, whose rows end in a period, tells a worse result as `revealed., made worse`. Play does not change.

Quality gate: 1826 tests, coverage 94.89%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.16] — 2026-10-20

The render checks of 9o are deleted, at the user's choice, since their work is done and they were built on the code as it stood; the roadmap no longer names them. A later byte-identical check is written anew by the method 9o.2 describes.

Quality gate: 1850 tests, coverage 94.92%, no code changed. Save format unchanged.

## [2026.10.20.15] — 2026-10-20

The roadmap's DONE line for 9o is cut to what a later session needs, and the note on the render checks outside the repository to how they are used.

Quality gate: 1850 tests, coverage 94.92%, no code changed. Save format unchanged.

## [2026.10.20.14] — 2026-10-20

Step 9o, 9o.3, and with it step 9o closes; 9p, the test audit, is NEXT STEP. Two places let text from the player's words reach a prompt unescaped, where SECURITY.md says it is escaped, and both now escape it: an NPC's remembered events in the target NPC's block (`prompt_shared.py` → `_format_memories`), whose words the extraction takes from the narration, and the source and condition of a roll bonus in the Brain's `<bonuses>` block (`ruleset/bonuses.py` → `bonus_block`), whose source is a connection's name. A test for each fails without its fix (`tests/test_prompt_xml.py`), and SECURITY.md names both places. The pattern that strips a host's `<think>` reasoning from an answer is read from `engine/parser.yaml` (`think_open`, `think_block`) instead of being written in `ai/provider_base.py`. The render checks of 9o.2 ran again: 642 of their 3621 renders changed, every one only where its text holds `<`, `>`, or `&`, and none in any other way. A prompt changes only for such text, so play does not change otherwise.

Quality gate: 1850 tests, coverage 94.92%. Save format unchanged. No Elvira session (Sessions with the user).

## [2026.10.20.13] — 2026-10-20

Step 9o, 9o.2, the last group, and with it 9o.2 closes: the markup of the small sites moves to yaml, 11 keys. In `prompts/brain.yaml` the correction analysis's request, its header, NPC line, aliases, and roll summary, and the lines and wrapper of the Brain's roll bonuses (`ruleset/bonuses.py`); in `prompts/blocks.yaml` the correction's context tag (`correction/orchestrator.py`), the task marker the narrator note goes before (`game/turn.py`), and the two forms of a Mythic action and subject, as the name and as the description of a danger or clock a random event starts (`gamemaster/random_events.py`). The correction request's first line, which begins with `##`, is a key of its own, since a yaml line that begins so reads as a comment to the project-rule scan. `ruleset/tracks.py` assembles no markup any more; it builds only ids. The render script of this group rendered the bonus block, the correction's request with and without a roll and NPCs, the correction note, the narrator note, and the dangers and clocks of every focus that starts one, in Delve as well as the three playable settings, and all eight groups' scripts ran again: 3621 renders, byte-identical before and after. A sweep of `src/` for tags in strings finds none left in a prompt; what remains is the HTML of the client's dialog highlight and the `<think>` pattern of `ai/provider_base.py`. The render checks found two places where text reaches a prompt unescaped, the memory events of the target NPC and the Brain's roll bonuses; they and the `<think>` pattern are roadmap 9o.3, now NEXT STEP's substep, since fixing them changes the prompts. The previous entry's key count is corrected to 14. Play does not change.

Quality gate: 1848 tests, coverage 94.88%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.12] — 2026-10-20

Step 9o, 9o.2, seventh group: the markup of `ai/blueprint_voicing.py` moves to `prompts/blueprint_voicing.yaml`, 16 keys: the voicing request as a template, its backstory and location lines, an act's line with its turning point and the three words for what a turning point does to its plotline (opens, concludes, advances), the revelation and ending seeds with their wrappers, and the campaign's chapter lines. An act's line is its own function, `_act_line`. The render script of this group rendered the request for 25 Adventure Crafter seeds and a Kishōtenketsu seed in each setting, with and without backstory, location, campaign history, and seeds, with every line that builds the request reached (what it leaves out are the call's failure and retry paths), and it was byte-identical before and after. Play does not change.

Quality gate: 1848 tests, coverage 94.90%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.11] — 2026-10-20

Step 9o, 9o.2, sixth group: the markup of `director.py` moves to `prompts/director.yaml`, 12 keys: the Director's prompt as a template, its arc notes and tool results, the `<reflect>` tag with its instinct, last reflection, tone, and profile attributes, and its story arc with the scene range, the past-range marker, and the transition trigger. An NPC's memory form, its arc attribute, and the thematic thread attribute are the keys the narrator's blocks already use. The render script of this group rendered the Director's system prompt, its reflection blocks, its story arc at several scenes with and without a thematic thread and a transition trigger, and both of its calls with and without the tool's results, with every line that builds a prompt reached (what it leaves out are the trigger rules and how guidance is applied), and the five earlier groups' scripts ran again: all byte-identical before and after. The previous entry's key count is corrected to 17. Play does not change.

Quality gate: 1848 tests, coverage 94.89%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.10] — 2026-10-20

Step 9o, 9o.2, fifth group: the markup of `ai/narrator.py` and `ai/recap.py` moves to `prompts/narrator.yaml`, 21 keys: the recap's request as a template, its NPC, story-arc, and campaign forms, and the separator between recent scenes; the metadata extraction's NPC reference with its aliases, status markers, place, and description, and its engine context with the move, stat, target, and consequences. A session-log entry, which the epilogue and the recap write alike, is one key, `block_session_log_entry`, where the epilogue had its own. The render script of this group rendered the recap's and the extraction's prompts with and without NPCs of every status, a blueprint, campaign history, and consequences, with every line that builds a prompt reached (what it leaves out are the calls' failure paths and the narrator call, which assembles no markup), and the four earlier groups' scripts ran again: all byte-identical before and after. The previous entry's key count is corrected to 20. Play does not change.

Quality gate: 1848 tests, coverage 94.90%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.9] — 2026-10-20

Step 9o, 9o.2, fourth group: the markup of `ai/brain.py` moves to `prompts/brain.yaml`, 20 keys: the Brain's user message as a template, the wrappers and lines of its moves, tracks, dangers, fact types, and NPCs, the form of a stat and of a stat's value, a way to roll with its condition, the trigger hint, the combat position, an NPC's bond and aliases, and the revelation check's prompt. The render script of this group rendered the Brain's system prompt, its cached prefix, and its user message with and without NPCs, tracks, dangers, a combat position, and a time of day, and the revelation check's prompt, in Delve as well as the three playable settings, with every line that builds a prompt reached (what it leaves out are the refusals and checks of the Brain's answer), and the three earlier groups' scripts ran again: all byte-identical before and after. Play does not change.

Quality gate: 1848 tests, coverage 94.89%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.8] — 2026-10-20

Step 9o, 9o.2, third group: the markup of `prompt_boundary.py` and `prompt_blocks.py` moves to `prompts/blocks.yaml`. The opening, epilogue, and chapter-opening scenes are three templates; the world and character tags, which every prompt opens with, the tags of pronouns, paths, and vow, the epilogue's NPC tag, ending form, and session-log entry, and the chapter's returning NPC tag and background NPCs (whose `name(disposition)` form is the known NPCs' own) are keys of their own. The story arc's act position is part of its template, and the prefix of the background NPCs is part of theirs, so `block_background_npcs_prefix` goes; the aliases attribute the target NPC and a returning NPC share is `block_npc_aliases_attr`. The render script of this group rendered 612 blocks and opening, epilogue, and chapter prompts, in Delve as well as the three playable settings, with every line and branch of both modules reached, and the first two groups' scripts ran again: all byte-identical before and after. Play does not change.

Quality gate: 1848 tests, coverage 94.92%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.7] — 2026-10-20

Step 9o, 9o.2, second group: the markup of `prompt_action.py` and `prompt_dialog.py` moves to `prompts/blocks.yaml`, 12 keys: the action and dialog scenes as two templates, the result tag with its match and consequences attributes, the position tag, and the tags of the player's words, a world addition, a consequence, and the oracle's answer. The three tags both prompts wrote out alike are one helper each in `prompt_shared.py` (`_player_words_tag`, `_world_add_tag`, `_consequence_tags`). The render script of this group rendered 90 action, dialog, and oracle prompts with every line and branch of both modules reached, and the first group's script ran again: both byte-identical before and after. Play does not change.

Quality gate: 1848 tests, coverage 94.90%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.6] — 2026-10-20

Step 9o, 9o.2, first group: the prompt markup that `prompt_shared.py` assembled in Python moves to `prompts/blocks.yaml`, 41 keys: the tags of time, earlier places, the active thread, known NPCs, lore figures, pacing, an altered or interrupt scene, random events, NPC agency, flags, threat events, filled clocks, and the Director's guidance and NPC notes; the target NPC's tag in its two forms with its attributes and its `agenda:`, `instinct:`, and `secrets(...)` labels; the activated NPC's tag with its attributes; and the memory labels `recent:` and `insight:` with the `event(weight)` form an NPC's memories share. What stays in Python is the joining of parts and the escaping. A placeholder is not named `name`, which `get_prompt` takes as the prompt's own name. A render script outside the repository (Sessions with the user) rendered every block of the module, on created games in classic, Starforged, and Sundered Isles with every line and branch of the module reached, and the action, dialog, oracle, and opening prompts that use them: 2466 renders, byte-identical before and after. Play does not change.

Quality gate: 1848 tests, coverage 94.91%. Save format unchanged. No Elvira session (Sessions with the user); the prompts are byte-identical.

## [2026.10.20.5] — 2026-10-20

Step 9o, 9o.1 closes: the project-rule scan that held only the config binding to no dataclass defaults now holds every dataclass in `src/` (`tests/test_project_rules.py` → `_check_no_dataclass_defaults`). An empty collection may stay a default, as CONTRIBUTING.md allows, except on a field the config binding fills from yaml, where it would fill a missing key; the binding's private raw store keeps its empty dict. The external structures are its carve-out, by class (`_EXTERNAL_STRUCTURE_DATACLASSES`: `AICallSpec` and `AIResponse` in `ai/provider_base.py`, the two partial classes in `setting/packages.py`), and a stale entry there, or a config binding file that is gone, fails the stale-entry scan. CONTRIBUTING.md and AUDIT.md (pass 2d and Status) say so, and the roadmap moves 9o.1 to DONE; 9o.2, the prompt markup, is left. Play does not change.

Quality gate: 1848 tests, coverage 94.92%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.4] — 2026-10-20

Step 9o, 9o.1, the last two modules, each with one default: the Adventure Crafter's `ThemeAlternation` in `crafters/adventure_crafter.py` is made with its first choice named, four before five, where a turning point and the tests left it to the default, and `OracleRow.oracle_rolls` in `setting/loader.py`, a Datasworn field some rows lack, keeps its type that allows none but loses the default its one maker in the engine never used, since the parser always passes what the row holds. The 20 defaults left are the external structures of `ai/provider_base.py` and `setting/packages.py`. Play does not change.

Quality gate: 1848 tests, coverage 94.95%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.3] — 2026-10-20

Step 9o, 9o.1, eighth module: `ruleset/move_effects.py` loses the three defaults of `MoveEffect`, the parsed form of an effect in `ruleset/move_outcomes.yaml`. Each branch of `parse_effect` names the value and the target its effect has, zero or empty where it has none, and so does the story complication a miss with a match swaps in for Pay the Price (`ruleset/move_outcome.py`). 22 defaults remain, 20 of them external structures. Play does not change.

Quality gate: 1848 tests, coverage 94.94%. Save format unchanged, since an effect is not saved. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.2] — 2026-10-20

Step 9o, 9o.1, seventh module: `gamemaster/npc/matching.py` loses the three defaults of the best match its fuzzy name matching keeps. The search starts with no NPC, no score, and no kind of match, and every way of matching now names its own kind: a match by shared words, which took the starting `identity`, sets it itself, so a match never reports a kind left over from the start, and the kind is none exactly when there is no match. Two tests pin a match by a shared word as the same figure and no match as having no kind. 25 defaults remain, 20 of them external structures. Play does not change.

Quality gate: 1848 tests, coverage 94.91%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.1] — 2026-10-20

Step 9o, 9o.1, sixth module: `web/session.py` loses the six defaults of `Session`, the server's one player session. It is made in one place, `new_session`, which names its starting state (no player, no game, the default save name, nothing processing, no connection, no burn offered); the server and the tests make theirs with it, and `Session` is keyword-only, so its fields keep their order. 28 defaults remain, 20 of them external structures. Play does not change.

Quality gate: 1846 tests, coverage 94.94%. Save format unchanged, since a session is not saved. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.20.0] — 2026-10-20

Step 9o, 9o.1, fifth module: `ruleset/outcome_result.py` loses the nine defaults of `OutcomeResult`, the record a move's effects and handlers fill. Every outcome starts empty, so its five makers (the effects, the suffer, threshold, and recovery handlers, and a dialog turn's engine moves) share `new_outcome`, which names each field; `OutcomeResult` is keyword-only, so its fields keep their order. The tests build theirs through `make_outcome`, which starts from `new_outcome`. 34 defaults remain, 20 of them external structures. Play does not change.

Quality gate: 1846 tests, coverage 94.93%. Save format unchanged, since an outcome is not saved. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.19.49] — 2026-10-19

Step 9o, 9o.1, fourth module: `models_story.py` loses its 37 defaults, so every maker of a thread, an entry on the characters list, a plotline, a session-log entry, the current act, a blueprint, the Director's guidance, a keyed scene, the narrative, and the campaign names each field. The makers that wrote the same thing in several places now share one: a vow's thread comes from `ruleset/tracks.py` → `_vow_thread` for a sworn vow and the background vow alike, an entry on Mythic's characters list from `gamemaster/random_events.py` → `add_character` for the vow's subject, the opening's NPCs, and a new NPC, empty Director guidance from `director.py` → `new_guidance` for a new game, a chapter, and a succession, and an opening's narration and session-log entry from `game/setup_common.py` → `record_opening` for all three openings. A turn builds its session-log entry as a `SceneLogEntry` and hands `finalize_scene` its pacing type beside it, where it passed a dict with a private key and the entry's consequences and result a second time; `finalize_scene` no longer returns whether a revelation was confirmed, which no caller read. A turn without a roll and an opening log no position or effect, where they logged the defaults risky and standard, which only the correction of an action turn reads; a new game is made at scene 1, and the position resolver no longer skips a log entry without a result, since every entry has one. `SceneLogEntry`, `StoryBlueprint`, `DirectorGuidance`, `NarrativeState`, and `CampaignState` are keyword-only, so their fields keep their order. The test helpers gain makers for the narrative, threads, entries on the characters list, and keyed scenes, and `make_scene_log_entry` now has callers. 43 defaults remain, 20 of them external structures. Play does not change.

Quality gate: 1846 tests, coverage 94.94%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.19.48] — 2026-10-19

Step 9o, 9o.1, third module: `models_npc.py` loses its thirteen defaults. A new NPC is made in one place, `gamemaster/npc/lifecycle.py` → `new_npc`, which sets its starting state (no arc or memories yet, its counters at 0, no reflection due) and takes what differs between its makers by name: the opening's NPCs, a mid-game NPC, the stub of a rejected reveal, a lore figure, and an NPC a correction splits off, where each of the five wrote its own. A memory names who it is about at every maker. `NpcData` is keyword-only, so its fields keep their order. 80 defaults remain. Play does not change.

Quality gate: 1846 tests, coverage 94.96%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.19.47] — 2026-10-19

Step 9o, 9o.1, second module: `models.py` loses its 34 defaults and `PlayerPreferences` its two. `BrainResult`, `TurnSnapshot`, and `GameState` are keyword-only, so their fields keep their order and the save format holds. A Brain answer was already read strictly, every field required, so only the tests' brain results needed the fields they left out, which `make_brain_result` now fills. A turn's snapshot names at its one maker (`GameState.snapshot`) that the turn's input, Brain answer, roll, narration, and scene are still to come. A new game names every field too: it is made without a character, with an empty name, concept, stats, and wishes, and takes one up through `take_up_character` as a successor does, which now gives the preferences whole. 93 defaults remain. Play does not change.

Quality gate: 1846 tests, coverage 94.97%. Save format unchanged. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.19.46] — 2026-10-19

Step 9o, 9o.1, first module: the dataclasses of `models_base.py` lose their seventeen defaults, so every maker of a clock, the world, a progress track, a threat, a random event, or a scene setup names each field, and one that forgets fails at once. The makers that wrote a fresh one in several places now share one: a clock comes from `gamemaster/clocks.py` → `new_clock`, which the spawners, the opening clock, the complication clocks, and the ruleset's dying clock use, with the owner, an empty fill, and no firing set there; a legacy track comes from `ruleset/progress.py` → `new_track` like every other track, where `ruleset/legacy.py` wrote it out. `PlayerPreferences` keeps its two defaults until `models.py`, since its only maker is `GameState`'s default. The test helpers fill the fields the models no longer default, and `make_scene_setup` replaces the bare scene setups in the tests. 129 defaults remain. Play does not change.

Quality gate: 1846 tests, coverage 94.91%. Save format unchanged: every field was saved already. No Elvira session (Sessions with the user); none would have been needed, since play does not change.

## [2026.10.19.45] — 2026-10-19

Step 9q: Elvira's scenarios reach what they prepare, where they set meters and stats and hoped. A missed aim is now a problem in her report. A scenario can fix the results of its first turns (`results` in `tests/elvira/elvira_config.yaml`): while such a turn plays, Elvira replaces the scoring of `ruleset/rolls.py` with one that draws the dice among those giving the named result, so every action and progress roll of the turn comes out so, follow-up and chained moves included, without a match unless only a match gives it, and a result no dice give stops the run with the reason (`tests/elvira/elvira_bot/fixed_results.py`); the engine keeps no switch for it. A scenario that dice cannot bring to its moment starts at it: the new `succession` scenario begins at the first character's game over, so the successor's creation and opening play. `near_death`, `miss`, `momentum_burn`, and `clock` fix misses and `complication` weak hits; `near_death` no longer aims at game over and succession, which the rolls on Endure Harm's own table leave to chance and the new scenario reaches, and no scenario sets every stat to 1 any more, so that preparation is gone. Scenarios play in direct mode only, which the command line now says by refusing `--ws` with `--scenario`, where it played direct without a word. The roadmap records the user's choice: no Elvira run on the real models while the API credit is tight, with each release saying what it would have run; 9o is NEXT STEP.

Quality gate: 1846 tests, coverage 94.90%. Save format unchanged. No Elvira session on the real models, the user's choice; the suite plays the `miss` and `succession` scenarios to their aims on the mock provider. To catch up later: one run of each scenario.

## [2026.10.19.44] — 2026-10-19

Step 9n, 9n.5, and with it 9n closes: the queries of principles 2 and 3 on the code the split into layers wrote or rewrote. Which code that is came from git rather than from the roadmap's list, which the 9n.4 sessions had not kept up: every line `git blame -w -M -C -C` gives to a commit after 9n.1a, which only moved the code, and not to 9n.3, whose code had its queries, in 99 files. Principle 2: 2a, readable strings, 68 hits, six of them prompt markup in `ai/brain.py`, `prompt_action.py`, and `prompt_boundary.py`, which belongs to the groups of roadmap 9o.2, the rest log lines and developer errors; 2b, numbers other than 0 and 1, no hit; 2c, 18 collection literals with string keys (schema structure, the config binding, the literal prompt keys the orphan scan reads) and 38 comparisons with a string, one of them a violation: the game master asked whether a move's kind was `gather_information`, a category of the ruleset, where its own question `gathers_information` answers it, so a ruleset's information moves now settle a place on a miss whatever their category; 2d, one dataclass default, `BrainResult.target_threat`, whose class is roadmap 9o.1. Principle 3: 3a, no except handler; 3b, 46 None checks, fallbacks, and isinstance calls, each on a value whose type allows it or a lazy cache; 3c, 87 functions used at most once whose definition is new or which lost a caller, one violation, `count_emergent_threats`, whose second caller had gone, so `add_threat` counts itself; 3d, 27 bodies that return one call, none without logic; 3e, nine parameters with a default, each set both ways in production except `present_npc_ids` of `retrieve_memories`, kept for step 11c, and found by reading, the meter effect in `ruleset/move_effects.py` took a target it never used. Met on the way and fixed: the opening clock was still made in `game/game_start.py`, which the roadmap's account of 9n.4 contradicted, and is now `gamemaster/clocks.py` → `start_opening_clock`; it and the complication clocks take their owner from `default_owner_kind` like the other clocks, where they wrote it out; and the Brain's check for a missing track name asks whether the move starts a track instead of fetching what it starts. The dying clock stays the ruleset's own timer in `ruleset/suffer.py`, which `docs/mechanics.md` now says. AUDIT.md's Status names the new packages, 9n moves to DONE, and 9q, Elvira's scenarios reaching their aims, is NEXT STEP with its substeps. Play does not change.

Quality gate: 1830 tests, coverage 94.92%. Save format unchanged. No Elvira session: in every shipped ruleset the information moves are the moves of the `gather_information` category, and the rest moves code without changing play.

## [2026.10.19.43] — 2026-10-19

Step 9n, 9n.4 closes: the principle-1 audit of `ruleset/`, all three steps, and with it principle 1 is done (AUDIT.md, Status). Step 1a flagged no file over 400 lines; the largest are `ruleset/move_effects.py` (372) and `ruleset/tracks.py` (264). Step 1b judged the files with a reason for suspicion legitimate: `ruleset/move_effects.py` keeps Pay the Price and the rolls on a move's tables beside the effects, since each applies further effects and a module of their own would import in a circle with it, and `ruleset/outcome_result.py` keeps `move_outcome_config` apart from `ruleset/move_outcome.py` for the same reason; `ruleset/tracks.py`, `ruleset/make_move.py`, and `ruleset/move_handlers.py` hold one concern each. Step 1c found momentum, experience, impacts, and the rolls on a move's tables spread only as layers of their concern. No code changed.

Quality gate: 1829 tests, coverage 94.92%. Save format unchanged. No Elvira session: no code changed.

## [2026.10.19.42] — 2026-10-19

Step 9n, 9n.4: the principle-1 audit of `gamemaster/` with `gamemaster/npc/`, all three steps. Step 1a flagged one file over 400 lines, `gamemaster/config_types.py` (472 lines), which holds one concern, the layer's config types, as the split of `config.py` beside it intends. Step 1b found four files holding a concern that has its own yaml and none of its own module: `gamemaster/world.py` held the chaos factor, the pacing hint, and the choice of story structure beside location and time, which are now `gamemaster/chaos.py`, `gamemaster/pacing.py`, and `gamemaster/story.py` beside `chaos.yaml`, `pacing.yaml`, and `story.yaml`; `gamemaster/engine_memories.py` held the scene context, now `gamemaster/scene_context.py` beside `scene_context.yaml`; and `gamemaster/npc/lifecycle.py` held description matching, now `gamemaster/npc/description_match.py` beside `description_dedup.yaml`. `gamemaster/resolvers.py` held the time a move takes beside position and effect, and that joined the rest of time in `gamemaster/world.py`. Two inline imports that broke a cycle are plain imports now, since the cycles are gone, and their whitelist entries with them. Kept, with a reason: the Mythic lists stay in `gamemaster/random_events.py`, whose yaml holds their settings and whose events draw their targets from them, and clearing a place's facts stays in `gamemaster/world.py`, since a move clears them and `gamemaster/facts.py` reads where a fact belongs from it. Step 1c: the facts, keyed scenes, and NPC naming are layers of their concern. Play does not change.

Quality gate: 1829 tests, coverage 94.92%. Save format unchanged. No Elvira session, the user's choice: the change moves code without changing play.

## [2026.10.19.41] — 2026-10-19

Two things 9n.4 found that pointed at nothing, fixed at the user's request. First, no threat had a vow in play: threats start only from a random event or a plot point, and nothing linked a vow to one, so a miss never advanced a threat's menace, a full menace track never made the player forsake a vow, and fulfilling a vow never overcame its threat; only the tests built a linked threat. Delve says what links them: once a threat is introduced, the player swears an iron vow to see its goal undone. The Brain now sees the active threats in `<dangers>`, each with its menace and the vow sworn against it, and when the move swears a vow against one of those without a vow it names it in `target_threat`, which its schema offers from those alone; `ruleset/tracks.py` → `start_track` links the new vow to the threat, and the three rules work from there (`ruleset/threats.py` → `vow_against`, which replaces two copies of the same search). Second, `clear_cache` in `ruleset/moves.py` and in `setting/packages.py` had no caller but tests, an orphan-symbol carve-out each; they are gone, and the two test files that need an empty cache patch the module's own. The Brain's system prompt gains the line for `target_threat` and its `target_clock` line names complications as the lines of `<dangers>` without an id.

Quality gate: 1829 tests, coverage 94.89%. Save format breaks: a save keeps its last turn's Brain answer, which now carries `target_threat`, so a save from before does not load. Elvira, Starforged, aggressor, 8 turns, about $0.52: the Brain answered with the new field on every turn without a refusal, two threats started from plot points and advanced, no vow was sworn against them in the run, which the suite plays; one problem, a miss the judge found too mild (4 of 10), the known weakness of misses, which this change does not touch.

## [2026.10.19.40] — 2026-10-19

Step 9n, 9n.4: the principle-1 audit of `setting/` and `crafters/`, all three steps. Step 1a flagged one file over 400 lines in the two layers, `crafters/adventure_crafter.py` (713 lines, 25 public symbols); step 1b found it held five concerns that split without coupling, so it is five modules: `crafters/adventure_crafter.py` keeps the data, the table lookups, and the turning points; `crafters/meta_plot_points.py` holds the Meta handlers with the two character-list helpers only they use; `crafters/character_traits.py` the character tables; `crafters/turning_point_spawns.py` the keyed scenes, dangers, and clocks a turning point adds; and `crafters/blueprint.py` the blueprint seeds and their materialisation. The Adventure Crafter's data loader is public, since two modules read it, and the error of a Meta drift names the module it lives in, where it named one that was gone. In `setting/` every file holds one concern (step 1b); step 1c found one concern with two homes, the two paths that follow a link from one oracle row to another table, which roadmap step 10.2 already settles. Play does not change.

Quality gate: 1827 tests, coverage 94.90%. Save format unchanged. No Elvira session, the user's choice: the change moves code without changing play.

## [2026.10.19.39] — 2026-10-19

Step 9n, 9n.4: threats, tracks, and NPC naming looked at for one concern spread over several files. Tracks and NPC naming are layers of their concern (a track's arithmetic, its lifecycle, a connection's bond, the legacy tracks; an NPC's oracle name, matching, rename, and the extraction's updates), each in its own module. Threats had two loose ends: `ruleset/progress.py` built a threat for its only caller in `ruleset/threats.py`, which now builds it itself, and wrote a menace track's arithmetic out again beside a progress track's, which the two now share. Found and recorded for step 9j.6, and in `docs/mechanics.md`: no threat links to a vow in play, only in tests, since threats start only from a random event or a plot point, so a miss never advances a vow's threat, a full menace track never forsakes a vow, and a fulfilled vow never resolves its threat; how Delve ties a threat to a vow is read before that is wired. Play does not change.

Quality gate: 1827 tests, coverage 94.86%. Save format unchanged. No Elvira session, the user's choice: the change moves code without changing play.

## [2026.10.19.38] — 2026-10-19

Step 9n, 9n.4: the clock code lives in one module. It lived in seven places: naming and counting in `gamemaster/clocks.py`, ticking in `gamemaster/clock_ticks.py`, a fill's consequence in `gamemaster/clock_consequences.py`, complication clocks in `gamemaster/complications.py`, a clock's keyed scenes in `gamemaster/keyed_scenes.py`, and the two spawners in `gamemaster/random_events.py` and `crafters/adventure_crafter.py`, which each checked for a clock from the same source, checked the chapter's cap, named it, built it, and gave it its keyed scenes. Now `gamemaster/clocks.py` holds all of it, and the three files that held only clock code are gone. The spawners call `spawn_emergent_clock` with the name, type, and source they own; the three ticks (a miss, an NPC's agency, the autonomous tick at scene end) share one step that fills a clock and fires it (`_advance_clock`), where each wrote it out. Play does not change.

Quality gate: 1827 tests, coverage 94.84%. Save format unchanged. No Elvira session, the user's choice: the change moves code without changing play, and the suite covers every spawner and tick.

## [2026.10.19.37] — 2026-10-19

Step 9n, 9n.4, first part: the duplicates 9h found are gone. Six functions numbered ids the same way, three for keyed scenes, two for the Adventure Crafter's characters and plotlines, and one for threats, and NPC numbers were counted in three places (`gamemaster/npc/matching.py` and twice in `game/setup_common.py`); they now share `ids.py` → `next_id`, which takes the number after the highest and never reuses one, so a keyed scene's id is `ks_` and its number whatever its source. Every source adds a keyed scene through `gamemaster/keyed_scenes.py` → `add_keyed_scene`, which validates it, numbers it, and puts it on the list, and asks `has_keyed_scene_from` whether it already added one, where three sources each wrote both. The Mythic lists' weight and consolidation, written out once for threads and once for characters, are one each (`gamemaster/random_events.py` → `consolidate_lists`), and an NPC's rename, written out in the identity merge and in the surname update, is `gamemaster/npc/lifecycle.py` → `rename_npc`. Code outside `game`, `tools`, and `correction` imports them through their `__init__.py`, which the one outlier (`correction/orchestrator.py`) did not, and a new project-rule scan holds it. Met on the way and fixed: `gamemaster/random_events.py` and `gamemaster/scene.py` imported the private Mythic loader of `gamemaster/fate.py`, which is now `gamemaster/mythic_data.py` → `load_mythic`, and four NPC modules imported the game state only for type checking with quoted annotations, where a plain import serves. The roadmap records two choices of the user: no closing Elvira run over every setting for 9n, and Elvira runs kept to what a change needs. What remains of 9n.4 is gathering the clock code and the principle-1 audit per layer.

Quality gate: 1827 tests, coverage 94.85%. Save format unchanged; a new keyed scene's id is `ks_` and a number, and older ids stay as they are. No Elvira session, the user's choice: the change moves code without changing play, and the suite covers every spawner.

## [2026.10.19.36] — 2026-10-19

Step 9n, 9n.3b: a setting names its ruleset, and the Datasworn files split into the two layers. Datasworn already says it: a file of `type: ruleset` is its own ruleset and an expansion names the one it extends, so the settings yaml gains no key; a setting plays the ruleset its file names, and a chain whose files name two rulesets stops loading (`setting/packages.py` → `SettingPackage.ruleset_id`). `setting/loader.py` reads a Datasworn file once (`read_datasworn`), and the setting keeps only its world, oracles and truths, while `ruleset/datasworn.py` → `load_ruleset` reads the rules, moves, and assets of the ruleset's own file and the expansions of the setting's chain. Stats, meters, impacts, legacy tracks, moves, and assets now come from there instead of from the setting chain, so a setting whose chain holds no ruleset file still plays its ruleset's moves, and classic's outcomes are the classic ruleset's, found by its id rather than along the setting chain. A new character's paths and starting assets still come from the setting's own file. `docs/settings.md` describes the rulesets and adding a setting and adding a ruleset apart. The principle-2 and principle-3 queries ran on the code 9n.3 wrote or rewrote (`ruleset/datasworn.py`, `setting/loader.py`, the ruleset check and `table_by_id` in `setting/packages.py`, `ruleset/moves.py` → `move_table`, `ruleset/legacy.py` → `mark_legacy_ticks`, `ruleset/assets.py`, `ruleset/character.py`): no broad except, no dataclass default, no new numeric threshold or mapping, and each of the 30 None checks is on a value whose type allows None. The property `SettingPackage.parent`, which no code read after the split, is gone, and a missing Datasworn file names `data/data.py`, where it named a script that no longer exists. Every text pattern the ruleset's yaml matches against a Datasworn row (Pay the Price, Endure Harm and Endure Stress, Take Decisive Action, Reveal a Danger) was checked against the 0.1.0 tables, and all sixteen still match.

Quality gate: 1824 tests, coverage 94.79%. Save format unchanged. Elvira, classic, aggressor, 8 turns, about $0.59: no problems, overall 6.8 out of 10, with misses, weak hits, a strong hit, four new NPCs, a filled clock, two Pay the Price rolls, Endure Stress as a follow-up move by classic's own outcome, a correction, an AI failure rolled back, and a save and load.

## [2026.10.19.35] — 2026-10-19

Step 9n, 9n.3a: every Datasworn file at 0.1.0, the user's choice. The engine read 0.0.10 for classic, Starforged, and Delve, and 0.1.0 for Sundered Isles, the only form of it, which linked into Starforged by ids the Starforged file did not carry. Datasworn last changed in November 2024 and 0.1.0 never left prerelease; all four files now come from the last commit of its `v0.1.0` branch, pinned in `data/data.py`, which no longer reads npm. Moves, rules, assets, and truths keep their ids, roll types, ways to roll, and outcomes. A move carries its own tables, so the list form of move tables, the 0.0.10 link forms, and the old table lookup are gone; Story Clue and Story Complication are among the moves' suggestions, which a move now offers where the setting chain holds them (`ruleset/moves.py` → `move_table`, `offers_table`). Starforged's renamed oracle collections are in its settings yaml, and classic names an NPC by one of its two hundred Ironlander names, where the engine read the book's two lists as given and family name. Two rules the engine decided itself are now read from Datasworn: a momentum burn is offered where the move allows it (`allow_momentum_burn`, every action roll, so play does not change), and a legacy track earns experience only where its rules tag it (`experience_tag` in `ruleset/legacy.yaml`; Starforged's three earn it, classic's bonds, which nothing marks yet, do not). A row of a shared table without a roll range is left out, where the parser gave it the range 0 to 0 and took the die from the last row, so a furnace planet's atmosphere, whose last row has no range, would have raised; the die stays the table's highest row, since Sundered Isles' highlands landmarks hold fifty rows of the d100 they name. The stray `data/.gitignore.txt`, which named the old version, is gone.

Quality gate: 1818 tests, coverage 94.77%. Save format unchanged. Elvira, Starforged, aggressor, scenario `complication`, 8 turns, about $0.58: no problems, overall 6.0 out of 10, with misses, weak hits, a strong hit, a fight, a complication clock, two Pay the Price rolls, two roll bonuses, a fact settled by fate, a correction, an AI failure rolled back, and a save and load; no place was generated, which the test suite rolls for every setting.

## [2026.10.19.34] — 2026-10-19

Roadmap, the user's choices: step 9q makes Elvira's scenarios reach what they prepare, by fixing the dice of their next turns or starting at the moment itself; it comes first after 9n. An overview of scores across runs is not built, and without one a floor on the judge's scores is left out too, since one short run scores too few turns per criterion to set it. Step 9p audits the tests after 9o: a test that holds what the game does stays, one that holds how it is built is rebuilt or goes, double tests are joined, and the coverage floor is read again. No code changed.

Quality gate: 1810 tests, coverage 94.78%. Save format unchanged.

## [2026.10.19.33] — 2026-10-19

Step 9n, 9n.2j: the two findings 9n.2 kept, at the user's request, and 9n.2 closes. The threat statuses outside the ruleset go: `ruleset/threats.py` says which threats are active and which overcome, and gives the events of overcome threats whose menace stays high (`overcome_under_pressure`, from `game/action_resolution.py`), which the chapter record, the action phase, and `/threats` now ask for. The narrator's rules named the ruleset's results (MISS, WEAK_HIT, STRONG_HIT) in `prompts/narrator.yaml` and `prompts/tasks.yaml`; they now take them from the ruleset by outcome (`ruleset/answers.py` → `results_by_outcome`, filled in by `prompt_blocks.py`), so another ruleset's names would stand in their place. The narrator's system prompt, its cached prefix, and the action task were rendered on created games in classic, Starforged, and Sundered Isles before and after and are byte-identical, and so is the Brain's prompt. 9n.2 moves to DONE, AUDIT.md's open items name the roadmap steps they now sit in, and 9n.5 lists the code 9n.2 wrote or rewrote, which its audit takes up.

Quality gate: 1810 tests, coverage 94.78%. Save format unchanged. No Elvira session: the prompts are byte-identical and the threat code moved unchanged.

## [2026.10.19.32] — 2026-10-19

Step 9n, 9n.2i: the character a player creates is the ruleset's, the user's choice, and with it the last part of 9n.2. The assets and their rules already came from Datasworn and lived in the ruleset; what remained was character creation, where the game package checked the paths and starting assets, named the concept from the paths, and swore the background vow, twice over: in a new game and for a successor (the finding of 9n.4). `ruleset/character.py` → `make_character` now checks and builds what the ruleset decides of a character, its stats, paths and the concept they name, starting assets, and background vow with its rank, and `give_character` gives it to the game; `game/game_start.py` → `take_up_character` takes it up with the name, pronouns, backstory, truths, and wishes, alike for a new game and a successor, and `validate_creation` keeps only what is no rule of the ruleset (the name, the truths, the tone). One check closed a gap: a setting whose creation offers no starting-asset category (Delve) let any starting asset through, and now refuses one; the form offers none there, so play does not change. 9n.2 keeps two findings, the result names in the narrator's prompts and the threat statuses outside the ruleset.

Quality gate: 1808 tests, coverage 94.77%. Save format unchanged. Elvira, Starforged, aggressor, scenario `near_death`, 8 turns, about $0.62: no problems, overall 7.2 out of 10, with a new character created, misses, weak and strong hits, a fight, five Pay the Price rolls, a momentum burn offered and taken, a correction, an AI failure rolled back, and a save and load; game over and succession were not reached, which the test suite plays through the real creation.

## [2026.10.19.31] — 2026-10-19

Step 9n, 9n.2h: the impacts are the ruleset's. They already came from the Datasworn rules with their labels, permanence, and the meters each keeps from recovering, and no code outside the ruleset names one. What the inventory found is a copy: `blocking_impact` in `ruleset/move_outcomes.yaml` named for eleven recovery and suffer moves the impact that blocks their meter, which the Datasworn rules already say (`prevents_recovery`). The suffer handler never read it, and the recovery handler now asks the rules (`ruleset/impacts.py` → `blocks_recovery`), so the key is gone; Heal still clears wounded, Hearten shaken, and Resupply unprepared. Withstand Damage's entry named battered, which its Datasworn rules let block nothing, and no turn reaches that move yet (step 19). What a move marks (`impact_pair`, `impact`) and the impact supply at 0 marks (`exhausted_impacts`) stay in the ruleset's yaml, since Datasworn says them only in the move texts.

Quality gate: 1802 tests, coverage 94.72%. Save format unchanged. No Elvira session: the recovery handler finds the same impact it was named before, and no prompt or turn changed; the session of the next release plays it.

## [2026.10.19.30] — 2026-10-19

Step 9n, 9n.2g: dialog and asking the oracle are the game master's own moves, the user's choice. They sat in `ruleset/engine_moves.yaml` beside world shaping, and the ruleset's yaml gave dialog its time and both their category, while the game master and the game package named their ids. They are now `gamemaster/moves.yaml`, each with the time it takes, and `gamemaster/moves.py` says whether a turn plays as dialog, whether it asks the oracle, and rolls the oracle's answer (`roll_oracle_answer`, from `ruleset/tracks.py`). World shaping, an action roll with the ruleset's stats, stays in `ruleset/engine_moves.yaml`. The move filter now offers only the Datasworn moves a situation allows, and the Brain offers those, the game master's moves, and world shaping in the same order as before (`ai/brain.py` → `_offered_moves`); a game master's move shows the Brain no roll by `ai_text.no_roll_type`. The Brain's system prompt, cached prefix, message, and schema are byte-identical before and after, and every move takes the time it took.

Quality gate: 1800 tests, coverage 94.72%. Save format unchanged. Elvira, classic, dialogist, 8 turns, about $0.63: no problems, overall 7.0 out of 10, with a dialog turn, weak and strong hits, a fight, a new place generated, a momentum burn offered and taken, a follow-up move, two facts settled by fate, a correction, an AI failure rolled back, and a save and load; the oracle was not asked, which the test suite plays.

## [2026.10.19.29] — 2026-10-19

Step 9n, 9n.2f: making a move is the ruleset's. The game package rolled the move itself, a progress roll on its track or an action roll with its stat, bonus, adds, and momentum (`game/turn.py`), and resolved its outcome with chained moves and boasts (`game/finalization.py`), naming Datasworn's roll types as it went. Both now live in `ruleset/make_move.py`: `roll_move` rolls the move and `resolve_move` resolves its outcome, while the game package keeps the turn's snapshot and the clock a miss ticks. A move says itself whether it is an action or a progress roll (`Move.is_action_roll`, `is_progress_roll`, and `EngineMove.is_action_roll`), so the Brain and the game package name no roll type. The information gate counted Gather Information by its move id in Python; the game master now asks whether an action gathers information, and the ruleset answers from `information_moves` in `ruleset/answers.yaml`, with the same move as before. Classic's own outcomes need the ruleset a setting names, so they move to 9n.3, and the user chose that dialog and asking the oracle become the game master's moves while world shaping stays with the ruleset (9n.2g). The Brain's system prompt, cached prefix, message, and schema are byte-identical before and after.

Quality gate: 1797 tests, coverage 94.72%. Save format unchanged. Elvira, Sundered Isles, aggressor, 8 turns, about $0.59: no engine warnings, overall 6.3 out of 10, with misses, weak hits, a strong hit, a fight, a complication clock, a roll bonus, two facts settled by fate, a correction, an AI failure rolled back, and a save and load; one problem, a miss on Compel the judge found too mild (4 of 10), the known weakness of misses, which this change does not touch.

## [2026.10.19.28] — 2026-10-19

Step 9n, 9n.2e: the tracks and ranks are the ruleset's. The ranks were already its yaml, Datasworn naming none, but code outside the ruleset named its track types, track statuses, and rank tables in about twenty places, and some of its track rules lived in the game package. Now the game package, the server, and the Brain ask the ruleset, the user's choice, as 9n.2b did for results. `ruleset/tracks.py` swears the background vow (`swear_background_vow`, from `game/game_start.py`, without the second check of a rank that creation already validates), ends a progress roll (`resolve_progress_roll`, from `game/action_resolution.py`), marks progress and legacy by rank (`apply_progress_and_legacy`, from `game/finalization.py`), and answers which tracks are active, which vows the chapter record lists, and whether a thread follows a vow. `ruleset/bond.py` says whether a connection is bonded and whether a move starts one. `ruleset/succession.py` decides which threads a successor keeps and picks the connections out of every track itself. `ruleset/progress.py` → `ranks` gives the ranks in order, which creation's vow ranks, rank shifts, and the Brain's schema read instead of the keys of two different tables, and a test holds every table keyed by rank to that order. The move filter moved from `tools/builtins.py` to `ruleset/move_availability.py`, beside its yaml. `/tracks` picks each line by the track's type from `strings/status.yaml`, with the same text as before. The Brain's system prompt, cached prefix, message, and schema are byte-identical before and after. Found and recorded: the chained moves still resolve in `game/finalization.py`, threat statuses are still named outside the ruleset (both 9n.2), and every thread on Mythic's list is a vow today (step 31).

Quality gate: 1794 tests, coverage 94.70%. Save format unchanged. Elvira, Starforged, aggressor, scenario `combat`, 8 turns, about $0.54: no problems, overall 6.8 out of 10, with two misses, four weak hits, a fight whose track filled through five marks, five Pay the Price rolls, a correction, an AI failure rolled back, and a save and load; no progress roll ended the fight, which the test suite plays.

## [2026.10.19.27] — 2026-10-19

Step 9n, 9n.2d: the stats are the ruleset's. `ruleset/stats.yaml` named the five stats beside Datasworn's `rules.stats`, with `none` among them for the Brain's answer, and held a total, a range, and a list of arrays beside the one array the rules give. Now a character's stats are the names and descriptions of the Datasworn rules along the setting chain (`ruleset/stats.py` → `stat_descriptions`; Delve takes classic's, Sundered Isles Starforged's), and `ruleset/stats.yaml` keeps only what Datasworn lacks: the array a new character arranges (`creation_array`) and the abbreviations of the Brain's state line. `validate_stats` moved to `ruleset/stats.py` and checks by setting that the character takes exactly the ruleset's stats, where it ignored one it did not know, with the array in any order. The creation form gets each setting's stats and derives its total and range from the array, so its minimum is 1, as the rules have it, not 0, and a value already entered stays when the player switches setting. The Brain's word for a move without a stat is `ai_text.no_stat` in `engine/ai_text.yaml` instead of a stat name filtered out again and literals in `ai/brain.py`, `ai/narrator.py`, and `game/turn.py`, and its schema takes the setting's stats. The Brain's system prompt, cached prefix, message, and schema on created games in classic, Starforged, and Sundered Isles are byte-identical before and after. DONE in the roadmap is cut to what a later session needs.

Quality gate: 1792 tests, coverage 94.66%. Save format unchanged. Elvira, classic, explorer, 8 turns, about $0.56: no problems, overall 6.7 out of 10, with two misses, two weak hits, a complication clock, two Pay the Price rolls, a follow-up move, a correction, an AI failure rolled back, and a save and load.

## [2026.10.19.26] — 2026-10-19

Step 9n, 9n.2c: the legacy tracks are the ruleset's. The campaign held Starforged's three legacy tracks as fixed fields in every setting, classic included, where nothing used them. Now it keeps by name the special tracks its ruleset's Datasworn rules name and do not call optional (`CampaignState.legacy`, built by `ruleset/legacy.py` → `new_campaign`), the user's choice: classic its bonds track, which 9j.2 will let Forge a Bond mark, Starforged and Sundered Isles quests, bonds, and discoveries, and Delve no failure track until 13b marks it. A predecessor's record keeps its boxes by track name, Continue a Legacy rolls each track the campaign holds, the player's status lists them, and strict loading now builds a dict of dataclasses back into dataclasses (`serialization.py`). The tests of succession play Starforged, whose rule Continue a Legacy is. Starforged's status line reads as before.

Quality gate: 1786 tests, coverage 94.66%. The save format breaks: a save from before cannot be loaded. Elvira, Starforged, aggressor, scenario `near_death`, 8 turns, about $0.58: no problems, overall 6.5 out of 10, with three misses, two impacts marked, two follow-up moves, and a save and load; game over and succession were not reached, which the test suite plays.

## [2026.10.19.25] — 2026-10-19

At the user's request, from the Elvira run of 2026.10.19.24: an NPC stayed in every scene once she had been in one. In that run Saffi walked into a store and shut the door in the first turn, and the narration rightly left her out after; the engine still gave her a memory of each investigation she could not have seen, for scenes 3 to 6, and the judge, which saw every active NPC as present, marked a turn that left her out at 4 of 10. The cause was a loop: an NPC counted as in the scene when the activation found her relevant, every such NPC got the turn's memory and was named in the scene context, and the next turn's activation read her name in that context and her fresh memory, so she was relevant again. Now activation decides only whom the narrator's prompt holds; an NPC counts as in the scene, for its memory of the turn, the scene context, the Mythic characters list, and a reported death, when the prompt held it and it is the action's target or the narration names it (`gamemaster/npc/matching.py` → `present_in_narration`). A test plays two turns whose narration leaves out an NPC the scene context named, which before the fix remembered both. Elvira's judge now sees the NPCs the engine counts as in the scene, not every active NPC. A passing mention of someone absent still counts as presence, which step 11b.1, where the extraction reports who leaves, takes up.

Quality gate: 1784 tests, coverage 94.71%. Save format unchanged. Elvira, Starforged, dialogist, 8 turns, about $0.53: no problems, overall 7.0 out of 10, and the one NPC the narration named in every scene remembers every scene, while the lore figures it only spoke of remember none.

## [2026.10.19.24] — 2026-10-19

Step 9n, 9n.2b: the result tiers are the ruleset's. Which result a roll gives is `results_by_dice_beaten` in `ruleset/dice.yaml`, the result for each number of challenge dice the score beats, and `ruleset/rolls.py` scores action and progress rolls, a momentum burn, and a downgrade in a bad spot from it instead of from written-out results; the hits are that list without its lowest, a move's Datasworn outcome texts are read by the keys Datasworn gives, and Continue a Legacy's fractions are keyed by result (`fraction_by_result` in `ruleset/succession.yaml`). Code outside the ruleset decides on a roll only by its outcome in the game master's words: the game package (a miss ticks a threat clock and advances menace, a weak hit may tick a clock, a hit completes a track, heads off a complication, and counts toward the information gate, `gamemaster/questions.py` → `gained`), the narrator's `<result>` block, whose text the outcome chooses (`result_success_body` and the rest in `prompts/blocks.yaml`), the narrative direction (`by_outcome` in `engine/narrative_direction.yaml`), the Director's call on a miss, and the successor's inheritance as the player sees it (`succession.legacy_success` and the rest in `strings/succession.yaml`). The result blocks for every result with and without a match, the narrative direction, and the succession summary were rendered before and after and are byte-identical. An error message that named `engine/succession.yaml` names the file that holds the rule. Found and left for the rest of 9n.2: the information gate counts Gather Information by its move id in `game/action_resolution.py`, and the narrator's prompts name the results.

Quality gate: 1782 tests, coverage 94.66%. Save format unchanged. Elvira, classic, dialogist, scenario `miss`, 8 turns, about $0.57: no engine warnings and no state violations, overall 5.7 out of 10, with three misses, three weak hits, two clocks filled, a complication clock, three Pay the Price rolls, a burn offered, a correction, and an AI failure rolled back; one problem, an NPC who drops out of a scene's narration (4 of 10), which this change does not touch.

## [2026.10.19.23] — 2026-10-19

Step 9n, 9n.2a: the meters are the ruleset's. `Resources` holds no meter as a field of its own any more but the meters by name (`Resources.meters`): the condition meters come from the Datasworn rules along the setting chain (`rules.condition_meters`, range and starting value; Sundered Isles takes Starforged's, Delve classic's), momentum from `ruleset/momentum.yaml`, and their arithmetic, which `Resources` held as methods, is `ruleset/meters.py` (`lose`, `gain`, `adjust_momentum`, `reset_momentum`, `in_crisis`). `ruleset/resources.yaml` is now `ruleset/meters.yaml` and keeps only what Datasworn lacks: the heavy-loss amount and the meters whose 0 brings a crisis. Max momentum is derived from the impacts instead of stored beside them, and that brought a rule fault to light: a momentum gain stopped at 10, not at the max the impacts lower, so a wounded character could hold more momentum than the rules allow; it now stops at the lowered max. The code that named health, spirit, and supply reads the ruleset's meters instead (suffer and recovery handlers, move effects, consequence sentences, strain, roll sources), and what the narrator and the player are told of a meter is keyed by its name in `engine/`: the narrator's descriptions with the flag for a meter at 0, which moved there from `prompts/blocks.yaml`, the player's status descriptions under `status_descriptions.meters`, and the meters that set narrative intensity. The narrator's character state, its flags, its narrative direction, and the player's status were rendered before and after for five sets of meters and are byte-identical. ARCHITECTURE.md (stats and meters keyed by name), README.md (the layers in one paragraph), and docs/mechanics.md (Meters) follow.

Quality gate: 1782 tests, coverage 94.71%. The save format breaks: a save from before cannot be loaded. Elvira, Sundered Isles, aggressor, 8 turns, about $0.59: no engine warnings and no state violations, overall 6.5 out of 10, with a correction, an AI failure rolled back, Pay the Price, and a save and load; one problem, a miss the judge found too mild (4 of 10), the known weakness of misses, which this change does not touch.

## [2026.10.19.22] — 2026-10-19

Step 9n, 9n.1d, at the user's choice: each layer reads its yaml through its own accessor, so reading against the direction is importing against it. `gm()` (`gamemaster/config.py`, its dataclasses in `gamemaster/config_types.py`), `crafter()` (`crafters/config.py`), and `rules()` (`ruleset/config.py`, `ruleset/config_types.py`) each load their own folder, and `eng()` loads only `engine/`; the strict binding they share is `config_binding.py`. Every configuration read moved to the accessor of the folder its yaml lives in, about 385 in the source and 140 in the tests, and the scan of configuration reads that 9n.1c added is gone again: the import scan now covers what it guarded, including a read handed along as a value, which that scan could not follow. The models in the base no longer read a layer's rules. A track's and a threat's arithmetic is `ruleset/progress.py`, the starting meters `ruleset/meters.py`, the chaos factor's start and step `gamemaster/world.py`, the legacy tracks `ruleset/legacy.py` → `new_campaign`, and a keyed scene is validated where a source makes it (`gamemaster/keyed_scenes.py` → `new_keyed_scene`); a new game's resources, world, and campaign come from these, no longer from defaults that read the configuration.

Quality gate: 1771 tests, coverage 94.67%. Save format unchanged. No Elvira session: no rule, value, prompt, or turn changed; the four loaders were run against the real yaml.

## [2026.10.19.21] — 2026-10-19

Step 9n, 9n.1c: two project-rule scans hold the layers to their direction, and 9n.1 is done. The import scan now refuses the game master an import of the crafters or the ruleset, and the crafters one of the ruleset (`_check_import_layers`). A new scan reads every configuration read in the four layers' code, `eng().section` and `get_raw("section")` through any name bound to `eng()`, and refuses a section whose yaml lives in a layer above the reader (`_check_layer_config_reads`): a layer reads its own folder, the layers below it, and `engine/`, the engine's own text and infrastructure. Today's code passes both; an import of the ruleset placed in the game master and a read of a ruleset section placed in the game master and in the crafters were each refused, then removed. The whole engine still reads one merged `eng()`, which the scan makes safe to keep.

Quality gate: 1771 tests, coverage 94.70%. Save format unchanged. No Elvira session: no code that runs in play changed.

## [2026.10.19.20] — 2026-10-19

Step 9n, 9n.1b: the game master is untangled from the ruleset. Nothing under `gamemaster/` or `crafters/` imports the ruleset or names its moves, results, meters, or threats any more: the game master asks the questions of `gamemaster/questions.py` → `RulesetAnswers` in its own words, `ruleset/answers.py` answers them from `ruleset/answers.yaml`, and the game package installs the answers when it loads (`docs/mechanics.md`, Game master and ruleset). How an action went is success, partial, or failure, and the game master's yaml is keyed by those words (the chaos factor's steps, the memories' texts and emotions, position's streaks); an NPC's closeness is a number from 0 to 10, a connection's filled boxes, kept a number because the keyed scenes' thresholds run from 3 to 7; strain is a level per meter. The rules the game master held are the ruleset's now: which move gains an advantage, Strike's effect, the time a move takes and its phrase in a memory, merging two NPCs' connections, a filled progress clock completing its track, and spawning threats, which random events and the Adventure Crafter ask for as a new danger (`threats.by_origin` holds rank and category, `threats.max_per_chapter` the cap; a random event's threat id begins `threat_random_event_`). Narrative direction, which only prompt assembly reads, moved to `engine/`. The scene context names the outcome and the action's phrase instead of the roll result and the move id, so it carries no system terms. The orphan scan counts a protocol's methods as used.

Quality gate: 1771 tests, coverage 94.69%. Save format unchanged. Elvira, Sundered Isles, explorer, 8 turns, about $0.52: no engine warnings, overall 6.7 out of 10, with misses, weak hits, a complication clock, a new place, a correction, and an AI failure rolled back; one problem, a miss the judge found too mild (audit 4 of 10), the known weakness of misses, which this change does not touch.

## [2026.10.19.19] — 2026-10-19

Step 9n, 9n.1a: the code and its yaml move into the four layers without a change in behaviour; the user's decisions on the direction of imports, the questions the game master keeps, and threats in the ruleset are in the roadmap (Decisions, Four layers). `setting/` holds the Datasworn loader, the setting packages (`datasworn/settings.py` is now `setting/packages.py`), and the oracle rolls and cascades; `gamemaster/` Mythic, keyed scenes, clocks, facts, generation, position and effect, pacing, stance and gating, the engine's memories, and the NPC layer in `gamemaster/npc/`; `crafters/` the Adventure Crafter; `ruleset/` the Ironsworn rules with the Datasworn moves and impacts, a connection's bond, and threats. `mechanics/consequences.py` splits along the layers into `ruleset/rolls.py`, `gamemaster/clock_ticks.py`, and the narrator's sentences in `ruleset/consequences.py`, and the two impact files are one, `ruleset/impacts.py`. The hubs `mechanics/__init__.py` and `npc/__init__.py` are gone: the layers' packages are markers and every caller imports from the module, so each import names its layer. The yaml follows into `gamemaster/`, `crafters/`, and `ruleset/` beside `engine/`, which keeps what is no rule (the AI's text, the parser, retry, persistence), and `eng()` merges the four folders; `engine/dice.yaml` splits into each layer's own (`dice`, `mythic_dice`, `adventure_crafter_dice`). The import-layer scan knows the new packages, the orphan-key scan reads every config folder, ruff now sorts imports (rule I), and the coverage floor rises to 94.

Quality gate: 1752 tests, coverage 94.65%. Save format unchanged. No Elvira session: no rule, value, prompt, or turn changed, only where they live, and the Elvira smoke test plays the moved pipeline on the mock provider.

## [2026.10.19.18] — 2026-10-19

At the user's request, ahead of 9n: the refusal Elvira found in 2026.10.19.14 (a strong hit on Compel that the narrator told as a refusal, audit 4 of 10). The engine log showed the cause: the hostile target got the stance matrix's `hostile` stance, "Refuses to engage. Threats or silence.", although the roll had decided they give in; the misses already override the stance (`miss_stance`), the hits did not. Now a hit grants as a miss withholds: a target whose matrix stance would refuse or deceive (`information_gate.refusing_stances`: hostile, stonewalling, confrontational, misleading, all a hostile NPC's on social and information moves) takes `information_gate.hit_stance`, yielding (`mechanics/stance_gate.py` → `resolve_npc_stance`, which takes `hit` beside `miss`); bystanders and dialog keep the matrix's stance. Checked on the narrator directly with the scene rebuilt: three narrations of a strong hit on Compel against a hostile prisoner all gave in, sullenly, two telling both things asked and one telling one, as its fact budget of one allows.

Quality gate: 1752 tests, coverage 94.68%. Elvira, Starforged, dialogist, 8 turns, about $0.48: no problems, overall 7.2 out of 10, though no hit on a hostile target came up; the three direct narrations cost a few cents.

## [2026.10.19.17] — 2026-10-19

Step 9h, 9h.29 settled by measurement, and step 9h closes. Thirty player inputs in Starforged, each with the move or moves the rules allow (the risky, the investigating, and the preparing moves, Compel, dialog, the oracle, world shaping, the recover, quest, connection, combat, and exploration moves), went to the Brain once with its hand-written hints and once with the book's trigger, the bold opening of each Datasworn move's text, for every Datasworn move on offer; the engine's own moves kept their hints in both. The hints chose right 30 times of 30, the triggers 29 (they took "I find a sniper's perch overlooking the landing pad" for world shaping), at 174 thousand against 181 thousand input tokens; 60 Brain calls, about $0.82. The hints stay, and `Move.text`, which only a test read, leaves `datasworn/moves.py`; the two tests that read it now check that Sundered Isles' Undertake an Expedition replaces Starforged's. Step 9h moves to DONE with its last two findings, 9h.13 and 9h.14, in 9n.4, and 9n becomes NEXT STEP with its definition of done and reference patterns.

Quality gate: 1743 tests, coverage 94.66%. Save format unchanged. No Elvira session: no prompt or turn changed.

## [2026.10.19.16] — 2026-10-19

Step 9h, 9h.16 fixed. Consequences are structured: every effect, handler, boast, chained move, and recommit records a `Consequence` (`models_base.py`: a kind, the key of its label in `ai_text.consequence_labels`, and the values the label is filled with) instead of a finished string, and `mechanics/consequences.py` picks the narrator's sentence by kind and values (`_sentence_event`) instead of parsing the label back (`_classify` is gone). The parser had told "legacy reward (bonds)" as a bond growing with someone called "legacy reward (", any follow-up move or oracle row containing "bond" as a bond, and split labels at their commas; a disposition shift (Make a Connection, Test Your Relationship) now has a sentence of its own (`disposition_shift` in `engine/consequence_templates.yaml`), and `bond_loss`, which nothing could produce, is gone. The momentum label takes a signed number (`momentum {n:+d}`), plain texts such as a boast or a death are the `told` kind, and the scene log keeps the structured consequences so a correction retells them the same way. Save format breaks.

Quality gate: 1742 tests, coverage 94.65%. Elvira, Starforged, aggressor, 8 turns, about $0.59: no problems, overall 6.7 out of 10, with a momentum burn, a correction, and two Pay the Price rows.

## [2026.10.19.15] — 2026-10-19

Step 9h, 9h.28 fixed. A correction of the state narrates the turn again with what the turn told the narrator: `TurnSnapshot` keeps the turn's random events, threat events, filled clocks, and NPC agency (`game/turn.py` → `_keep_what_the_turn_told`, called where the action and dialog prompts are built, so a momentum burn and a replayed turn keep theirs too), and `correction/orchestrator.py` → `_rewrite_prompt` hands them on instead of empty lists. The check surfaced a second fault: the rewrite called `check_npc_agency` again, which advanced every NPC scheme clock a second time on a turn where agency fell due; it now reads the agency the turn told. Save format breaks: the snapshot gained four fields.

Quality gate: 1740 tests, coverage 94.62%; both new correction tests fail without the fix. Elvira, classic, 8 turns, one state correction, about $0.53: no problems, overall 7.2 out of 10.

## [2026.10.19.14] — 2026-10-19

Step 9h, 9h.18 fixed. A move whose outcomes act on an NPC (a bond, a connection's rank, a disposition; `NPC_EFFECTS` in `mechanics/move_effects.py`) is refused by `call_brain` when it names no target NPC (`ai/brain.py` → `_check_target_npc`, `mechanics/move_outcome.py` → `acts_on_an_npc`, read from the move's outcomes), as Make a Connection already was; this catches Test Your Relationship, which had no such check. The effects themselves now raise without a target, and the bond and rank effects without a connection, instead of quietly doing nothing, since both are refused before them. Classic's Forge a Bond lost its `bond +1` on a hit, which could never act because classic has no connection tracks; 9j.2 says so.

Quality gate: 1738 tests, coverage 94.65%. Elvira, Starforged, dialogist, 8 turns, about $0.57: one problem, a narration that let a strong hit on Compel end in a refusal (audit 4 of 10), which this change does not touch; no move was refused for a missing target, overall 6.7 out of 10.

## [2026.10.19.13] — 2026-10-19

Step 9h, 9h.25 fixed, checked against Starforged's move texts in Datasworn. A connection Forge a Bond's hit seals now stays as a bonded connection (status `bonded`, `tracks_bonded_on_a_hit` in `engine/track_moves.yaml`) instead of completing and dropping out: it keeps its progress, so the NPC's bond no longer falls to nothing, it still aids, now with +2 (`bonded_add` in `engine/roll_bonuses.yaml`, the book's Bolster their influence, a fixed choice recorded in `docs/divergences.md`), Make a Connection does not make it a second time, `/tracks` names it, and the Brain sees which NPCs share a bond. The check surfaced a second fault: Develop Your Relationship always rolled the bonded version, so a connection without a bond never gained progress and Forge a Bond could never succeed. Develop now follows its two branches. With a bond it rolls +rank as before, offered only while a bonded connection exists (the new availability condition `bonded_track`) and refused for an NPC without one. Without a bond it marks progress per rank without a roll (`without_bond` in `engine/move_outcomes.yaml`), which the engine does when a hit on Test Your Relationship makes it as a follow-up (`game/finalization.py` → `_chain_without_bond`); the player's own Develop without a bond waits for the moves without a roll in 13b, recorded as a divergence. Save format breaks: a track status gained a value.

Quality gate: 1726 tests, coverage 94.53%. Elvira, Starforged, dialogist, 10 turns, about $0.68: no problems, overall 6.6 out of 10; she made no connection in this run, so the connection path rests on the new integration test that plays Make a Connection, Test Your Relationship, and Develop Your Relationship through the real turn.

## [2026.10.19.12] — 2026-10-19

Step 9h, 9h.17 fixed. `/advance` no longer spends experience for nothing: `mechanics/legacy.py` → `advance_asset` refuses an asset the setting lacks, a new asset the character already holds, an upgrade of an asset not held or with every ability enabled, and an advance the experience does not cover, and returns the reason, which `web/handlers.py` → `handle_advance_asset` tells the player from `strings/advance.yaml` (four new strings; `advance.insufficient` now names the asset). Before, an unknown id joined the character's assets, and an upgrade of an asset not held, unknown, or full cost experience and changed nothing. A held asset is matched however its id is written (`empath` or `path/empath`), and an upgrade lands on the id the character holds it under, which is the id the roll bonuses read. `advance_cost` gives the cost by kind and raises on an unknown kind; `mechanics/assets.py` → `enable_next_ability` no longer returns quietly when every ability is enabled, since that is refused before it.

Quality gate: 1719 tests, coverage 94.42%. Save format unchanged. No Elvira session: Elvira does not use `/advance`.

## [2026.10.19.11] — 2026-10-19

Step 9h, 9h.5 settled. Every `.get()`, `.setdefault()`, and `.pop()` in `src/` whose default is computed rather than a constant, found by walking the syntax tree: 2 hits, 0 violations. Both are documented environment overrides in `config_loader.py`, `STRAIGHTJACKET_CONFIG` and `STRAIGHTJACKET_USERS_DIR`, whose default is the project's own config file or users folder; the case in `web/serializers.py` that the substep named went in the principle-5 audit of `web/`. No code changed.

Quality gate: 1713 tests, coverage 94.26%. Save format unchanged. No Elvira session.

## [2026.10.19.10] — 2026-10-19

Step 9h: the principle-5 audit of the top level, which closes principle 5. Queries (hits/violations): public symbols 3/1, return values 2/0, `strings/` keys built from a prefix against their domain values 9 families/0 (9h.6 settled). The package's `__version__` re-export, which nothing read, leaves `src/straightjacket/__init__.py`, now a package marker.

Quality gate: 1713 tests, coverage 94.26%. Save format unchanged. No Elvira session: nothing in play changed.

## [2026.10.19.9] — 2026-10-19

Step 9h, 9h.30 and 9h.31 at the user's word. `strings/consequence.yaml`, `strings/effect.yaml`, and `strings/position.yaml`, labels nothing showed, are deleted with the user's consent. The creation form takes its pronoun options from `creation.pronoun_options` in `engine/creation.yaml` through the creation defaults, since the chosen value also reaches the narrator's prompt, and its empty choice from `ui.no_choice`, which the starting-asset choice shares; Elvira rolls from the same list, and also takes the stat names and the number of paths from the config instead of her own copies.

Quality gate: 1713 tests, coverage 94.26%, the page's script checked with `node --check`. Save format unchanged. No Elvira session: nothing in the engine's play changed.

## [2026.10.19.8] — 2026-10-19

Step 9h: the principle-5 audit of `web/`, the page included. Queries (hits/violations): public symbols 36/1, session fields 7/0, fields of the messages the server sends against what the page reads 79/17, server values the page copies 4/4, keys of `strings/` 179/23. The unused `/health` route goes. Eleven message fields nothing read go (a truth's quest starter, the setting's creation flags, the stat arrays, and the predecessor's name, concept, end reason, and track ids in the succession summary); six gain a reader: the save list names the character and the chapter beside the scene, a new chapter and a succession open with a chapter heading, and the form offers as many paths and starting assets as the config allows. The page no longer copies the stat names, the autosave's name, or the creation defaults: the server sends the stat names (`StatsConfig.character_names`, which also replaces three copies of that filter in `game/`) and the default save's name, and the page labels stats with `strings/stat.yaml` and the burn offer with the result labels instead of raw codes. An epilogue reloaded from a save is shown as an epilogue. Dead strings leave (`succession.preparing`, the results' severities); three dead strings files wait for the user's consent (9h.30).

Quality gate: 1713 tests, coverage 94.28%, the page's script checked with `node --check`. Save format unchanged. No Elvira session: nothing in the engine's play changed.

## [2026.10.19.7] — 2026-10-19

Step 9h: the principle-5 audit of the files directly under `engine/`. Queries (hits/violations): public symbols without an outside reader 12/0, re-exports of `models.py` 40/0 (seven no production file imports, kept since ARCHITECTURE.md names the hub for every dataclass), dataclass fields read by attribute name 876/24, returns no production caller reads 6/4. Twenty-three fields that play wrote and nothing read leave the state: dice numbers kept only for the log (a random event's focus roll and table, the scene test's roll), copies (a fact's odds, a threat event's ticks, a fate result's odds, question, chaos factor, method, roll, and event, a filled clock's track flag, an inheritance roll's predecessor boxes and fraction, a chapter summary's place and scene count, the epilogue's text and shown flag), an NPC's unused keywords and a character entry's turning-point count, and the session log's activation scores, Director trigger, and revelation check, which only Elvira or nothing read; the Director's trigger is now a log line. `resolve_fate` takes the chaos factor from the game. The fields' producers lose what only fed them (`activate_npcs_for_prompt`'s scores, `roll_event_focus`'s roll), and `save_game`, `delete_save`, `create_user`, and `delete_user` no longer return what no caller read. One field gains a reader: a state correction retold the clock ticks of scene end as if the turn had caused them, and now leaves out the events marked `autonomous`.

Quality gate: 1713 tests, coverage 94.27%. Save format breaks (the fields above). Elvira about $0.55, no problems.

## [2026.10.19.6] — 2026-10-19

Step 9h: the principle-5 audit of `correction/`. Queries (hits/violations): public symbols 3/0, re-exports 1/0, public names imported past the hub 0/0, dataclass fields 0/0, return values 9/2, parameters that copy another 2/2, fields of the analysis's answer 19/0, config read 23/0, prompt keys 3/0, strings 1/0. `process_correction` returned the game it was handed, as did `process_turn`, `process_momentum_burn`, `generate_epilogue`, `start_new_chapter`, and `start_succession_with_character`; they now return what they make, and the web handlers and Elvira hold the game themselves. `apply_post_narration` reads the present NPCs' names and the Brain's world addition itself instead of taking copies, so a state correction now extracts with the turn's world addition, which it dropped. The correction's prompt rewrite no longer hands back the turn's consequences.

Quality gate: 1715 tests, coverage 94.30%. Save format unchanged. Elvira about $0.52, no problems.

## [2026.10.19.5] — 2026-10-19

Step 9h: the principle-5 audit of `tools/`. Queries (hits/violations): public symbols 7/0, re-exports 2/0, public names imported past the hub 1/1, dataclass fields 0/0, fields of the offered moves 4/4, fields of the tool's answer 24/0 with 3 for the user, config read (availability rules 54, roll types, engine-move fields 3, tool descriptions 1, prompt keys 1) 60/0, readers that add the engine moves again 2/2. `available_moves` returns the moves themselves by id instead of dicts copying their name, stats, and roll type, of which a Datasworn move's stats only a test read; the hub re-exports it, and the Brain's schema and its check no longer add the engine moves a second time. The thread id and the clock owner in the Director's tool answer wait under 11.0.

Quality gate: 1714 tests, coverage 94.27%. Save format unchanged. No Elvira session: the Brain's prompt and schema are byte-identical before and after, checked in twelve states over the four settings.

## [2026.10.19.4] — 2026-10-19

Documentation only, at the user's request: the md files shortened, since a session reads them all. The roadmap goes from about 61,000 to 47,000 characters: later steps are sketches that keep their decisions and the facts found, and point to CONTRIBUTING.md, AUDIT.md, `docs/`, the data, and the CHANGELOG instead of repeating them, with a rule that keeps it short; an independent check against the old text found nothing important lost, and its few gaps were put back. The CHANGELOG goes from about 126,000 to 66,000 characters: the 48 entries over 700 characters keep their core, the user's choices, the audits' queries and counts, and the quality gate, and their full text stays in git history. Corrected on the way: `docs/settings.md` on how a setting's moves merge along its parent chain, ORIGINS.md's credits for the Location Crafter, roadmap step 25's claim that Set a Course is played as dialog, and AUDIT.md's list of open items.

Quality gate: 1713 tests, coverage 94.27%, no code changed. Save format unchanged.

## [2026.10.19.3] — 2026-10-19

Step 10, ahead of its turn: the Location Crafter (Tana Pigeon, Word Mill Games), which the user bought, transcribed while the book is at hand into `data/location_crafter.json` (new): the Special Elements table, the scene roll and its progress points, the element kinds, uniques, known elements, growing lists, mapping, the book's texts for the narrator, and its three example regions. Its Complex Question tables are not copied, since `mythic_gme_2e.json` holds their successors. README's License names the file (CC BY-NC 4.0). Nothing reads it before step 10, where the user chose that the Crafter runs only in places without a ruleset procedure and that the engine builds its lists without an AI call. The roadmap also records when a Word Mill book or Mythic Magazine issue is bought.

Quality gate: 1713 tests, coverage 94.27%, no code changed. Save format unchanged. No Elvira session.

## [2026.10.19.2] — 2026-10-19

Step 9h: the rest of what the earlier audits removed and the rules or the story know, now with a reader. Impacts come from the setting's own Datasworn rules through the chain (`datasworn/impacts.py` → `get_impacts`); `engine/impacts.yaml`, a hand copy, is deleted with the user's consent, and the narrator receives each marked impact with the book's description (`prompt_shared.py` → `_impacts_block`). A turning point keeps its plotline and whether it opens, advances, or concludes it, which the blueprint voicing now sees. Every threat advance reaches the narrator as `<threat_advance>`, an autonomous tick in the next turn as off screen (`mechanics/threats.py` → `take_pending_threat_events`), and in Delve with a roll on its category's table. Fixed on the way: threats named "Roll twice" (`datasworn/cascade.py` now rolls the rows) and a Delve threat's category taken from the plot point's guess.

Quality gate: 1713 tests, coverage 94.27%. Save format breaks (`WorldState.pending_threat_events`, `ThreatEvent.development`). Elvira about $0.60.

## [2026.10.19.1] — 2026-10-19

Step 9h: the earlier audits' removals read again by the rule that a field without a reader is first a missing reader. A move carries its Datasworn tables (`datasworn/moves.py` → `Move.tables`), and the engine rolls those instead of yaml paths: Sundered Isles' Make a Discovery and Confront Chaos no longer roll Starforged's tables, Pay the Price and the Endure tables come from their moves, Take Decisive Action's weak hit rolls its own table, a hit on Gather Information rolls Story Clue (`mechanics/move_effects.py` → `roll_move_table`), and Delve's Escape the Depths miss reveals a danger. Classic's overrides hold in every setting built on its ruleset (`mechanics/outcome_result.py`), so Delve no longer endures as Starforged does. The Brain sees each way to roll in the book's words and can answer `lowest` for Heal (`mechanics/roll_sources.py` → `roll_by_method`); the stat descriptions are the setting's own.

Quality gate: 1703 tests, coverage 94.21%. Save format unchanged. Elvira about $0.75.

## [2026.10.19.0] — 2026-10-19

Step 9h: the principle-5 audit of `datasworn/`, and the rule that a field without a reader is first a missing reader written into the roadmap (Decisions, Bound to the rules). Queries (hits/violations): single-load symbols 33 of 98/0, re-exports 0/0, dataclass fields 63/10, unread returns 0/0, `get_raw` sections 0/0, string subscripts 37/0, Datasworn fields without a reader 6/6. Those now have one: a row's `duplicates` rule (`datasworn/oracle_rolls.py` → `roll_rows`), so "Roll twice" no longer reaches the narrator as a result; table, path, and asset names from Datasworn's `name`; each move's own text for its result as `<move_outcome>` (`datasworn/moves.py` → `outcome_text`); markdown stripped in one place (`plain_text`). Gone: `OracleResult` and fields only tests read or that copied others.

Quality gate: 1681 tests, coverage 94.20%. Save format unchanged. Elvira about $0.74.

## [2026.10.18.21] — 2026-10-18

Step 9h, at the user's word: a field without a reader is first a missing reader (AUDIT.md, principle 5). Before a field, a return value, or an AI answer goes, the session asks whether it carries what the rules or the story know, and if so gives it a reader. Two answers the last release dropped come back with one: the blueprint's antagonist stands in the `<story_arc>` the narrator and the Director see, and the Director's arc notes reach its next call as `<arc_notes>`.

Quality gate: 1679 tests, coverage 94.17%. Save format breaks (the blueprint and the Director guidance regain those fields). Elvira about $0.55.

## [2026.10.18.20] — 2026-10-18

Step 9h: the principle-5 audit of `ai/`. Queries (hits/violations): single-load symbols 50 of 106/0, re-exports 0/0, dataclass fields 20/0, unread returns 2/1, config fields read 146/0, `get_raw` sections 2/0, string subscripts 83/0, prompt keys 110/0, fields of the AI's answers 78/4. The token log leaves production; Elvira counts through a meter around the provider (`tests/elvira/elvira_bot/tokens.py`), so her cost covers every engine call. The AI is no longer asked for four answers nothing read: the Brain's `type`, a rename's `reason`, the blueprint's `antagonist_force`, and the Director's `arc_notes`.

Quality gate: 1677 tests, coverage 94.09%. Save format breaks (`BrainResult`, `StoryBlueprint`, and `DirectorGuidance` each lose a field). Elvira about $0.46.

## [2026.10.18.19] — 2026-10-18

Step 9h: the principle-5 audit of `game/`. Queries (hits/violations): single-load symbols 50 of 79/0, re-exports 12/0, dataclass fields 41/0, unread returns 8/2, config fields read 227/0, `get_raw` sections 2/0, string subscripts 77/0. `prepare_succession` and `register_extracted_npcs` no longer return what no caller used. `determine_end_reason` guessed from the meters why the game ended, so a miss at Face Desolation with health and spirit at 0 archived the character as dead; the move that ends the game now records its reason (`end_reason` in the threshold moves of `engine/move_outcomes.yaml`, `retire` on retiring).

Quality gate: 1677 tests, coverage 94.10%. Save format breaks (`end_reason` replaces `game_over`). Elvira about $0.51.

## [2026.10.18.18] — 2026-10-18

Step 9h: the principle-5 audit of `npc/`. Queries (hits/violations): single-load symbols 43 of 70/0, re-exports 25/8, dataclass fields 3/0, unread returns 1/0, config fields read 73/0, `get_raw` sections 1/0, string subscripts 34/0, emotions sections 2/0. The hub no longer re-exports the eight helpers that only the package's own files use. No Elvira session, since nothing in play changed.

Quality gate: 1677 tests, coverage 94.07%. Save format unchanged.

## [2026.10.18.17] — 2026-10-18

Step 9j.9, at the user's word and with their two choices: the progress moves as their texts have them. Every hit on a progress roll now completes the track (`game/action_resolution.py` → `_apply_track_completion`), where a weak hit left it open. On a miss the fights are lost, while Fulfill Your Vow, Forge a Bond, Finish an Expedition, and Reach Your Destination recommit (the user's choice; `recommit_on_miss`, `mechanics/tracks.py` → `recommit_track`), and the last two no longer pay the price. Forge a Bond's weak hit seals the bond and tells the narrator that they ask something more first (the user's choice). Finish an Expedition's weak hit marks its legacy reward one rank lower, and Take Decisive Action in a bad spot counts one result lower (`mechanics/consequences.py` → `downgrade_in_position`).

Quality gate: 1677 tests, coverage 94.11%. Save format unchanged. Elvira about $0.31.

## [2026.10.18.16] — 2026-10-18

Step 9j.5, pulled forward at the user's request, with their four choices: harm, stress, and death as the rulebooks have them. Every loss of health, spirit, or supply goes through `mechanics/suffer.py` → `suffer`, with momentum costs past 0 and unprepared when supply runs out. Endure Harm and Endure Stress follow as follow-up moves, in classic on every loss and in Starforged and Sundered Isles at 0, mark impacts, and roll their tables; a dying character has a two-turn clock to heal. Face Death and Face Desolation end the game on a miss, and their weak hit binds an extreme vow whose completion clears the burden (`ProgressTrack.bound_impact`). The game no longer ends when health and spirit are both 0. Also fixed: classic Face Death marks cursed, classic Heal and Sojourn follow their texts, and dialog turns resolve these events before the narrator writes.

Quality gate: 1652 tests, coverage 94.01%. Save format breaks (`bound_impact` on a progress track). Elvira about $0.92 for two games.

## [2026.10.18.15] — 2026-10-18

The scene-end half of 9j.6, at the user's request: a menace that filled at scene end forsook its vow unheard, since `game/scene_finalization.py` resolved it after the narration. Scene end now only ticks the threats, the next turn resolves a full track before the narrator writes, and a dialog turn passes its threat events to the narrator and the Director (`prompt_shared.py` → `_threat_events_block`).

Quality gate: 1628 tests, coverage 93.80%. Save format unchanged. Elvira about $0.46.

## [2026.10.18.14] — 2026-10-18

Step 9h: the principle-5 audit of `mechanics/`, settling 9h.8. Queries (hits/violations): single-load symbols 174 of 293/4 dead, re-exports 85/39, dataclass fields 48/10, unread returns 19/14, config fields without a reader 15 of 464/9, `get_raw` sections 15/0. `OutcomeResult` loses fields only tests read, `TurningPoint` and `PlotPointHit` what nothing read, and fourteen functions their unused returns; the hub re-exports only what outside code imports. Config no code read leaves, `engine/bonds.yaml` and `engine/act_progress.yaml` with the user's consent. A random event's menace mark moves to `threats.menace_on_random_event`. Found: no turn ever marked an impact (for 9j.5).

Quality gate: 1627 tests, coverage 93.75%. Save format unchanged. Elvira about $0.41.

## [2026.10.18.13] — 2026-10-18

Step 9h: the principle-3 audit of the top level of `src/straightjacket/`; principle 3 is done. Queries (hits): broad except 0, `is None` 1, fallbacks 1, `isinstance` 2, single-reference functions 5, single-call bodies 5, parameters 0. The strings loader now lives in `i18n.py`, a string missing a placeholder value raises as a prompt does, and prompts and strings share `load_text_dir`.

Quality gate: 1629 tests, coverage 93.79%. Save format unchanged. Elvira about $0.15 through the server.

## [2026.10.18.12] — 2026-10-18

Step 9h: the principle-3 audit of `web/`, with its items of 9h.13, settling 9h.7, and the principle-2 findings of 9h.27. Queries (hits): broad except 17, except handlers 27, `is None` 12, fallbacks 26, falsy returns 15, `isinstance` 9, single-reference functions 42, single-call bodies 2, test parameters 0; about thirty violations. A handler catches only the call that reaches the AI and `_dispatch_one_message` reports any other fault; a new chapter or succession runs on a copy that replaces the game only on success; status labels are read strictly. The parser's prompt-leak patterns, the bond and track scale, and the clock urgency thresholds left Python for yaml. Elvira's WebSocket mode waits for each request's closing message.

Quality gate: 1626 tests, coverage 93.74%. Save format unchanged. Elvira about $0.35 through the server.

## [2026.10.18.11] — 2026-10-18

Step 9h: the principle-3 audit of the files directly under `engine/`, with their items of 9h.13, `director.py` for 9h.7, and 9h.26. Queries (hits): broad except 1, except handlers 5, `is None` 21, fallbacks 16, falsy returns 21, `isinstance` 17, single-reference functions 82, single-call bodies 18, test parameters 20; about sixty violations. Fixed: a correction of the state lost the turn's scene type, position, and effect; the Director catches each of its two calls on its own; a prompt missing a variable raises. Gone: `bootstrap_log.py`, write-only save data, guards against impossible states, and parameters production never set. New items 9h.27 and 9h.28.

Quality gate: 1625 tests, coverage 93.31% (`fail_under` raised to 93). Save format unchanged; a save no longer carries the engine version. Elvira about $0.57.

## [2026.10.18.10] — 2026-10-18

Step 9h.24, as the user agreed: two NPCs found to be one become one without leaving anything behind (`npc/lifecycle.py` → `absorb_npc`, for a correction's merge and a rename's duplicate), handing over the connection, clocks, and list entry. No connection made in play was ever its NPC's, since Make a Connection named its track after the Brain's track name; the track now carries its NPC's id, the Brain must name that NPC, and every move starts its track after the roll, only on a hit where the move says so (`mechanics/tracks.py` → `start_track`). New items 9h.25 and 9j.8.

Quality gate: 1632 tests, coverage 92.92%. Save format unchanged. Elvira about $0.47.

## [2026.10.18.9] — 2026-10-18

Step 9h: the principle-3 audit of `correction/`, with its items of 9h.13. Queries (hits): broad except 1, except handlers 1, `is None` 2, fallbacks 4, falsy returns 3, `isinstance` 0, single-reference functions 13 of 13, single-call bodies 0, test parameters 0; about twenty violations. Fixed: the last turn's snapshot outlived a new chapter or a succession, so a correction could undo the chapter or bring the dead back; marking an NPC deceased mangled words in its description. The analysis names NPCs by id, skips with a warning what it cannot apply, and catches only its call; the operations live once in `engine/correction.yaml`. New item 9h.24.

Quality gate: 1625 tests, coverage 92.76%. Save format unchanged. Elvira about $0.46.

## [2026.10.18.8] — 2026-10-18

Step 9h: the principle-3 audit of `tools/`, with its items of 9h.13. Queries (hits): broad except 1, except handlers 1, `is None` 1, fallbacks 6, falsy returns 1, `isinstance` 4, single-reference functions 13 of 15, single-call bodies 2, test parameters 5; about fifteen violations. The tool registry registers a tool by name with an empty parameter schema (the parameter code is in git history), a tool call is a `ToolCall`, and `tools/handler.py` leaves the AI-call carve-out. A move that rolls or marks a track is offered only while a track of its type is active (`engine/move_availability.yaml`), and `find_progress_track` raises when it finds none. Fixed with it: classic's Undertake a Journey starts its journey, Enter the Fray's weak hit leaves the foe in control, and a successor no longer inherits the combat position.

Quality gate: 1612 tests, coverage 92.61%. Save format unchanged. Elvira about $0.34.

## [2026.10.18.7] — 2026-10-18

Step 9h: the principle-3 audit of `datasworn/`. Oracle tables are looked up once through the setting chain (`datasworn/settings.py` → `SettingPackage.oracle_table`, raising for a missing path, with `has_oracle` for optional tables), where six places did it on their own, and the action and theme oracles now read the chain too. `active_package` and the moves' second reading of the setting yaml leave, fields only tests read leave the moves, and the Datasworn fields all four rulesets carry are read strictly.

Quality gate: 1610 tests, coverage 92.58%. Save format unchanged. Elvira about $0.46.

## [2026.10.18.6] — 2026-10-18

Step 9h: the database is gone instead of audited, with the user's consent. Only the Director's tool read it, while most of its tables and queries were written and never read; the tool now reads the game state, and the in-memory SQLite copy, its schema, sync, queries, and tests leave. The Director's prompt and tool both show an NPC's recent observations (`npc/memory.py` → `recent_observations`), and Elvira counts the Director's tool calls correctly.

Quality gate: 1619 tests, coverage 92.59%. Save format unchanged. Elvira about $0.47.

## [2026.10.18.5] — 2026-10-18

Step 9h.15, the rest of the parameters that exist for tests, and the check the user asked for before every commit. Seven parameters production never set are gone, among them the fixed rolls of the fate chart, the scene check, the adjustments, and the event focus (tests fix the dice through `tests/_helpers.py` → `fix_dice`), and twenty-two defaults every production call overrode are required. Two write-only stores went: `MemoryEntry._score_debug` and the user settings file `settings.json`. CONTRIBUTING.md's workflow gains step 4, reading the whole diff before the commit, and the roadmap opens with a section Always.

Quality gate: 1650 tests, coverage 92.56%. Save format breaks (`MemoryEntry._score_debug`). Elvira about $0.44.

## [2026.10.18.4] — 2026-10-18

Step 9h, the user's decisions on 9h.15 and on the retry's catch, left to the session with a standing wish for lean, KISS, YAGNI, and DRY code. CONTRIBUTING.md gains No parameters for tests. `EngineConfig` is gone; the narration language comes from `config.yaml` alone, and Elvira reaches another one through `STRAIGHTJACKET_CONFIG`. Test-only seams and defaults in `ai/` went. Fixed: `create_with_retry` recognised a connection error by its name, so the OpenAI SDK's timeout was never retried; it now reads the class hierarchy. The retry's catch keeps covering the request built inside the provider's call (9h.22 settled).

Quality gate: 1651 tests, coverage 92.55%. Save format unchanged. Elvira about $0.51.

## [2026.10.18.3] — 2026-10-18

Step 9h: the principle-3 audit of `ai/`, with the narration items of 9h.13 and 9h.19. Queries (hits): broad except 8, except handlers 9, `is None` 36, fallbacks 37, falsy returns 26, single-reference functions 27 of 74, single-call bodies 11, parameters with a default 15; about thirty violations. Each AI-call try now holds only the call and the reading of its answer, so a configuration or engine fault no longer reaches the player as an unreachable AI. Dead structure went, among it the Anthropic adapter's tool-loop conversion and cached schemas. A narration the provider reports complete is no longer trimmed (9h.19); a truncated one is trimmed at sentence breaks from yaml.

Quality gate: 1651 tests, coverage 92.53%. Save format unchanged. Elvira about $0.49.

## [2026.10.18.2] — 2026-10-18

Step 9h, more of the rulebooks in the engine, at the user's request. Moves whose roll options name no stat roll with what they name (9h.21): Check Your Gear, Set a Course, and Make Camp with supply, Develop Your Relationship with the connection's rank (`mechanics/roll_sources.py` → `roll_source_without_stat`). The Brain is asked again for a stat its move does not offer. A thread gains weight when a scene invokes it by anything the engine can see (`game/scene_finalization.py` → `invoked_threads`).

Quality gate: 1650 tests, coverage 92.45%. Elvira about $0.35.

## [2026.10.18.1] — 2026-10-18

Step 9h, the user's decisions on 9h.1 and 9h.20. An action move that offers stats but comes back from the Brain with stat `none` is asked again once (`retry.brain_stat_retries`), and a second answer without a stat fails the turn, where it played as dialog. A rolled move that acts on a vow adds weight to the vow's thread (`mechanics/tracks.py` → `vow_acted_on`, registered in `docs/divergences.md`), replacing a step that never fired.

Quality gate: 1642 tests, coverage 92.41%. Elvira about $0.17.

## [2026.10.17.13] — 2026-10-17

Step 9h: the principle-3 audit of `game/`, the first under AUDIT.md's new form, which fixes in the session and writes no report file; the old fix-files' open items moved to roadmap 9h. Queries (hits): broad except 1, except handlers 1, `is None` 31, fallbacks 36, falsy returns 10, `isinstance` 1, single-reference functions 53, single-call wrappers 1, test parameters 8; about thirty violations. The deferred Director's broad catch is gone and its request is a `DirectorCall`; guards became strict lookups. A chapter no longer copies what carries over into its summary and back (9h.3). Fixed: new NPCs reached the Mythic characters list under the AI's label.

Quality gate: 1635 tests, coverage 92.40%. Save format breaks (`ChapterSummary` loses its copies). Elvira about $0.52.

## [2026.10.17.12] — 2026-10-17

Step 9h: the principle-3 audit of `npc/`. Every new NPC's name is rolled, where a game without a setting gave it the AI's label; dispositions no longer pass through a synonym map (its yaml removed with the user's consent); redundant guards in activation, memory, and matching went, and `next_npc_id` returns the id alone. The roadmap asks every session to move finished work to DONE and shorten it, at the user's request.

Quality gate: 1651 tests, coverage 92.39%. Save format unchanged. Elvira about $0.42.

## [2026.10.17.11] — 2026-10-17

Step 9h: the principle-3 audit of `mechanics/`. No broad except; the violations were guards for impossible states, mostly silent. An unknown impact, clock type, effect, fate method, time of day, bonus, or complication clock now raises, and the fate chart refuses a chaos factor it has no column for. Fixed: the second adjustment of an altered scene could raise after ten re-rolls. `_next_threat_id` lives once in `mechanics/threats.py`. Open items 9h.15 to 9h.18 and 9j.7 recorded.

Quality gate: 1653 tests, coverage 92.37% (floor raised to 92). Save format unchanged. Elvira about $0.50.

## [2026.10.17.10] — 2026-10-17

Step 9h: the principle-4 audit, no backwards compatibility, all three passes. No code migrates an old save, but several readers let malformed data through and now refuse it: saves with a null or a plain value where the type does not allow one, a turn's resource snapshot, every hand-built engine yaml section at every depth, and `config.yaml`, with `extra_body` now required. A flaky test that seeded the random generator before two threads drew from it now seeds afterwards.

Quality gate: 1656 tests, coverage 92.25%. Save format unchanged; malformed saves no longer load. Elvira about $0.60.

## [2026.10.17.9] — 2026-10-17

The user settled the principle-2 audit's open questions with two standing choices, now rules in CONTRIBUTING.md: config over code, and what belongs together lives together. Applied at once: every system's dice and the score cap in `engine/dice.yaml`, the ticks per box in `engine/progress.yaml`, named NPC status groups in `engine/enums.yaml`, and parse patterns in yaml. `get_current_act` raises without a blueprint instead of inventing an act, and the emergent clock and threat counts live once in `mechanics/clocks.py` and `mechanics/threats.py`.

Quality gate: 1651 tests, coverage 92.27%. Save format unchanged. Elvira about $0.50.

## [2026.10.17.8] — 2026-10-17

Step 9h: the principle-2 audit, config-driven, all four passes. The fate check reads Mythic's own table from `data/mythic_gme_2e.json`, and the hand-copied odds leave `engine/fate.yaml`. Readable text Python wrote moved to `prompts/`, `strings/`, and engine yaml, and thresholds and groupings to yaml, with one shared list of sentence-ending marks. Fixed on the way: an empty epilogue fails like an empty narration, nothing is named "Unnamed threat", and the save list's delete button has an accessible name. Five questions for the user became 9h.12.

Quality gate: 1649 tests, coverage 92.17%. Save format unchanged. Elvira about $0.50.

## [2026.10.17.7] — 2026-10-17

Step 9h, three substeps. 9h.2: Ask the Oracle without a setting raises, and a progress roll or mark on a track of the wrong kind is refused (`call_brain`) or raises (`find_progress_track`) instead of playing on zero boxes. 9h.10: the hand-written tensions that chosen truths started as threads are gone, and step 10b names the truths' own quest starters instead. 9h.11: the opening's memory updates are read as the schema requires.

Quality gate: 1648 tests. Save format unchanged. Elvira about $0.47.

## [2026.10.17.6] — 2026-10-17

The campaign's tone, substep 9h.9, chosen with the user. Every game had an empty tone, so every chapter's structure fell back to an even chance. Character creation now offers a tone, preset to the setting's new `default_tone`; it decides each chapter's structure through `story.kishotenketsu_probability` and reaches the narrator as its tone authority. The dead `setting_archetype` field is gone. Measured first: the blind reader preferred the toned prompt 11 to 5, mostly on misses.

Quality gate: 1650 tests. Save format breaks (`setting_archetype` is gone). About $2.50 for the measurement and Elvira.

## [2026.10.17.5] — 2026-10-17

A Sundered Isles Elvira session, the check for the name matcher change of 2026.10.17.4, found a fault in the same path: a figure that shared a word with a rolled NPC's label renamed her. An NPC whose name the engine rolled is now matched only by its own name and its exact earlier labels, and no label replaces a rolled name.

Quality gate: 1648 tests, coverage 92.09%. Save format unchanged. Elvira about $0.49.

## [2026.10.17.4] — 2026-10-17

Step 9g: tests that play a turn, a correction, a momentum burn, or a chapter transition build their game through the real character creation (`tests/_creation.py`, with a scripted provider). It surfaced what hand-built states hid: correction tests asserted an artifact of the snapshot, and the name matcher ignored a short name that is a whole word of a known one ("Kira" beside "Kira Vance"), which now matches. Step 9h becomes NEXT STEP.

Quality gate: 1646 tests, coverage 91.97% (floor raised to 91). Save format unchanged. No Elvira session.

## [2026.10.17.3] — 2026-10-17

Documentation only. Step 10 gains substep 10.7, at the user's request: at a generated place, a miss takes its worsening from the place's own peril table and an offered opportunity from its opportunity table (Starforged's location themes, derelicts, vaults, planets, and space; Sundered Isles' overland, caves, ruins, and shipwrecks), so the soft and unconnected costs that Elvira's audit keeps finding on misses come from the source tables instead of the narrator. The roadmap's notes for sessions with the user record the user's preference to settle from the source material whatever a rulebook table can settle.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.17.2] — 2026-10-17

Step 9e, the open findings from Elvira runs, each fixed in the engine. A `present` fact answered no about the action's target releases it; the metadata extraction offers only known NPC ids; an NPC records whether its name was rolled, so a different full name makes a new figure while a named lore figure takes its revealed name; a description match keeps the known name. Blueprint voicing asks once more when its counts are wrong, and in dialogs the NPC's fact budget governs, both the user's choices.

Quality gate: 1641 tests, coverage 91.52%. Save format breaks (`name_rolled`). About $1.70 for two Elvira sessions and the dialog measurement.

## [2026.10.17.1] — 2026-10-17

Step 9d, generators: places and NPC names come from the setting's own tables instead of the narrator. Each setting names under `generators` the table each role of a category rolls, and `datasworn/oracle_rolls.py` follows Datasworn's roll instructions. When the Brain moves the character to a place the world does not know, it names the place's kind, and the engine rolls it, keeps it, and gives the narrator its details as `<generated>`. The decisions, taken with the user, are under Decisions in the roadmap.

Quality gate: 1635 tests, coverage 91.19%. Save format breaks (the world keeps its generated places). Elvira about $1.75.

## [2026.10.17.0] — 2026-10-17

Documentation only: step 9f closes, at the user's choice. Two more narrator-prompt variants with a longer word budget were measured and neither won; after six rounds in which rewording stayed within the noise, the faults that remain are for the engine. Measuring the extraction prompts moves to the new step 9m, and 9d, generators, becomes the next step. About $4.

Quality gate: project-rule scans clean; no code, prompt, or configuration changed.

## [2026.10.16.8] — 2026-10-16

Step 9l, the user's idea: a weak-hit complication of Gather Information or Compel can start a four-segment threat clock (`mechanics/complications.py`), named from the story-complication table or a Mythic action pair, one open at a time; it fills every scene and strikes unless the Brain aims a hit at it (`target_clock`). Elvira gains a `complication` scenario. The roadmap keeps finished work in a short DONE section.

Quality gate: 1621 tests, coverage 91.09%. Save format unchanged. Elvira about $2.

## [2026.10.16.7] — 2026-10-16

The weak hit of Gather Information and Compel follows the rulebook, at the user's choice: its cost is the complication the move text names, and it may be subtle. A `complication` effect in `engine/move_outcomes.yaml` gives it to the narrator as a consequence it must tell, and the narrator's WEAK_HIT rule takes a named complication as the cost. The user's idea of a complication that strikes only when left alone becomes step 9l.

Quality gate: 1606 tests, coverage 90.98%. Save format unchanged. Elvira about $0.43.

## [2026.10.16.6] — 2026-10-16

Documentation only: the 9f.11 branch measured with a WEAK_HIT rule that counts a named complication as the cost, on the three weak hits of the set. The audit no longer missed a cost, but the blind reader preferred the current narrations 10 to 3, because they show a loss where the branch shows a complication. Whether these weak hits follow the rulebook or keep the stricter loss is now an open decision for the user under 9f.11. Under 1 dollar.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed on main.

## [2026.10.16.5] — 2026-10-16

Documentation only: 9f.6 and 9f.11 measured, neither adopted. A budget of 300 to 400 words lost the blind reading 7 to 14, the extra words going to NPC facts beyond the budget and moves the player did not choose. 9f.11's named weak-hit complication waits on a branch until a matching WEAK_HIT rule is measured with it. The blind reader no longer counts length. About $2.

Quality gate: project-rule scans clean; nothing changed on main.

## [2026.10.16.4] — 2026-10-16

Documentation only. Step 9f spends credits only where a change shows something, at the user's wish: a variant targets a problem found in measured narrations, gets the audit and the blind reading first, and the ten Elvira sessions only on a clear signal. The first variant under that rule paired "looking touches nothing" with a visible cause for every setback; the misses recovered from v14, but player-character findings stayed at 41 and 41 and the blind reader preferred the current prompt 9 to 7, so no Elvira sessions ran and the prompt stays. About 1.50 dollars.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.3] — 2026-10-16

Documentation only: the first round of step 9f against a new audit baseline (98 and 122 findings). 9f.9 and 9f.10 close without a prompt change; three narrator variants were measured and none adopted (9f.3, a replaced example, and a rule that looking touches nothing). `docs/ai.md` gives the reason the clusters send no sampling parameters. About $25 at full price.

Quality gate: project-rule scans clean; no code, prompt, or configuration changed.

## [2026.10.16.2] — 2026-10-16

Documentation only: a new Elvira baseline for step 9f under the Haiku 5.5 judge. Ten sessions of the unchanged prompt (the five comparison situations twice) scored 6.41 ± 0.14 overall and 3.81 for result integrity, where GPT-6 Luna had scored the same prompt 7.52 ± 0.18, so Haiku judges more strictly; the measuring setup's README names the new baseline. Two engine warnings: the Brain's known Set a Course as dialog (step 25), and blueprint voicing returning one revelation of three, since Anthropic does not enforce array counts, now a finding under step 9e. About 6.30 dollars at full price for the ten sessions.

Quality gate: project-rule scans clean. No code, prompt, or configuration changed.

## [2026.10.16.1] — 2026-10-16

Elvira's player and judge run on Claude Haiku 5.5 instead of GPT-6 Luna, at the user's choice, since the monthly Anthropic credit covers them: the player without thinking, the judge at effort low with room for 16,000 tokens, and a null temperature now accepted. A judge tends to favour its own model family, so Elvira scores from before this version are no baseline; step 9f needs ten fresh sessions of the unchanged prompt first. A four-turn Elvira session in Sundered Isles ran with the Anthropic key alone: the judge scored every narration, no engine warnings.

Quality gate: 1602 tests green, project-rule scans clean, coverage 90.97%, ruff and mypy --strict clean. Save format unchanged.

## [2026.10.16.0] — 2026-10-16

A critical read of every md file against the code, correcting what had drifted (a removed tool loop, AI decisions left out, provider notes, Delve's 12 domains), with duplicates pointing to one place and this log at a few sentences per entry. The correction analysis and blueprint voicing escape player text, the layer scan keeps `tools` from `ai`, and a setting's `id` must equal its file name. Roadmap steps 14a to 36 become short sketches. The Yaml content boundary states the user's choice: game content comes from the sources, an oracle, or as the last resort the AI, never by hand.

Quality gate: 1602 tests, coverage 90.96%. Save format unchanged. Elvira about $0.48.

## [2026.10.09.4] — 2026-10-09

A hit on a search no longer reaches the narrator beside a fact saying that nothing useful is there: `mechanics/facts.py` → `overrule_facts_by_hit` drops such a no on a hit, in the turn, the momentum burn, and the state correction. A narrator prompt with targeted changes for Sonnet (9f.15) was measured and not adopted.

Quality gate: 1599 tests, coverage 90.96%. Save format unchanged.

## [2026.10.09.3] — 2026-10-09

Every role runs Claude Sonnet 5.5 at effort medium, the user's choice after comparing it with Haiku 5.5 (blind reading 14 to 6, Elvira 7.60 against 7.12, at about ten times the cost). Fixed what Sonnet showed: the Director's reflection fields are plain strings to stay within Anthropic's limit on nullable fields, the Director no longer gets a tool round (`run_tool_loop` is gone), and the Anthropic adapter no longer sets an automatic cache mark beside its own. A twelve-turn session costs about 54 cents.

Quality gate: 1592 tests, coverage 90.94%. Save format unchanged.

## [2026.10.09.2] — 2026-10-09

Every role ran Claude Haiku 5.5 at effort medium, the user's choice; the clusters stopped sending `temperature`, `top_p`, and `top_k`, which Haiku 5.5 refuses. Anthropic caching works: the adapter marks the part of the system prompt that is fixed within a game. Fixed in what the models are told: a progress mark no longer reads as a wound, Director notes name the NPC, and the Brain and the Director see the world. Every prompt and engine text was rewritten except the narrator's, whose rewrite lost the blind reading 3 to 14.

Quality gate: 1591 tests, coverage 91.00%. Save format unchanged.

## [2026.10.09.1] — 2026-10-09

Claude Haiku 5.5 measured against GLM 5.3 for every role and effort, at the user's request. One engine change: the Anthropic adapter passes schemas through the SDK's `transform_schema`, since structured outputs refuse limits such as `maxItems`, and the engine checks counts after parsing. Haiku at medium won the blind readings and scored 7.44 against 6.82 in Elvira at about a sixth of the cost, but its first sentence came after 10.8 seconds instead of 3.1.

Quality gate: 1581 tests, coverage 90.95%. Save format unchanged.

## [2026.10.09.0] — 2026-10-09

A critical read of every md file against the code, and the fixes it called for. Act transitions are checked in every turn's scene-end bookkeeping (`story_state.py`) instead of depending on the Director. The WebSocket origin check allows LAN play and IPv6 loopback. Player and save names with a path separator or a leading dot are refused. The import-layer scan splits the engine core into a base and the rest, `run.py` and `data/data.py` join the comment scan, and the register gains three entries.

Quality gate: 1580 tests, coverage 90.91%. Save format unchanged.

## [2026.10.04.6] — 2026-10-04

Documentation only. The roadmap no longer notes the MiMo evaluation: the user is not changing models now and will take it up again later if needed.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.5] — 2026-10-04

Documentation only. The roadmap's notes for sessions with the user say where the measuring setup for prompt tuning lives (outside the repository, with a README on capturing situations, measuring a variant, and reading blind) and that its captured situations predate the player-agency line of 2026.10.04.4. They also note that the evaluation of MiMo-V2.6-Pro at Prima Labs waits for Prima Labs' answer about its rate limit, with the report beside the measuring setup.

Quality gate: 1557 tests green, project-rule scans clean (documentation drift included). No code, prompt, or configuration changed.

## [2026.10.04.4] — 2026-10-04

Step 9f, substeps 1 and 2: the narrator's action and dialog tasks end with a player-agency line in the system prompt's own wording. Measured on GLM 5.3 over fourteen captured situations, audited by GPT-6 Luna: player-character overreach fell from 49 findings to 30 and the audit total from 158 to 131, and no other kind rose beyond the spread. A length line was not adopted, since together with the agency line it left weak hits without their cost more often. Step 9f gained three substeps from the measurement. One Elvira session: no engine warnings, player agency 4.5 of 5.

Quality gate: 1557 tests green, coverage 90.79%.

## [2026.10.04.3] — 2026-10-04

Documentation only. Step 9f, prompt tuning, becomes NEXT STEP ahead of 9d at the user's choice, with substeps, a definition of done, and a measuring method: the same captured situations for every variant, an audit by a judge from another model family, and a blind reading with balanced positions. A first comparison of GLM 5.3 with MiMo-V2.6-Pro scored both alike. Step 9e gains a finding: a fact can place an NPC out of reach while that NPC is the scene's target.

Quality gate: 1557 tests green, coverage 90.77%.

## [2026.10.04.2] — 2026-10-04

Documentation only. Scene challenges turned out to be configured but unreachable: Begin the Scene has no roll, so no scene-challenge track ever exists, and the `fill_clock` effect of their misses is read by nothing. New step 9k makes them playable from the rulebook, and `docs/mechanics.md` says they are not playable yet.

Quality gate: 1557 tests green, coverage 90.81%.

## [2026.10.04.1] — 2026-10-04

Documentation only. The md files state the current state, each fact in one file: reasons are written out instead of pointing to CHANGELOG versions, process rules live in CONTRIBUTING.md, the divergence register is the one list of where the AI still decides, and this log starts at 2026.09.24.0. The user decided that death comes only through Face Death; step 9j.5 builds it.

Quality gate: 1557 tests green, coverage 90.77%.

## [2026.10.04.0] — 2026-10-04

The Brain chooses a track by id, and track names reach its prompt escaped. Action moves that mark progress (Strike, Clash, Gain Ground, expeditions, journeys, delves, scene challenges) never marked it, because Datasworn gives a track category only to progress rolls; they name their category in `engine/track_moves.yaml` now. The position resolver's secured-advantage factor fires again. The design document is linked instead of copied, and Elvira has `docs/elvira.md`. Two Elvira sessions in Starforged: Strike and Clash filled the fight's track.

Quality gate: 1557 tests green, coverage 90.76%. Save format unchanged.

## [2026.09.29.12] — 2026-09-29

Step 9c, soft misses from the engine side. On a miss every NPC present withholds, the target NPC's agenda, memories, and secrets stay out of the prompt, and Director guidance and a pending revelation wait for a hit; an information miss settles `useful` as no, and a miss with a match rolls the story-complication oracle where the setting has one. Elvira gained a `miss` scenario. On audited misses, result integrity rose from 3.0 to 3.4 of 5; three other variants measured no better and were dropped.

Quality gate: 1550 tests green, coverage 90.65%.

## [2026.09.29.11] — 2026-09-29

Documentation only. The design document is now `docs/narrative_rpg_engine_v2_4.md` instead of a PDF, so a session reads it with the other md files; the text is unchanged (5,493 words in both, compared word by word), with its sections as headings and its prompt examples as code blocks. README, ORIGINS, ARCHITECTURE, and the divergence register link to it.

## [2026.09.29.10] — 2026-09-29

Documentation only. The working agreements that lived only in conversation are now in the roadmap, so a fresh session can pick up the work: short CHANGELOG entries, commit and push per finished release, Elvira sessions as part of a step, Dutch plain-prose answers for a screen-reader user, and starting a session by reading every md file. Step 10 notes the Location Crafter in case the user buys it.

## [2026.09.29.9] — 2026-09-29

Documentation only. At the user's request the priorities list is gone and every item on it is a numbered step in the order of work: 9c soft misses, 9d generators, 9e Elvira findings, 9f prompt work, 9g fixtures, 9h principle audits, 9i revelations, 9j rules conformance. A new finding becomes a substep or a step in the same commit.

## [2026.09.29.8] — 2026-09-29

Step 9b, chapters as Mythic adventures. The EdgeTales resets are gone: health, spirit, supply, momentum, and clocks carry over, the chaos factor restarts at Mythic's 5, and a game that is over continues only through succession. The engine writes the chapter record from its own data, so the `chapter_summary` AI role is removed. An Elvira `chapter_end` session reached the new chapter with its clocks carried over and no engine warning. The save format breaks.

Quality gate: 1529 tests green, coverage 90.44%.

## [2026.09.29.7] — 2026-09-29

Documentation only. The user made chapters the next step: new step 9b treats a chapter as Mythic's and the Adventure Crafter's adventure within a campaign and removes what came from EdgeTales (refilled health, spirit, supply, and momentum, wiped clocks, an AI-written chapter summary), with two register entries until then. The generators move to step 9c and engine-settled revelations to 9d; earlier CHANGELOG entries keep the old numbers.

## [2026.09.29.6] — 2026-09-29

Documentation only. A one-time coverage map checked every part of the four Datasworn rulesets, Mythic GME 2e, the Adventure Crafter, Blades, and the design document against the code and the roadmap. What stood nowhere became roadmap work, including new steps 10b, 13c, and 36, and the register gained the session moves, Mythic's rules-system parts, and foe actions decided by the AI.

## [2026.09.29.5] — 2026-09-29

The user's two decisions, built from the classic move texts. Classic Ironsworn marks experience by the vow's rank when Fulfill Your Vow hits, instead of filling Starforged's legacy tracks. Draw the Circle takes the boasts the player declares, read by the Brain, each for +1 momentum and its cost from `engine/boasts.yaml`. New register entries: a classic successor inherits no legacy boxes, and a duel opens no combat track.

Quality gate: 1535 tests green, coverage 90.47%.

## [2026.09.29.4] — 2026-09-29

Documentation only. ARCHITECTURE.md records the order of preference: a tabletop system decides first, an engine rule second, and the AI only writes prose and reads free text. The user decided that classic Ironsworn earns experience by its own rule and that boasts are modelled. A new sketch step lets the engine settle when a revelation lands, so the revelation-check AI call can go.

## [2026.09.29.3] — 2026-09-29

The opening extraction asks for the place's short name as the narration gives it, two to five words, with what happens there in `scene_context`. Before, all three openings of the day's classic sessions came back as descriptive sentences of 15 to 20 words, which then stood in `<location>`, `<prev_locations>`, and `<fact about>`; after, four openings (three Sundered Isles, one classic) gave three-word names such as "Terracoyote Crossing wayhouse". No engine warning besides one Director time-out.

Quality gate: 1526 tests green, thirty project-rule scans clean, ruff and mypy --strict clean.

## [2026.09.29.2] — 2026-09-29

`docs/divergences.md` becomes a register: every departure says why and ends with a status (Permanent, Until step N, or Open), and a project-rule scan rejects an entry without one. `apply_progress_and_legacy` takes the rolled track and raises instead of assuming a rank. Setting yaml gains a required `playable`, so Delve is no longer skipped by name.

Quality gate: 1526 tests green, coverage 90.42%.

## [2026.09.29.1] — 2026-09-29

A correction of a misread input replays the turn through the turn's own code (`replay_turn`) with the same scene type, facts, and dice, instead of a separate copy that lost misses, track creation, clock ticks, and the scene end. The correction AI no longer decides whether to reroll, and a corrected turn can offer a momentum burn. Elvira's new checks caught a restore that cut the narration history by length; it is copied whole now. The save format breaks.

Quality gate: 1523 tests green, coverage 90.48%.

## [2026.09.29.0] — 2026-09-29

Step 9a, fact resolution: the Brain names the facts an action or question turns on, Mythic's fate chart settles them with odds the engine derives from `engine/fact_resolution.yaml`, and the narrator gets them as `<facts>`. A fact belongs to its place, and a hit settles a yes where the type says so. The momentum burn resumes from a snapshot taken after the roll instead of overwriting the previous turn. Two Elvira sessions: facts resolved in play, no engine warnings. The save format breaks.

Quality gate: 1517 tests green, coverage 90.52%.

## [2026.09.27.2] — 2026-09-27

Documentation only: the user decided step 9a's open points. A fact hangs on an NPC id or on the current location, every fact clears when the player moves and at a chapter start, each fact type says whether a hit clears it, and resolved facts live in one list on the world state.

## [2026.09.27.1] — 2026-09-27

The engine owns the opening clock and the time of day. The opening extraction asked the model for both and overwrote the engine's clock and time, and a succession discarded its extraction, so the successor's opening NPCs were never registered. The extraction now returns only NPCs, memories, deaths, location, and scene context; every opening starts at `opening.time_of_day`, only a new game gets an opening clock, and a succession applies its extraction. Two Elvira sessions in Sundered Isles reached succession and a chapter transition without engine warnings. The user decided how step 9a derives its odds.

Quality gate: 1489 tests green, coverage 90.15%. Save format unchanged.

## [2026.09.27.0] — 2026-09-27

Documentation only: the working documents restructured along common practice, with duplicates and claims the code contradicts removed. ARCHITECTURE.md becomes a bird's-eye view, CONTRIBUTING.md returns, and the details move to `docs/` (`ai.md`, `mechanics.md`, `settings.md`, `divergences.md`); the documentation-drift scans follow. Roadmap step 9 is split so that fact resolution comes first. The md files went from about 257 to 161 KB.

Quality gate: 1494 tests green, coverage 90.14%.

## [2026.09.26.20] — 2026-09-26

The "runaway" of GLM 5.3's structured answers was a carriage-return loop inside the JSON, which a JSON grammar allows. Every cluster bans the 396 tokens of its tokenizer that hold a carriage return through `logit_bias`, and every call with a schema gets the compact schema at the end of its prompt, so cached prefixes stay intact. Before, 3 of 220 structured calls broke off at the token limit; after, 0 of 360. Every role runs on GLM 5.3 again; an eight-turn Elvira session showed no failures.

Quality gate: 1494 tests green, coverage 90.13%. Save format unchanged.

## [2026.09.26.19] — 2026-09-26

GLM 5.3's structured failures probed: 3 of 220 structured calls (1.4 percent) broke off at the 8192-token limit after a short piece of JSON, taken for a reasoning runaway, so the structured roles stayed on GLM 5.3 Flash. 2026.09.26.20 found the real cause, a carriage-return loop. The roadmap item about the Director reaching its three-round tool limit was dropped, since one tool cannot reach it.

## [2026.09.26.18] — 2026-09-26

A third group of narrator-prompt changes (a WRONG/RIGHT pair for failed searches and questions, the system prompt without its MUSTs and NEVERs) was measured on a forced-miss bench and not adopted. That bench is not in the repository. With earlier attempts, five instruction variants left investigation misses as soft as before, so the remaining softening looks like the model's. The wording of 2026.09.26.17 was corrected: the model mix was kept for reliability and cost, not for higher scores.

## [2026.09.26.17] — 2026-09-26

The narrator and creative clusters stayed on GLM 5.3; the Director, the Brain, judgment, and extraction went back to GLM 5.3 Flash after GLM 5.3's JSON failed a few times on Together. Over four sessions the mix matched all-GLM-5.3 on the judged scores at less than half the cost (7.3 against 16.5 cents for eight turns). Reverted in 2026.09.26.20.

## [2026.09.26.16] — 2026-09-26

Prompt review, second group: word budgets for the opening and chapter opening (250 to 350 words) and the epilogue (350 to 500), whose reflection on the character's growth is the one named exception to PLAYER AGENCY; the Brain prompt no longer restates the fields its schema enforces; the extractor prompts read the opening clock and the dispositions from configuration.

## [2026.09.26.15] — 2026-09-26

Prompt review, first group: three contradictions removed (the Director rules out the supernatural only where `<world>` lacks it, the chapter opening takes history only from what is established, the tone block follows the Director only for world and NPCs), and the Director's fixed task moved ahead of the changing scene, which raised its cached input from 27 to 50 percent.

## [2026.09.26.14] — 2026-09-26

Every role on GLM 5.3 through Together, the user's choice: on the forced-miss bench it followed the instructions about as well as GLM 5.3 Flash and finished a narration in 2.1 seconds against 3.3, at about nine times the price per token.

## [2026.09.26.13] — 2026-09-26

Elvira's judge also sees the previous narration, the backstory, the NPC descriptions, and the rolled move's own text for the result, so continuity no longer counts as invention and an unwelcome truth on a miss no longer as a silver lining. New baseline.

## [2026.09.26.12] — 2026-09-26

The narrator stops taking over the player character: a budget of 150 to 220 words, a PLAYER AGENCY rule covering the character's inner life, actions, words, and past, a Director rule that keeps its guidance off the player character, and the narrator at temperature 1.0 and top_p 0.8. Over six measured variants this raised judged player agency from 2.75 to 4.08 and cut complaints about the player character from 42 to 17 percent.

## [2026.09.26.11] — 2026-09-26

The Director's reflections become one required slot per selected NPC, keyed by its id, so a duplicate cannot be written; one tool, `query_game_state`, replaces `query_npc`, `query_active_threads`, and `query_active_clocks`.

## [2026.09.26.10] — 2026-09-26

Blueprint voicing fixes the number of acts, revelations, and endings in its schema with `minItems` and `maxItems` and calls once instead of asking again; `AIResponse` carries a host's reasoning text, and a Director failure shows its end.

## [2026.09.26.9] — 2026-09-26

The Director's retry of 2026.09.26.8 removed, since every failure ran to the 8192-token limit and a retry cannot prevent that; a failure now reports its stop reason, output and reasoning tokens, and JSON length, and the OpenAI-compatible adapter reports reasoning tokens.

## [2026.09.26.8] — 2026-09-26

The Director retried its final step once on invalid JSON (removed in 2026.09.26.9); a failed Director keeps the NPCs' importance accumulators instead of zeroing them.

## [2026.09.26.7] — 2026-09-26

The users folder follows `STRAIGHTJACKET_USERS_DIR` when set; Elvira keeps her players in tests/elvira/users.

## [2026.09.26.6] — 2026-09-26

The succession WebSocket tests save into a temporary users folder instead of the project's `users/`.

## [2026.09.26.5] — 2026-09-26

Every role on GLM 5.3 Flash through Together, the user's choice for its narration; Elvira stays on GPT-6 Luna. Together beat OpenRouter, Fireworks, and Baseten on time to the first sentence (2.9 seconds) because it also caches short prompts.

## [2026.09.26.4] — 2026-09-26

The startup check works with Together, whose `/models` returns a bare list the OpenAI SDK cannot parse; Together configured beside the other providers.

## [2026.09.26.3] — 2026-09-26

NPC statuses get one central list in `engine/enums.yaml`, and the correction schema limits `status` to it.

## [2026.09.26.2] — 2026-09-26

Elvira's player and judge name their own provider and model (GPT-6 Luna) instead of following the game; OpenRouter configured; cheap models measured against Luna (DeepSeek V4 Flash, GLM 5.3 Flash, Qwen3.7 Flash, Ling 3.0 Flash, Gemma 4 31B). Fix: the correction schema limits `disposition` to the known dispositions, after a model wrote a stance there and crashed the next turn.

## [2026.09.26.1] — 2026-09-26

The model-comparison harness removed at the user's request, so the project is the game plus Elvira again; a new test covers the engine lines only the harness reached; this CHANGELOG shortened up to 2026.09.26.0.

## [2026.09.26.0] — 2026-09-26

Every role on GPT-6 Luna again: reasoning effort `none`, the creative cluster `low`, and the Director at `none` because Chat Completions allows tool calls only there. Luna back in the Elvira and harness price tables. An eight-turn Elvira session found no problems and cost about one cent.

## [2026.09.25.6] — 2026-09-25

Every role on Fireworks' standard tier of GLM 5.3, a third cheaper than Fast; in play the first sentence came after about 11 seconds and a turn took about 28.

## [2026.09.25.5] — 2026-09-25

Measured, not adopted: GLM 5.3's standard tier narrated within the noise of Fast but made the player wait far longer. The Director was found to be half of a session's cost.

## [2026.09.25.4] — 2026-09-25

The narrator system prompt ordered for prompt caching (fixed rules first, per-turn character state last), which also measured better; cached input shown in the token log; a missing `recovery_MISS` memory emotion that ended turns added.

## [2026.09.25.3] — 2026-09-25

The narrator's miss rule describes what happens instead of what to avoid; GPT-6 Sol judges beside GLM in the harness; the Brain always names a new track; a correction to a dialog turn no longer tries to roll `dialog`.

## [2026.09.25.2] — 2026-09-25

Outright errors in the prompt files fixed: the correction analyser's role, cut off by the comment sweep of 2026.04.26.2; a literal unicode escape as the quote example; stealth routed to shadow as both rulebooks say; stale references to removed tools, fields, and the retry loop.

## [2026.09.25.1] — 2026-09-25

Player and save names that Windows cannot store are refused with `InvalidNameError` and a clear message; README and ARCHITECTURE say what the AI still decides.

## [2026.09.25.0] — 2026-09-25

The setting-yaml loader refuses unknown keys; the coverage floor rises to 90; the working documents are brought in line with the code. Releases 2026.09.24.52 to .62 were made on 25 September but kept the 24 September date.

## [2026.09.24.62] — 2026-09-25

Every cluster names its own provider, model, and extra body again; the shared `ai.model` of .61 is gone.

## [2026.09.24.61] — 2026-09-25

Every role on GLM 5.3 Fast through Fireworks, Elvira's player and judge following the Brain; unused tooling removed (Elvira's narrator and model swaps, the harness contestants, the Luna and Claude price tables).

## [2026.09.24.60] — 2026-09-25

NPCs change location only when the narration names them; the Brain prompt explains every field of its schema, enforced by a test.

## [2026.09.24.59] — 2026-09-25

The Director's output schema offers only the NPCs chosen for reflection. Findings on GLM 5.3's always-on thinking and on Gemini 3.8 Flash through Google's own API.

## [2026.09.24.58] — 2026-09-25

Whole Elvira sessions on one model per candidate: GPT-6 Luna 7.7 seconds per turn and about $0.01 per session, GLM 5.3 Fast 11.9 seconds and $0.27, Gemini 3.8 Flash 7.5 seconds and $0.09. Streamed sentences decode literal unicode escapes; the Brain schema limits `bonus_id`, `target_npc`, and `target_track` to what the prompt offers.

## [2026.09.24.57] — 2026-09-25

The harness rubric values atmosphere and sensible invention and uses a two-family panel, because a judge favours its own family. Fifteen narrators compared: Gemini 3.8 Flash and GLM 5.3 Fast ahead, GPT-6 Luna with the lowest atmosphere score. Elvira runs on one model for everything.

## [2026.09.24.56] — 2026-09-25

A ten-model narrator comparison with reasoning off or as low as allowed, judged by GPT-6 Sol: Gemini 3.8 Flash, GPT-6 Luna, GPT-6 Sol, and GLM 5.3 Fast within a few tenths of each other, Luna by far the cheapest and fastest.

## [2026.09.24.55] — 2026-09-25

Three engine bugs fixed: a bond keyed scene spawned for a character who is not an NPC, the Brain able to play a move the situation does not allow, and unknown Director tool arguments failing a round.

## [2026.09.24.54] — 2026-09-25

Results of the deeper narrator test: Kimi K3 and Gemini 3.8 Flash narrated single scenes better than GPT-6 Luna, GLM 5.3 held up best over whole sessions, and all were slower and costlier than Luna.

## [2026.09.24.53] — 2026-09-25

A deeper narrator test: ten harder scenes, confidence intervals, paired comparison, and Elvira able to narrate with another model.

## [2026.09.24.52] — 2026-09-25

Two more narrator candidates measured (Muse Spark 1.3 and Qwen3.8 Flash), both below GPT-6 Luna.

## [2026.09.24.51] — 2026-09-24

Elvira plays prepared rare situations (`--scenario`: near death, chapter end, momentum burn, combat, a filling clock); the schema-strictness check became a test.

## [2026.09.24.50] — 2026-09-24

The model-comparison harness moved into the repository as `tests/modeltest/`, rebuilt on the engine's adapters, at the user's request.

## [2026.09.24.49] — 2026-09-24

Elvira varies setting and play style per run, judges with a model from another family, and survives AI failures, with one injected narrator outage per run that must roll back exactly.

## [2026.09.24.48] — 2026-09-24

Elvira's run reports leave the repository; `tests/elvira/runs/` is ignored by git.

## [2026.09.24.47] — 2026-09-24

Four decisions by the user: an AI failure pauses the turn and restores the snapshot, as the design document asks; loading returns exactly what was saved; step 9 returns `GeneratedEntity` or `ResolvedFact`; the Yaml content boundary covers setting yaml.

## [2026.09.24.46] — 2026-09-24

Documentation only: step 13b's move counts recounted; narrator-prompt issues recorded for a measured round.

## [2026.09.24.45] — 2026-09-24

Audit round against the project rules: strict loading, where an unknown or missing field raises and an old save is reported to the player as incompatible; typed config for Pay the Price and roll bonuses. The save format breaks.

## [2026.09.24.44] — 2026-09-24

The roadmap's Current state opens with priorities, working agreements, and how to run Elvira.

## [2026.09.24.43] — 2026-09-24

Documentation pruned and brought in line with the code.

## [2026.09.24.42] — 2026-09-24

Elvira reports every engine warning and error as a problem. The first such run found every Director call failing, because GPT-6 Luna refuses function tools with a reasoning effort in Chat Completions; the Director got its own cluster at reasoning effort `none`.

## [2026.09.24.41] — 2026-09-24

Roll bonuses reach real games: bare asset ids and paths, as character creation stores them, are now found.

## [2026.09.24.40] — 2026-09-24

Corrects the quality gate of .39, where mypy still reported two errors.

## [2026.09.24.39] — 2026-09-24

Corrects .38: duplicate progress-track ids are repaired too, and a vow and its thread stay linked.

## [2026.09.24.38] — 2026-09-24

A vow sworn twice no longer breaks the save.

## [2026.09.24.37] — 2026-09-24

Elvira records per turn what the engine did: bonuses, chained moves, Pay the Price, extraction, the Director and its tools.

## [2026.09.24.36] — 2026-09-24

Every role on GPT-6 Luna, the narrator included.

## [2026.09.24.35] — 2026-09-24

Elvira's judge gets its own token limit and reasoning effort `low`, after GPT-6 Luna's default reasoning used up the budget and left no verdict.

## [2026.09.24.34] — 2026-09-24

Classic Ironsworn marks its own lasting harm (maimed, corrupted).

## [2026.09.24.33] — 2026-09-24

Assets and connections give their roll bonuses: enabled abilities are tracked, the Brain names a bonus by id, and the engine takes the add from the rule text.

## [2026.09.24.32] — 2026-09-24

Every "with a match" clause is modelled, including oracle moves as chained moves and a connection's rank raise.

## [2026.09.24.31] — 2026-09-24

Moves that say "make another move" roll it in the same turn.

## [2026.09.24.30] — 2026-09-24

Outcomes on a match follow Starforged.

## [2026.09.24.29] — 2026-09-24

Pay the Price rolls the setting's official Datasworn table and applies its costs.

## [2026.09.24.28] — 2026-09-24

Turning points follow the Adventure Crafter: five slots, at most three None.

## [2026.09.24.27] — 2026-09-24

The Adventure Crafter's tables checked and pinned by tests.

## [2026.09.24.26] — 2026-09-24

Rules conformance for Mythic's lists and meaning tables, the Adventure Crafter's theme priority, and Blades clock sizes of 4, 6, or 8.

## [2026.09.24.25] — 2026-09-24

Legacy tracks, experience, and connections follow Starforged.

## [2026.09.24.24] — 2026-09-24

Move outcomes can differ per setting; Endure Harm and Endure Stress follow each rulebook.

## [2026.09.24.23] — 2026-09-24

"Add +1 on your next move" is banked and added to the next action roll.

## [2026.09.24.22] — 2026-09-24

Rules conformance, second pass: momentum per move outcome compared automatically with the Datasworn texts, Mythic checked, and the list of deliberate divergences recorded in ARCHITECTURE.md.

## [2026.09.24.21] — 2026-09-24

Negative momentum cancels a matching action die, as the rules say; Elvira counts the Director's tokens and has a calibrated judge.

## [2026.09.24.20] — 2026-09-24

Fix: the metadata and opening-setup extractions could not be routed since .9 and failed silently; a project-rule scan now requires every AI call to carry its own role name.

## [2026.09.24.19] — 2026-09-24

Narrator on Claude Opus 5.5, every other role on GPT-6 Luna; blueprint voicing asks for and checks the required counts.

## [2026.09.24.18] — 2026-09-24

Every role except the narrator on Claude Haiku 4.5.

## [2026.09.24.17] — 2026-09-24

The action roll follows Ironsworn: one d6 plus the stat, not two.

## [2026.09.24.16] — 2026-09-24

Elvira tests far more on her own (streaming checks, blind audit, save round trip, succession, coverage, report); she found broken dialog markup and a Director tool without a useful error.

## [2026.09.24.15] — 2026-09-24

Elvira runs again, with a smoke test in the normal gate.

## [2026.09.24.14] — 2026-09-24

Both SDKs used as intended: one retry layer honouring Retry-After, timeouts, refusals, and `max_completion_tokens` for OpenAI's own models.

## [2026.09.24.13] — 2026-09-24

Narrator on Claude Opus 5.5 at effort low.

## [2026.09.24.12] — 2026-09-24

Sentence-level narration streaming, so the screen reader starts after the first sentence.

## [2026.09.24.11] — 2026-09-24

All roles on Claude; the Anthropic adapter fixed for current Claude models.

## [2026.09.24.10] — 2026-09-24

The result tag in every action-turn narrator prompt was malformed XML and is now closed correctly; a test parses the engine-built scene as XML.

## [2026.09.24.9] — 2026-09-24

Providers can be mixed per role, and startup checks that every configured model still exists.

## [2026.09.24.8] — 2026-09-24

Dependencies brought to their current major versions.

## [2026.09.24.7] — 2026-09-24

Documentation only: step 9's fact-resolution trigger decided; the Brain flags undetermined facts and the engine resolves them through fate.

## [2026.09.24.6] — 2026-09-24

Rules and robustness fixes found by comparing with EdgeTales 0.9.67–0.9.96: NPC agency on dialog turns, Director reflections checked against the engine's selection, compel without bond progress, momentum reset floored at 0.

## [2026.09.24.5] — 2026-09-24

mypy runs in strict mode.

## [2026.09.24.4] — 2026-09-24

Import layers become a project rule; the track lifecycle moves to `mechanics/tracks.py`.

## [2026.09.24.3] — 2026-09-24

Five more ruff rule families enabled.

## [2026.09.24.2] — 2026-09-24

Documentation drift and the provider adapters get tests, and coverage gets a floor.

## [2026.09.24.1] — 2026-09-24

Project-rule scans hardened and three added.

## [2026.09.24.0] — 2026-09-24

Documentation re-sync after a four-month pause; `.gitattributes` keeps the design-document PDF binary.
