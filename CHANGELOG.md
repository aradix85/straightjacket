# Changelog

Straightjacket — AI-powered narrative solo RPG engine. See [ORIGINS.md](ORIGINS.md) for where it comes from.

This log starts at 2026.09.24.0, the restart after a four-month pause. Earlier releases, back to the fork from EdgeTales, and the longer text of entries that were later shortened are in git history (`git log -p CHANGELOG.md`).

## Versioning

Calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day.

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
