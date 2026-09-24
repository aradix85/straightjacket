# Changelog

Straightjacket — AI-powered narrative solo RPG engine.
Originally forked from [EdgeTales](https://github.com/edgetales/edgetales). See [ORIGINS.md](ORIGINS.md).

## Versioning

Straightjacket uses calendar versioning: `YYYY.MM.DD.N`, where `N` is a zero-based counter for releases on the same day. The first CalVer release is `2026.04.25.0`. Earlier `0.x.y` releases keep their original version numbers and are not renumbered. The switch was made because the project has no public API to version semantically against — the `0.x.y` numbers were running counters with no meaning, and dates carry the meaning the numbers didn't.

## [2026.09.24.40] — 2026-09-24

Corrects the quality gate of 2026.09.24.39, which stated mypy was clean while it reported two errors: ruff's automatic fix had turned the new link check into `renamed_tracks.get(thread.linked_track_id)`, and the thread's link can be None. The link is now checked for None before the lookup. The release script also only committed after the tests, not after ruff and mypy; from here each of the three must pass before a commit.

Quality gate: 1410 tests green, twenty-nine project-rule scans clean, coverage 89.80%, ruff check and ruff format clean, mypy --strict clean on 109 source files. Save format unchanged.

## [2026.09.24.39] — 2026-09-24

Corrects 2026.09.24.38, which claimed the damaged save from the run loads again. It did not: the duplicated vow had also produced a second progress track with the same id, and loading then failed on "UNIQUE constraint failed: progress_tracks.id" after the thread ids were repaired. That claim was written before the check's output was read.

`persistence.py` → `_repair_duplicate_ids` (replacing `_repair_duplicate_thread_ids`) now renames duplicate progress-track ids as well, and points each renamed duplicate thread at the renamed duplicate track it belongs to, so a vow and its thread stay linked. The damaged save itself could not be retried: the next Elvira run cleans its saves at start and had already removed it. A new test builds the same damage, two vow tracks and two linked threads with equal ids, saves, loads, and checks unique ids with the links intact.

Quality gate: 1410 tests green, twenty-nine project-rule scans clean, coverage 89.78%, ruff check and ruff format clean, mypy --strict clean on 109 source files. Save format unchanged.

## [2026.09.24.38] — 2026-09-24

A vow sworn twice no longer breaks the save.

Found by Elvira's long run with GPT-6 Luna: in turn twenty the Brain had the character swear a vow whose name matched an earlier one word for word. `game/turn.py` → `_maybe_create_track` builds the track id and the linked thread id straight from the vow name, so it created a second track and a second thread with the same ids. The turn failed on "UNIQUE constraint failed: threads.id" when the database synced, the game was saved anyway, and loading that save failed at the same sync, leaving it unusable. The bug predates this day.

Prevented: swearing a vow whose name matches an active vow creates nothing and logs it; a vow sworn again after the earlier one is completed or forsaken gets unique ids with a numeric suffix, via the new `ids.py` → `unique_id`. Repaired: `persistence.py` → `load_game` renames duplicate thread ids before syncing the database, with a warning, so a save already hit by the bug loads again; the damaged save from the run now loads with unique thread ids. Elvira: a load-back that raises is reported as a save/load problem instead of ending the run without a report.

Tests: new `tests/test_track_ids.py` (an active vow sworn again is not duplicated, a vow sworn again after completion gets unique ids, a save with duplicate thread ids loads with repaired ids) and an Elvira test for a failed load-back.

Quality gate: 1409 tests green, twenty-nine project-rule scans clean, coverage 89.79%, ruff check and ruff format clean, mypy --strict clean on 109 source files. Save format unchanged.

## [2026.09.24.37] — 2026-09-24

Elvira records what the engine did in each turn.

A long run could not show the day's new rules at work: Elvira's session log was a compact diagnostic without the narration, and nothing recorded whether the Brain chose a bonus, a move chained, a price was paid, or the Director used its tools.

Engine events. During a run Elvira attaches a handler to the engine logger and keeps, per turn, the lines whose prefix is listed under `logging.event_prefixes` in `tests/elvira/elvira_config.yaml` (bonuses, chains, Pay the Price, metadata extraction, opening setup, Director, tools, legacy, clocks, Adventure Crafter, move outcomes). They land in `TurnRecord.engine_events`. The engine gains the log line they needed: `pay_the_price` now logs the rows it rolled as `[PayThePrice]`.

Session log. The compact turn record now always carries the full narration, and when present the NPCs with status and disposition, the judge's verdict, the streaming figures, and the engine events.

Coverage and report. The coverage tracker gains `bonus_used`, `chained_move`, and `pay_the_price`, observed from the events; the Markdown report gains an "Engine events" section with new NPCs extracted from narration, the bonuses, chained moves, and prices paid with their rows, and the Director's tool rounds.

Tests: the capture keeps only the configured prefixes (with a real logger, since the test suite stubs the engine's logging module), and the smoke test checks that the narration is in the session log.

Quality gate: 1405 tests green, twenty-nine project-rule scans clean, coverage 89.69%, ruff check and ruff format clean, mypy --strict clean on 108 source files. Save format unchanged.

## [2026.09.24.36] — 2026-09-24

Every role runs on OpenAI's GPT-6 Luna, the narrator included.

The narrator cluster moves from Claude Opus 5.5 at Anthropic to GPT-6 Luna at OpenAI, at reasoning effort `none`, without the Anthropic-only `cache_control` and `output_config`. Opus narrated best and told failure most honestly, but at roughly four times the time and many times the cost per turn it did not fit a setup where everything else runs on GPT-6 Luna. On the ten test situations with two blind judges GPT-6 Luna scored 6.40 against Opus's 6.88, level with Sonnet 5, narrated the failed leap as a failure in two of three attempts where Haiku managed none, and answered in about four seconds; its narrations are shorter and plainer. The Anthropic provider stays configured, unused, so any cluster can move back by naming it. The startup check confirms the single model.

Quality gate: configuration and documentation only; the startup check passes.

## [2026.09.24.35] — 2026-09-24

Elvira's judge no longer loses verdicts to reasoning.

The judge called GPT-6 Luna without a reasoning setting, so the model reasoned at its default effort, and on some turns the reasoning used the whole 800-token budget and left an empty answer ("no verdict: JSONDecodeError"), seen in the first turns of a long run. The judge now has its own `max_tokens` (3000) and `extra_body` (`reasoning_effort: low`) in `tests/elvira/elvira_config.yaml`, like the player's `bot_extra_body`, and `judge_turn` takes the judge configuration instead of a bare model name. Verified live: two audits of a failed leap narrated as a success both returned verdicts, result integrity 1, overall capped at 4, naming the contradiction.

Quality gate: Elvira and project-rule tests green, ruff check and ruff format clean; engine unchanged.

## [2026.09.24.34] — 2026-09-24

Classic Ironsworn marks its own lasting harm.

Classic Endure Harm and Endure Stress marked Starforged's lasting impacts, permanently harmed and traumatized, where Ironsworn names maimed and corrupted. `engine/impacts.yaml` gains `maimed` and `corrupted` (permanent) and `encumbered` (a classic condition, not blocking recovery), and the classic overrides in `engine/move_outcomes.yaml` pair wounded with maimed and shaken with corrupted. The shared description of `cursed`, which only spoke of a vessel, now fits a character too. Still borrowed from Starforged, recorded in ARCHITECTURE.md: wounded and shaken block recovery.

Tests: at 0 health or spirit with the first impact already marked, a miss marks the lasting harm of each rulebook, four cases.

Quality gate: 1404 tests green, twenty-nine project-rule scans clean, coverage 89.69%, ruff check and ruff format clean, mypy --strict clean on 108 source files. Save format unchanged.

## [2026.09.24.33] — 2026-09-24

Assets and connections give their bonuses on rolls (roadmap R.1).

Until now assets did nothing mechanically: the game stored only their ids, never which abilities were enabled, an upgrade cost experience without enabling anything, and the Brain never saw the assets.

Abilities. `GameState.asset_abilities` records which abilities of each asset are enabled (default empty, filled from the Datasworn defaults on first use, so existing saves load). New `mechanics/assets.py`: asset data lookup through the setting chain, the enabled abilities, and `enable_next_ability`, which `advance_asset` now calls on an upgrade, in order, where the player would choose.

Bonuses. New `mechanics/bonuses.py` collects the roll bonuses: every enabled ability whose text grants an add (95 abilities in Starforged, 137 in classic Ironsworn carry one), and every active connection's aid (add +1 and +1 momentum on a hit, from the Make a Connection rule, configured in the new `engine/roll_bonuses.yaml`). The Brain message gains a `<bonuses>` block listing them by id with their condition, the Brain output schema gains `bonus_id`, and `prompts/brain.yaml` gains one rule: name a bonus only when the action clearly meets its condition, exactly as written, never invented. The engine checks the id against the offered bonuses, ignores an unknown one with a warning, adds the bonus to the action roll with any banked next-move bonus, and grants momentum on a hit where the rule text ties it to the same add. Combat Bot's "add +1 on Strike; if you Clash, take +1 momentum" therefore gives the add without the momentum.

Verified live with GPT-6 Luna as Brain: "I strike the raider with my combat bot fighting at my side" chose the Combat Bot bonus, and "I study the old star chart" chose none.

Tests: new `tests/test_roll_bonuses.py` (an enabled ability becomes an option, a disabled one only after an upgrade, a connection offers its aid, an unknown choice is ignored, a chosen bonus adds to the roll and grants momentum only on a hit, momentum tied to another move is not granted, and saves without ability states load).

Quality gate: 1400 tests green, twenty-nine project-rule scans clean, coverage 89.68%, ruff check and ruff format clean, mypy --strict clean on 108 source files. Save format: one new field with a default; older saves load.

## [2026.09.24.32] — 2026-09-24

Every "with a match" clause in the rules is now modelled, including oracle moves as chained moves and a connection's rank raise.

Oracle moves as chained moves. Explore a Waypoint on a strong hit with a match now makes Make a Discovery, and on a miss with a match makes Confront Chaos instead of paying the price, as the rules offer. Both are moves without a roll: they roll on their own table. `engine/move_outcomes.yaml` gains `oracle_moves`, naming each oracle move's table, number of rolls, and legacy reward; `game/finalization.py` → `_chain_oracle_move` rolls the table, gives the result to the narrator on the "follow-up move" line, and marks the legacy ticks (Make a Discovery 2 discoveries ticks, Confront Chaos 1 per aspect). Two fixed choices, recorded in ARCHITECTURE.md: the ticks are marked at once, where the rules mark them when the discovery or aspect is first engaged, and Confront Chaos takes one aspect where the player may choose up to three.

Rank raise. Develop Your Relationship on a strong hit with a match may raise the connection's rank; a new move effect `raise_connection_rank` raises it one step, up to epic. The connection lookup shared with the bond effect moves into `mechanics/move_effects.py` → `_connection_track`, and stripping Datasworn link markup into `strip_datasworn_links`, used by Pay the Price and the oracle chain.

The known-gap list for match clauses in `tests/test_rules_conformance.py` is now empty. New tests: both Explore a Waypoint chains with their legacy ticks and without the price on the miss, and the rank raise including epic as the ceiling.

Quality gate: 1392 tests green, twenty-nine project-rule scans clean, coverage 89.66%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.31] — 2026-09-24

Moves that say "make another move" now make it, in the same turn.

Where an outcome's rule text sends the player to another move, the engine now rolls that move at once. `engine/move_outcomes.yaml` gains the effect `chain_move <move>`, recorded on the outcome as `chained_move`; `game/finalization.py` → `_chain_move` then rolls the chained move: with the best stat its Datasworn roll options allow, or, for a connection move rolled by rank, with the value of the target NPC's connection rank. A banked next-move bonus is spent on it, as it is the next move. Its outcome is resolved, its consequences join the first move's under a "follow-up move" line for the narrator (`ai_text.yaml` → `consequence_labels.chained_move`), and a legacy reward it grants carries over. Without a value to roll with, for example no connection with the NPC, the chain is skipped with a warning.

Test Your Relationship is the first user: on a strong or weak hit the rules say Develop Your Relationship, which replaces the engine's earlier "+1 bond" and then rolls with the connection's rank, marking 2 bonds legacy ticks on its own strong hit. Explore a Waypoint's match clauses stay open: their targets, Make a Discovery and Confront Chaos, are oracle moves without a roll.

Tests: a chained Develop Your Relationship with fixed dice reaching its 2 legacy ticks, and a chain skipped without a connection. `tests/test_models.py` expected connection progress from Test Your Relationship itself and now expects the chained move instead.

Quality gate: 1388 tests green, twenty-nine project-rule scans clean, coverage 89.63%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.30] — 2026-09-24

Outcomes on a match follow Starforged (roadmap R.3).

The Datasworn move texts hold seven "on a strong hit with a match" or "on a miss with a match" clauses, all in Starforged; classic Ironsworn has none. The engine ignored all of them beyond the narrator's twist. The four mechanical ones are now modelled: `engine/move_outcomes.yaml` accepts optional `strong_hit_match` and `miss_match` entries, which replace the plain outcome on a match because the rule text describes the whole result there, and `mechanics/move_outcome.py` → `resolve_move_outcome` takes `match` from the roll (passed by `game/finalization.py`). Scene challenge Face Danger now marks progress twice on a strong hit with a match and fills two segments and pays the price on a miss with a match; scene challenge Secure an Advantage takes both benefits and marks progress on a strong hit with a match and fills two segments and pays the price on a miss with a match.

The other three are pinned as known gaps in `tests/test_rules_conformance.py`, which fails if a new unmodelled match clause appears: Explore a Waypoint's "you may instead Make a Discovery" and "Confront Chaos" chain a second move, the same open design question as Test Your Relationship, and Develop Your Relationship's optional rank raise has no effect yet.

Tests: the match-clause check, and six scene challenge cases with and without a match.

Quality gate: 1386 tests green, twenty-nine project-rule scans clean, coverage 89.69%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.29] — 2026-09-24

Pay the Price follows the rulebooks (roadmap R.3).

Pay the Price. The engine answered every Pay the Price with one of eight invented lines inherited from EdgeTales ("Something valuable breaks beyond easy repair", "Someone saw what {player} did") and applied no mechanical cost. It now rolls the setting's own table from the Datasworn data (`moves/pay_the_price`: twenty rows in Starforged, sixteen in classic Ironsworn). `engine/pay_the_price.yaml` becomes its configuration: the table path, the roll-twice and roll-again rows with their extra rolls and a depth limit of two, and the rows with a mechanical cost; a row saying the character is harmed, stressed, or wastes resources costs 1 health, spirit, or supply, the smallest suffer amount, recorded as a fixed choice. `mechanics/move_effects.py` → `pay_the_price` rolls, strips Datasworn link markup for the narrator, and applies those costs; the move effect and the suffer handler both use it.

Automated outcome check. A second pass over the Datasworn outcome texts, for suffer moves, Pay the Price, and progress, found five cases. One is a real divergence, now fixed with a classic override: Ironsworn's Enter the Fray on a miss also pays the price. Three are fixed choices where the player would pick a cost, recorded in ARCHITECTURE.md. One is a bonus on a strong hit with a match, which the engine does not model, recorded as open in roadmap R.3.

Tests: the price comes from the official table in both settings, a harmed row costs health, a roll-twice row adds two results with their costs, and Enter the Fray pays on a miss only in classic. `tests/test_move_outcome.py` checked the invented lines; one test now checks the official table and the other, which checked the player-name substitution in those lines, is removed with them.

Quality gate: 1379 tests green, twenty-nine project-rule scans clean, coverage 89.71%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; `engine/pay_the_price.yaml` changes from a list of lines to a configuration block.

## [2026.09.24.28] — 2026-09-24

Turning points follow the Adventure Crafter (roadmap R.8, now complete).

The rulebook text, found in a public copy and in a published roller, settles the open question from 2026.09.24.27: every turning point rolls five times on the plot point table; a None leaves that slot empty, at most three None results are allowed, and a fourth is disregarded and rolled again, so every turning point has 2 to 5 real plot points. And a Conclusion on a new plotline, or on one already concluding, counts as None.

`mechanics/adventure_crafter.py` → `roll_turning_point` drew a random count of 2 to 5 plot points and counted None as one of them, so a turning point could end with no real plot point at all, and a Conclusion on a brand-new plotline flipped it to its conclusion immediately. It now fills five slots with at most three None, and rolling one plot point moves into `_roll_plot_point`, which turns such a Conclusion into None. The limits come from `turning_point_rules` in `data/adventure_crafter.json`. `ai/blueprint_voicing.py` no longer passes None slots to the voicing model as turning-point beats.

Tests: five slots with at most three None over 200 seeds, a scripted fourth None that is rerolled, and a Conclusion on a new plotline counted as None. `tests/test_adventure_crafter.py` asserted that a Conclusion flips a brand-new plotline, which the rulebook forbids; it now flips an advancing plotline.

Quality gate: 1374 tests green, twenty-nine project-rule scans clean, coverage 89.68%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.27] — 2026-09-24

The Adventure Crafter's tables are checked and pinned (roadmap R.8).

Checked and conform: for each of the five themes the plot point table covers 1 to 100 without gaps or overlaps, as does the meta plot point table; Conclusion sits at 1 to 8 and None at 9 to 24 on every theme; the character and plotline lists have 25 lines of 4 percent each. Turning-point assembly follows the rules summarised in `data/adventure_crafter.json`. Two new tests in `tests/test_rules_conformance.py` pin the tables.

Recorded as an open question in roadmap R.8, because it needs the rulebook text: the engine draws 2 to 5 plot points and counts a None as an empty slot, so a turning point can end up with no real plot point; whether None is skipped or rerolled is not decided here.

No engine code changed.

Quality gate: 1371 tests green, twenty-nine project-rule scans clean, coverage 89.66%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.26] — 2026-09-24

Rules conformance for Mythic's lists and meaning tables, the Adventure Crafter's theme priority, and Blades clock sizes (roadmap R.7, R.8, R.9).

Clock sizes. Blades in the Dark clocks have 4, 6, or 8 segments. Clocks the engine makes itself already used 6, but clocks from the opening setup took whatever segment count the model named. `engine/clocks.yaml` gains `allowed_segments` (4, 6, 8), and `game/setup_common.py` → `conform_clock_segments` snaps a requested count to the nearest allowed size, the larger on a tie, logs the change, and caps the filled segments at the new size.

Checked and conform, now pinned in `tests/test_rules_conformance.py`: Mythic's meaning tables have the 2e shape (verbs and subjects, adverbs and adjectives, 100 each, and 45 element tables of 100), a thread or character is held on a list at most three times, and an empty list falls back to current context; the Adventure Crafter's theme priority maps a d10 to the first theme on 1 to 4, the second on 5 to 7, the third on 8 and 9, and alternates the fourth and fifth on a 10. The individual table words were not checked against the books.

Still open under R.8: turning-point assembly, the plot point tables per theme, and the character and plotline lists.

Quality gate: 1369 tests green, twenty-nine project-rule scans clean, coverage 89.69%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; `engine/clocks.yaml` gains the required key `allowed_segments`.

## [2026.09.24.25] — 2026-09-24

Legacy tracks, experience, and connections follow Starforged (roadmap R.4).

Checked against the Starforged Datasworn texts. Legacy rewards per rank (1 tick to 3 boxes) and 2 experience per filled box already conformed. Four divergences are fixed:

- Make a Connection gave +1 momentum and a mark of connection progress on a hit. The rules create the connection and nothing more; a strong hit keeps the engine's disposition shift, now recorded as an engine addition.
- Develop Your Relationship rewarded the bonds legacy track by the connection's rank on a strong hit. The rules mark a fixed 2 ticks, via a new effect `legacy_ticks <track> <ticks>`.
- Fulfill Your Vow gave the full legacy reward on a weak hit. The full reward requires swearing a new vow, which the engine cannot know at that point, so a weak hit now rewards one rank lower (a troublesome vow earns nothing), via a new effect `legacy_reward_lower <track>` and `mechanics/legacy.py` → `shifted_rank`.
- A full legacy track stopped at 40 ticks and earned nothing more. It now clears and keeps counting, at `legacy.xp_per_box_after_clear` (1) experience per box, and remembers its clears in `ProgressTrack.completions` (default 0; saves load unchanged). `mark_legacy` now delegates to `mark_legacy_ticks`.

The automated momentum comparison no longer counts a conditional future bonus ("whenever your connection aids you... take +1 momentum") as an immediate gain; that loophole had let Make a Connection pass. `tests/test_legacy.py` asserted the old cap and now asserts the clear. New tests: Fulfill Your Vow per rank, Develop Your Relationship's 2 ticks, Make a Connection without momentum, and a full track clearing into single-experience boxes.

Recorded as open in roadmap R.4: Test Your Relationship (its hits say "Develop Your Relationship", a second move the engine does not chain) and a connection's aid bonus. Recorded in ARCHITECTURE.md: classic Ironsworn earns experience through legacy tracks rather than directly.

Quality gate: 1354 tests green, twenty-nine project-rule scans clean, coverage 89.67%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format: one new field with a default; older saves load.

## [2026.09.24.24] — 2026-09-24

Move outcomes can differ per setting, and Endure Harm and Endure Stress follow each rulebook (roadmap R.1 and R.3).

Per-setting overrides. `engine/move_outcomes.yaml` gains `move_outcome_overrides`, keyed by setting; `mechanics/move_outcome.py` → `resolve_move_outcome` uses a move's override for the current setting before the shared table. The shared table follows Starforged; classic Ironsworn now gets its own Secure an Advantage (strong hit +2 momentum as a fixed choice, weak hit +1, which Ironsworn gives instead of Starforged's +2), Endure Harm, and Endure Stress.

Endure Harm and Endure Stress. The suffer handler takes three new required parameters: what shaking it off costs in momentum, whether a weak hit offers the momentum-for-recovery exchange, and whether recovery is allowed from 0. Starforged: free recovery on a strong hit, the exchange on a weak hit, an additional -1 or -2 momentum on a miss, all as before, except that the weak-hit exchange no longer charges momentum at full health, where it recovered nothing. Classic Ironsworn: shaking it off costs 1 momentum and needs the track above 0, a weak hit presses on, and a miss costs 1 momentum without extra harm, as the Datasworn texts say. The handler is split into small functions (`_can_recover`, `_recover`, `_suffer_strong_hit`, `_suffer_weak_hit`).

Still borrowed from Starforged in the classic setting, recorded in ARCHITECTURE.md: the lasting-harm names (permanently harmed and traumatized for maimed and corrupted) and wounded or shaken blocking recovery.

Tests: nine Endure Harm cases across both rulebooks and all three results, including full health and 0 health; Secure an Advantage per setting; the momentum comparison now reads the outcome that applies per setting, leaving Draw the Circle's boast as the only recorded momentum divergence. Two handler tests built parameter dicts for the old contract and gain the three new keys.

Quality gate: 1348 tests green, twenty-nine project-rule scans clean, coverage 89.63%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.23] — 2026-09-24

"Add +1 on your next move" now happens. The move effect `next_move_bonus` (Starforged's Secure an Advantage on a strong hit or as a weak-hit choice, and similar outcomes) was announced to the narrator as a consequence but never reached a roll: `mechanics/move_effects.py` stored it on a result object nobody read.

The bonus is now banked on the character as `Resources.next_move_bonus` (default 0, so existing saves load unchanged) and added to the next action roll, which spends it; progress rolls neither use nor spend it, as the rules say ("not a progress move"). `mechanics/consequences.py` → `roll_action` takes the adds as a required argument, and they still count when negative momentum cancels the action die. The correction re-roll uses and spends the bonus the same way. This gives the action roll the adds mechanism that asset bonuses will need (roadmap R.1).

The roll log line moves into `game/turn.py` → `_log_action_roll`; it shows the adds, and it no longer labels a die cancelled by negative momentum as a cap, which the log line from 2026.09.24.21 did.

Tests: adds raise the action score, adds still count with a cancelled die, the effect is banked and spent by the next action roll, and a save without the new field still loads.

Quality gate: 1337 tests green, twenty-nine project-rule scans clean, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format: one new field with a default; older saves load.

## [2026.09.24.22] — 2026-09-24

Rules conformance, second pass: momentum per move outcome and Mythic (roadmap section R), with a new conformance test file and a documented list of deliberate divergences.

Momentum per outcome. An automated comparison reads every move outcome text in the Datasworn data for Starforged and classic Ironsworn and compares each unconditional momentum gain ("take +2 momentum") with `engine/move_outcomes.yaml`. Of 183 outcomes checked, every one matches except two, both now recorded: the table is shared by Ironsworn and Starforged and follows Starforged where they differ (classic Secure an Advantage, weak hit, gives +2 instead of Ironsworn's +1), and Draw the Circle grants its weak-hit momentum without modelling the boast. Outcomes where the player chooses are not covered by the automated check and stay open under R.3. Also recorded under R.1: the move effect `next_move_bonus` ("add +1 on your next move") is announced to the narrator but never added to the next roll.

Mythic. Checked and conform: the fate check (odds and chaos modifiers, yes at 11 or more, exceptional yes 18 to 20, exceptional no 2 to 4, random event on doubles within the chaos factor), the fate chart (Mythic 2e values and exceptional thresholds in all 81 cells), the scene test (expected above the chaos factor or on a 10, otherwise odd altered and even interrupted), the chaos factor's start and range, and the event focus table. The chaos factor moves per turn from the roll instead of per scene from control, recorded as a deliberate divergence.

New `tests/test_rules_conformance.py` (14 tests) pins all of this: the momentum comparison fails on any divergence beyond the two recorded ones. New ARCHITECTURE.md section "Deliberate divergences from the source rulebooks" lists the four known exceptions (chaos per turn, shared outcome table, boasts, a fate-chart 100 counting as doubles).

No engine code changed in this pass.

Quality gate: 1333 tests green, twenty-nine project-rule scans clean, coverage 89.66%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.21] — 2026-09-24

Rules conformance, first pass over Ironsworn (roadmap section R), plus two Elvira fixes.

Negative momentum. Ironsworn and Starforged cancel the action die when momentum is negative and its absolute value equals the die: at momentum -3 a rolled 3 counts as 0, and the action score is the stat alone. The engine never did this. `mechanics/consequences.py` → `roll_action` now takes the current momentum (required argument; the turn and the correction re-roll pass it), and the roll log line notes a cancelled die. Three new tests fix the dice and check a matching negative momentum, a non-matching one, and positive momentum.

Checked and conform: momentum values (start +2, maximum +10, floor -6, reset never below 0), momentum burn (miss or weak hit only, positive momentum only, never on progress rolls, reset afterwards, a match stays a match), and progress ticks per rank on 40-tick tracks. Recorded as open in roadmap R: adds from assets and moves are not applied at all, the gain and loss per move outcome, suffer moves and impacts, legacy tracks, and bonds.

Elvira: Director tokens now count. The engine drains the token log at the start of each turn and Elvira records a turn's tokens before the Director runs, so Director calls were drained unseen; Elvira now adds them right after the Director run. Metadata-extraction tokens were missing for a different reason, fixed in 2026.09.24.20: the extraction itself was failing.

Elvira: calibrated judge. With Haiku as judge nearly every turn scored 10; with GPT-6 Luna ordinary scene texture was marked as unprompted invention. The rubric now anchors each score (5 no fault, 4 one minor fault, 3 one clear fault, 2 several or one serious, 1 violated outright), states that sensory detail and minor characters a scene naturally introduces are not faults, reserves 9 and 10 overall for turns with every criterion at 4 or 5, and caps overall at 4 when result integrity is 1 or 2.

Quality gate: 1319 tests green, twenty-nine project-rule scans clean, coverage 89.63%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.20] — 2026-09-24

Fixes a regression introduced in 2026.09.24.9: two AI calls could not be routed, so since that release the narrator-metadata extraction failed after every narration and the opening-setup extraction failed at the start of every new game, both silently.

The routing provider picks the provider by `AICallSpec.log_role`, on the assumption that the label is the call's role name. Two calls used a different label: the metadata extraction was labelled `metadata` (role `narrator_metadata`) and the opening setup `narrator_retry` (role `opening_setup`). Routing raised "Role 'metadata' has no cluster assignment", and both calls catch AI failures by design (AI-call carve-out), so the game went on without them: new NPCs were never registered, and renames, details, deaths, and lore updates from narration were lost, as was the structured opening setup. The mock-provider tests could not see it, because they hand the pipeline a provider directly and never go through routing. Elvira found it: with its judge no longer a Claude model, it flagged a narration that introduced an NPC the game did not know, and the coverage report showed no NPC introductions.

Both labels now carry their role names. New project-rule scan (twenty-nine): every `AICallSpec` must set `log_role` to a role in `config.yaml` → `ai.role_cluster`, and where the model comes from `model_for_role(X)`, X must be that same role. On the previous `ai/narrator.py` the scan reports exactly the two broken calls.

Quality gate: 1316 tests green, twenty-nine project-rule scans clean, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; saves from since 2026.09.24.9 simply lack the NPCs those turns should have registered.

## [2026.09.24.19] — 2026-09-24

The narrator stays on Claude Opus 5.5; every other role moves to OpenAI's GPT-6 Luna, a second provider next to Anthropic.

Configuration. `config.yaml` gains an `openai` provider (`type: openai_compatible`, OpenAI's default endpoint, `OPENAI_API_KEY`, 120-second timeout). The creative cluster (Director, blueprint voicing, chapter summary, recap) runs GPT-6 Luna at reasoning effort `low`; classification, judgment, and extraction run it at `none`. The OpenAI clusters carry no `cache_control`, which is an Anthropic parameter; OpenAI caches automatically. Measured beforehand on the ten test situations with the same two blind judges: GPT-6 Luna 6.40 out of 10 against Haiku's 6.10, the failed leap narrated as a failure in two of three attempts (Haiku in none), 3.6 seconds and about three cents per hundred calls. All eight engine schemas pass OpenAI's strict structured outputs, checked statically (every property required) and live.

Elvira's player and judge move to GPT-6 Luna as well; the player gets a required `bot_extra_body` (`reasoning_effort: none`) in `elvira_config.yaml`, because GPT-6 Luna rejects a temperature other than 1 while it reasons. The judge is no longer a Claude model scoring Claude's narration, and it scores more critically.

Found by switching models, in the game itself. The blueprint voicing prompt said "per ending seed" and "per revelation seed", while the engine requires exactly `possible_endings_per_blueprint` and `revelations_per_blueprint` (three each) and a new game often has a single ending seed. Haiku padded the list on its own; GPT-6 Luna followed the prompt and returned one ending, so every new game failed with "voicing returned 1 endings, expected 3". The voicing user message now states `required_counts` (acts, revelations, possible endings), the prompt asks for exactly those counts, basing entries on the seeds in order and resolving the same central conflict with a different type when seeds run out, and `call_blueprint_voicing` checks the counts after parsing and asks again, up to the cluster's retries, before giving up the way it already did on AI failure. Verified live: the first voicing attempt returned three acts, three revelations, and three endings. New test: a reply with too few endings triggers a second call.

Quality gate: 1316 tests green, twenty-eight project-rule scans clean, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; the startup check confirms both providers.

## [2026.09.24.18] — 2026-09-24

Every role except the narrator runs on Claude Haiku 4.5: the creative cluster (Director, blueprint voicing, chapter summary, recap) moves from Claude Sonnet 5 to Haiku. The narrator stays on Claude Opus 5.5 at effort low.

Measured on the same ten situations, three attempts each, with the same two blind judges (GPT-6 Sol and Claude Sonnet 5): Opus 5.5 low scored 6.88 out of 10 at 13.2 seconds per narration, Sonnet 5 low 6.42 at 8.7 seconds, Haiku 4.5 6.10 at 5.2 seconds. Overall the gap is modest, but it concentrates in result integrity (Opus 4.5, Sonnet 4.4, Haiku 3.8 out of 5): in all three attempts at a failed leap across a gorge, Haiku narrated the leap as a success. Since the action roll now misses a third of the time, the narrator stays on the model that tells failure honestly.

Verified live before switching: with every cluster on Haiku in memory, a full turn took 9.4 seconds with the first sentence after 4.2, and the deferred Director made four tool calls in two rounds, used the `known_npcs` list from 2026.09.24.16 to correct a guessed NPC id, and applied its guidance. The live Haiku narration of a miss was a genuine failure but invented backstory for the player character.

Quality gate: config and documentation only; the config and project-rule tests pass and the startup check confirms every configured model at Anthropic.

## [2026.09.24.17] — 2026-09-24

The action roll follows Ironsworn: one d6 plus the stat, capped at 10, against two d10s. `mechanics/consequences.py` → `roll_action` rolled two d6 plus the stat. ARCHITECTURE.md described it as "2d6+stat", but it was never recorded as a deliberate divergence and appears to have been inherited; Elvira's roll display ("Action 1+3=7") exposed it. The difference is large. At stat 2 the chance of a strong hit falls from 58% to 23%, a weak hit rises from 32% to 44%, and a miss rises from 10% to 33%, exactly the Ironsworn odds. Expect more misses, more consequences, and more momentum burns; engine values tuned under the old odds may deserve a second look, which Elvira's coverage and audit now make visible.

`RollResult` keeps its `d2` field so existing saves still load; it is now 0 for every roll, as it already was for progress rolls, and can go with the next deliberate save-format break. The roll log line and the correction analysis show the action die only. Mythic's fate check in `mechanics/fate.py` keeps its two d10s, which is correct for Mythic 2e.

Decision recorded as a principle with a checklist in roadmap section R: every rule taken from Ironsworn/Starforged, Mythic 2e, the Adventure Crafter, or Blades in the Dark works as its source describes, or is listed as a deliberate divergence.

Tests: the existing action-roll test now asserts `action_score == min(d1 + stat, 10)` and `d2 == 0`; a new test rolls 500 times at stat 2 and checks that the score is always the die plus the stat, peaking at 8. No seeded test depended on the old second die.

Quality gate: 1315 tests green, twenty-eight project-rule scans clean, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.16] — 2026-09-24

Elvira tests far more of the game on her own, and in doing so found two bugs in the game itself.

Found in the game. `web/serializers.py` → `highlight_dialog` ran three passes over the narration, and the straight-quote pass matched the `class="dialog"` attribute the curly-quote pass had just inserted, so every narration with curly-quoted dialog reached the browser as broken markup, showing text such as `dialog">` that NVDA read aloud. It now runs one combined pass over all three quote styles, so no pass ever sees inserted markup; a new test in `tests/test_web.py` fails on the previous code. And the Director's `query_npc` tool answered an unknown id with a bare "not found", so the Director kept guessing ids (`npc_2`, `npc_3`); the error now lists the known active and background NPCs, so the next tool round can correct itself (test in `tests/test_tools.py`).

Found in Elvira. WebSocket mode could never start: `_start_server` waited for the server with a blocking `urllib` request inside the event loop that runs the server, so the server could not answer and every attempt timed out. It now waits on uvicorn's own `started` flag.

New in both modes: streaming checks per turn (time to first sentence, sentence count, and whether the streamed text equals the final text; a complete stream that differs is reported as a problem), and a Markdown report per run next to the JSON log, verdict first, with a heading per section for screen-reader navigation.

New in direct mode: a blind narration audit per turn by Claude Haiku 4.5 (`judge` in `elvira_config.yaml`, rubric in `elvira_prompts.yaml`; a failed audit is recorded, never fatal), a save/load round trip after every save that compares the whole game state, succession on game over (`session.succession_on_game_over`), a coverage tracker with steering towards dialog, combat, and travel in the second half of a run, and an estimated cost per role from a price table in `elvira_config.yaml`.

New in WebSocket mode: narration sentences are recorded as they arrive, and after the first turn Elvira sends the status, tracks, threats, and recap queries and reports empty answers or errors.

Tests: `tests/test_elvira_smoke.py` now also checks the report, the coverage, a clean save round trip, and complete streams, and gains a WebSocket test that starts the real server on a free port against the mock provider. In direct mode the save round trip found no differences.

Quality gate: 1314 tests green, twenty-eight project-rule scans clean, coverage 89.65%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.15] — 2026-09-24

Elvira runs again, and the normal test gate now notices when it stops running.

Three breakages, all found by running Elvira for the first time since the provider changes of this day. The session banner read `cfg().ai.provider`, which 2026.09.24.9 replaced with per-role providers, so every run crashed before the first turn; the banner now shows provider and model for the narrator, Brain, and Director. Output redirected to a file used Windows' cp1252 encoding, so any line with a character such as ≤ or → failed; `elvira.py` now switches stdout and stderr to UTF-8. And `SessionLog.to_diagnostic_dict` read a `character` field that `SessionLog` never had, so every run crashed at the end while writing its report; the field exists now and holds the character's name, concept, and setting.

New `tests/test_elvira_smoke.py` runs Elvira's real `run_session` for three turns, including a correction turn, against the mock provider from the integration tests, with users and run logs in a temporary directory. It fails on the previous `runner.py` with the banner crash and caught the missing `character` field on its first run. Elvira's WebSocket mode is not covered yet.

Seen in the live run, not fixed here: the Director calls `query_npc` with guessed ids (`npc_2`, `npc_3`) that do not exist.

Quality gate: 1311 tests green, twenty-eight project-rule scans clean, coverage 88.92%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged.

## [2026.09.24.14] — 2026-09-24

The two provider SDKs are now used as intended, and OpenAI's own models work.

Double retries. Both SDKs retry failed requests twice on their own, and `create_with_retry` retried on top of that (three attempts in the current config), so a persistent overload could take up to twelve attempts, and Straightjacket's own loop ignored the server's `Retry-After`. Both adapters now create their SDK client with `max_retries=0`; `create_with_retry` is the only retry layer and honours `Retry-After`, capped by the new `retry.max_retry_after_seconds: 60` in `engine/retry.yaml`.

Timeouts. The SDKs wait up to ten minutes per attempt by default. Each provider in `config.yaml` now has a required `timeout_seconds` (120 for Anthropic), passed to the SDK client.

Refusals. `normalize_stop_reason` mapped every unknown stop reason to `complete`, so a refusal passed silently as ordinary narration. It now takes the truncation values as a tuple (Anthropic adds `model_context_window_exceeded`) and a refusal value (Anthropic `refusal`, OpenAI `content_filter`). `create_with_retry` retries a refusal like a transient error and logs an error when it persists; `stream_with_retry` falls back to a normal call when a stream ends in a refusal.

OpenAI's own models. The OpenAI-compatible adapter sent `max_tokens`, which GPT-6 Luna and GPT-5.6 Luna reject ("Use 'max_completion_tokens' instead"), so the adapter only worked with third-party services. It now sends `max_completion_tokens`; verified live that Fireworks (GLM 5.2, Kimi K2.6) accepts it too.

Streaming bookkeeping. The streaming path added in 2026.09.24.12 skipped `post_process_response` and token logging, so streamed narrator calls were missing from the token log and from Elvira's cost figures. `stream_with_retry` now runs both, through a helper shared with `create_with_retry`.

Prompt caching. The narrator cluster caches for an hour (`cache_control: {type: ephemeral, ttl: "1h"}`): with a screen reader, hearing a narration, thinking, and typing often takes longer than the default five minutes. Verified live: 3970 tokens of the real narrator prompt written to the one-hour cache and read back. Also measured: Claude Haiku 4.5 caches a 9,000-token prompt but not the Brain's roughly 2,300 tokens, which is below its minimum, so `cache_control` on the Haiku clusters has no effect and costs nothing.

Considered and left out: strict tool definitions (two of the three Director tools have optional parameters with defaults, which strict mode forbids), token counting before sending, and the batch API (half price, but not for interactive play; useful for comparison runs).

Verified live through Straightjacket's own adapters: OpenAI GPT-6 Luna and Fireworks GLM 5.2 each pass plain text, the Brain schema, a Director tool call, and streaming. New `tests/test_retry_and_refusal.py` (refusal retried, persistent refusal returned, `Retry-After` honoured and capped, streaming refusal falls back) and refusal-mapping tests for both adapters; existing tests updated for the client arguments and `max_completion_tokens`.

Quality gate: 1310 tests green, twenty-eight project-rule scans clean, coverage 88.55%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; `config.yaml` gains the required key `timeout_seconds` per provider.

## [2026.09.24.13] — 2026-09-24

The narrator runs Claude Opus 5.5 at reasoning effort `low`: the narrator cluster's `extra_body` gains `output_config: {effort: low}`, which the Anthropic adapter merges into the request since 2026.09.24.11.

Based on the measurement recorded in roadmap Current state: default, `medium`, and `low`, each on ten situations three times with two blind judges, scored 6.85, 6.75, and 6.88 out of 10, no measurable quality difference, while `low` was about five seconds faster per narration and wrote a third fewer output tokens.

Verified live, which is also the first live run of sentence-level streaming against Anthropic: through `stream_with_retry` with the real config, the first sentence arrived after 8.7 seconds and the last after 15.9, all 21 sentences came through, the streamed text matched the final text exactly (so the client changes nothing at the end), and the text held no reasoning. Reasoning never reaches the narration on either path: non-streaming responses keep only text blocks, and streaming passes on only `text_delta` events. Reasoning tokens are still billed as output, which is why `low` saves money.

Quality gate: 1304 tests green, twenty-eight project-rule scans clean, coverage 88.59%, ruff and mypy --strict unaffected (config only). Save format unchanged.

## [2026.09.24.12] — 2026-09-24

Sentence-level streaming of narration (roadmap section S), so the screen reader starts reading after the first sentence instead of after the whole turn.

Both adapters gain `stream_message(spec, on_text)`. Anthropic streams through `messages.stream` and passes on text deltas only, never reasoning; OpenAI-compatible streams with `stream_options.include_usage`. The routing provider forwards it. `ai/provider_base.py` → `stream_with_retry` streams when the provider can and otherwise feeds the whole reply at once; if a stream fails it logs, marks the stream failed, and falls back to a normal call with retries.

New `ai/sentence_stream.py` → `SentenceStream` buffers streamed text until a sentence is complete, respecting closing quotes, paragraph breaks, and abbreviations, and cleans each sentence with the new `parser.py` → `clean_sentence` (the sentence-safe subset of the parser: role prefix on the first sentence, prompt tags, bracket labels, mechanic annotations, markdown). A hold marker (a tag, code fence, JSON, rule, or heading) stops the stream; sentences that end before the marker still go out. Abbreviations and hold markers live in `engine/parser.yaml`.

The stream travels from `web/handlers.py` through `process_turn`, `SceneContext`, and `narrate_scene` into `call_narrator`. The handler sends each sentence as a `narration_sentence` WebSocket message with the scene and location, and waits for all of them before the authoritative `narration` message, which now carries `stream_complete`. The client appends each sentence to the log region, puts the scene heading before the first one, and skips the later scene marker for the same scene. When the final text matches what was streamed it changes nothing; otherwise it replaces the text and announces only the part not yet heard. `server.stream_narration` in `config.yaml` switches it off. Openings, corrections, and momentum burns do not stream.

Tests: new `tests/test_sentence_stream.py` (sentence order across chunks, the last sentence on finish, abbreviations, closing quotes, paragraph breaks, hold markers, failure, the non-streaming path, the fallback), plus stream tests for both adapters that also check the parameters against the installed SDK. The hold-marker test caught a real bug on its first run: a chunk that held both a finished sentence and a marker dropped the sentence.

Not verified: how NVDA reads the streamed sentences and whether the silent replacement stays silent (user test), streaming through the web UI against Anthropic end to end, and Elvira in WebSocket mode.

Quality gate: 1304 tests green, twenty-eight project-rule scans clean, coverage 88.55%, ruff check and ruff format clean, mypy --strict clean on 106 source files. Save format unchanged; `config.yaml` gains the required key `server.stream_narration`.

## [2026.09.24.11] — 2026-09-24

All roles run on Claude, and the Anthropic adapter is fixed for the current Claude models. Before this release the adapter could not run them at all.

Decision: narrator Claude Opus 5.5, creative roles Claude Sonnet 5, classification, judgment, and extraction Claude Haiku 4.5, every cluster with prompt caching. Chosen after comparing twelve model configurations on real Straightjacket narrator prompts (ten situations, several attempts each, two blind judges from different model families, measured speed and cost). Recorded in roadmap Current state.

Sampling. Claude Opus 5.5 and Sonnet 5 reject `temperature` and `top_p` outright; Haiku 4.5 accepts only one of the two. Every cluster sent both, so every Claude call failed. `temperature` and `top_p` stay required cluster keys but may now be `null`, which means the parameter is not sent; `sampling_params` omits them.

Tool loop. `tools/handler.py::run_tool_loop` appends OpenAI-style messages (an assistant message with `tool_calls`, then role `tool` results), and the Anthropic adapter passed them through unchanged, which the Messages API rejects ("Unexpected role tool"). The Director's tool loop had therefore never worked on Anthropic. The adapter now converts them into `tool_use` and `tool_result` blocks, merging consecutive tool results into one user message. Verified live: a Director run on Sonnet 5 made four tool calls in two rounds and applied its guidance.

Cluster `extra_body` on Anthropic. It was ignored; the adapter now routes it by key: `cache_control` and `thinking` become typed parameters, `output_config` merges with the JSON-schema format (so a cluster can set Opus's `effort`), everything else goes into `extra_body` beside the sampling values. Prompt caching is on for every cluster through `cache_control: {type: ephemeral}`; verified live with the real narrator prompt: 3970 tokens written on the first call, read from cache on the second.

Usage. Anthropic reports cached input separately, so the token log showed a Director call as "2 in". Input tokens now include cache reads and writes, and `cache_read_tokens` reports the cached share. One existing test asserted the old two-key usage dict and is updated.

Thinking blocks (Opus 5.5 always reasons; `thinking.type: disabled` is refused) never reach the narration: only text blocks become `AIResponse.content`. That was already the case; a test now pins it.

Elvira's bot model moves to Claude Haiku 4.5, because the bot uses the brain role's provider.

Verified live against Anthropic: the startup check passes, a full turn through `process_turn` (Brain on Haiku, narrator on Opus, extraction on Haiku) takes about 30 seconds and produces clean narration without reasoning text, and the deferred Director completes with tools. New tests: thinking blocks excluded, tool-loop conversion, `extra_body` routing, cached usage, and `null` sampling in the config loader.

Quality gate: 1293 tests green, twenty-eight project-rule scans clean, coverage 88.48%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Save format unchanged; config.yaml changes shape only in allowing null sampling.

## [2026.09.24.10] — 2026-09-24

The `<result>` tag in every action-turn narrator prompt was closed with `</r>`. `prompt_action.py::_build_result_constraint` built all three variants (MISS, WEAK_HIT, STRONG_HIT) as `<result ...>...</r>`, so the one tag that tells the narrator what happened was malformed XML on every action turn. Models coped, but the prompt was not what it claimed to be. Found while capturing a real narrator prompt for model comparisons; all three now close with `</result>`.

New `tests/test_prompt_xml.py` runs real turns through `process_turn` with the mock provider, captures the narrator prompt, and parses the engine-built `<scene>` block as XML: for MISS, WEAK_HIT, and STRONG_HIT, and for a dialog turn. The action test fails on the previous code; the dialog scene was already well-formed. The check covers the structure the engine builds, not the `<task>` text after it, which deliberately names other tags in angle brackets (`<story_arc>`, `<director_guidance>`) as pointers for the model; rewriting those is a prompt change and would need an Elvira measurement first.

Quality gate: 1288 tests green, twenty-eight project-rule scans clean, coverage 88.42%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Save format unchanged.

## [2026.09.24.9] — 2026-09-24

Providers can be mixed per role, and startup now checks that every configured model still exists.

Background: Cerebras retired `zai-glm-4.7`, the narrator model, on 2026-08-17, and its public catalogue is down to `gpt-oss-120b` and `qwen-3.8-27b`. Nothing in Straightjacket noticed: the narrator call failed on every turn, and the AI-call carve-out turned that failure into an empty narration.

Per-role providers. `config.yaml` gains `ai.providers` (a name mapped to `type`, `api_base`, and `api_key_env`), every cluster names its `provider`, and the single `ai.provider`, `ai.api_base`, and `ai.api_key_env` keys are gone (the config format breaks; no migration). A cluster that names an undefined provider fails at load. `get_provider` returns a routing provider that sends each call to the provider of its role's cluster, keyed on `AICallSpec.log_role`; a call without a known role raises. `correction/analysis.py` was the one AI call that did not set `log_role`; it does now. Elvira's bot calls use the brain role's provider. Any OpenAI-compatible service works through `type: openai_compatible`, Anthropic through `type: anthropic`.

Startup check. `check_configured_models` asks every provider in use for its model list (new `list_models` on both adapters, behind a `ModelListingProvider` protocol) and raises with the missing model and what that provider does offer. `run.py` runs it before starting the server and exits with the message; Elvira runs it before a session. It replaces the old startup warning that only checked whether the API-key variable was set. With the current config it reports the retired narrator model, which is correct: choosing replacements is the user's pending decision (roadmap Current state).

Sentence-level streaming of narration ("half-streaming": stream from the provider, release whole sentences to the screen reader) is sketched as roadmap section S.

Tests: new `tests/test_api_client.py` (routing per role, unknown role, startup check passing and failing, missing API key, unknown provider type), config-loader tests for the provider fields, and `list_models` tests for both adapters.

Quality gate: 1286 tests green, twenty-eight project-rule scans clean, coverage 88.40%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Not verified against the live APIs.

## [2026.09.24.8] — 2026-09-24

Dependencies brought to their current major versions, and the Starlette test-client warning resolved.

`anthropic` 0.125 → 1.8 and `openai` 2.54 → 3.19; the ranges in `pyproject.toml` and `requirements.txt` move from `<1` and `<3` to `>=1.8,<2` and `>=3.19,<4`. Both SDKs moved their HTTP layer from `httpx` to `httpx2` in August 2026; Straightjacket passes no custom HTTP client, so that change needs no code. openai 3.x accepts every parameter the OpenAI-compatible adapter sends, unchanged. anthropic 1.x removed `temperature`, `top_p`, and `top_k` from the typed `messages.create` signature (passing them raises `TypeError`), while the Messages API still accepts them. The Anthropic adapter now sends them through `extra_body`, so cluster sampling settings keep applying, and a model that rejects them fails loudly at the API instead of being silently ignored.

The test extra swaps `httpx` for `httpx2`: Starlette 1.7's `TestClient` deprecates `httpx` in favour of `httpx2`. This removes the one warning the suite has shown since 2026.09.24.0, and `httpx` is no longer installed in the environment at all.

New in `tests/test_providers.py`: two tests check that every parameter each adapter sends appears in the signature of the installed SDK's create method. The adapter tests use fake clients, so without this check an SDK upgrade that removes a parameter would pass the suite and fail only against the real API, which is exactly the break anthropic 1.0 would have caused.

All other direct dependencies were already at their latest versions within their ranges (starlette 1.7.0, uvicorn 0.53.0, PyYAML 6.0.3, pytest 9.1.1, ruff 0.16.8, mypy 2.3.1).

Quality gate: 1276 tests green with no warnings, twenty-eight project-rule scans clean, coverage 88.24%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Not verified: a live call against either provider (needs an API key); the signature tests cover the shape of the request, not the response.

## [2026.09.24.7] — 2026-09-24

Documentation only: the open question in roadmap step 9 is decided. Fact resolution is triggered by the Brain, which flags the undetermined facts a player action depends on, chosen from a fixed yaml list of fact types; the engine derives the odds, resolves through fate, remembers the answer on the entity, and hands it to the narrator as a `<fact>` tag. The decision, its three conditions (yaml fact-type list that raises on unknown types, persisted facts that are reused rather than re-rolled, Brain prompt instructions with examples in the same commit), and the rejected alternatives are recorded in roadmap.md (Current state and step 9, including three new Definition of Done items). ARCHITECTURE.md "Engine-resolved fiction" gains one sentence on the decided trigger.

## [2026.09.24.6] — 2026-09-24

Rules and robustness fixes found by comparing with EdgeTales 0.9.67–0.9.96 (Lars). Ideas reimplemented, no code copied. Each fix comes with a test that fails on the previous code; for the momentum and Director fixes the old code already fails on the new signatures, the compel and dialog-agency tests fail on behaviour.

NPC agency ran only on action turns. `check_npc_agency` fires on scenes that are a multiple of `pacing.npc_agency_interval`, but only the action path called it, so whenever that scene was a dialog or oracle turn, agency was skipped for the whole interval. The dialog path now calls it too: agency actions reach the dialog prompt as `<npc_agency>` (the block moved into a shared `prompt_shared.py::_npc_agency_block` used by both prompts), fill results join the same-turn clock fills, and clock events reach scene finalization.

Director reflections were applied without checking the engine's selection. The prompt only offers NPCs that need a reflection or a profile and are active or background, but the answer was applied for any NPC id the AI returned, including deceased and lore NPCs, and a duplicate entry for the same NPC was applied twice (two reflection memories, two sets of updates). One shared `_reflection_eligible` now decides both sides, duplicates within one response are skipped, and `_process_npc_reflection` returns the resolved NPC id.

`compel` marked bond progress on a strong hit. Neither Ironsworn nor Starforged does that; a successful compel is transactional. `bond +1` removed from `adventure/compel` and `relationship/compel`.

Momentum reset could fall below zero. After a burn the reset is +2, reduced by one per impact; the rules put its minimum at 0, but the code floored it at the momentum floor (-6), so three or more impacts reset momentum to -1 or lower. New `momentum.reset_floor: 0` in `engine/momentum.yaml`, and `Resources.reset_momentum` takes `reset_floor`.

Checked and not a bug here: an NPC introduced and killed in the same scene. EdgeTales could not mark such an NPC dead because its extractor had no id to report; in Straightjacket a new NPC gets a seed memory for the current scene and `find_npc` resolves names, so the presence check accepts the death. The test stays as a regression guard.

Six larger ideas from the comparison are sketched in roadmap.md under "E — Ideas from the EdgeTales comparison": clock and threat pressure in narrative direction, NPC exit tracking, NPC-to-NPC dynamics, stale NPC retirement, a constrained Brain `target_npc`, and a narrator rule on NPC backstory.

One existing test, `test_compel_no_disposition_shift`, asserted that compel marks connection progress, which is exactly the behaviour this release removes. Per "Tests are not the spec" it is rewritten as `test_compel_strong_hit_marks_no_bond_and_no_disposition_shift`.

Quality gate: 1274 tests green, twenty-eight project-rule scans clean, coverage 88.05%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Save format unchanged.

## [2026.09.24.5] — 2026-09-24

mypy runs in strict mode. `mypy --strict` reported 398 errors; it now reports none, and `[tool.mypy]` in `pyproject.toml` says `strict = true` instead of listing six individual flags.

Explicit re-exports (131 errors). `models.py` and `engine_config.py` declare `__all__`. Seven imports that reached a name through a module that merely imported it now import from the defining module (`BrainResult` and `ClockFillResult` from `models`, `normalize_disposition` from `emotions_loader`), and `roll_progress` joins the `mechanics` public API.

Generic parameters (237 errors). Every bare `dict`, `list`, `set`, and `Callable` in annotations states its parameters: `dict[str, Any]`, `list[Any]`, `set[Any]`, `Callable[..., Any]`. mypy found no conflicts afterwards; every annotated dict does have string keys. Narrowing `Any` to concrete types stays audit work.

Any at the boundary (30 errors). Values that arrive as `Any` from yaml, JSON, `getattr`, or `dict[str, Any]` get their declared type where they enter typed code: an annotated first assignment, a declaration before a loop, or a typed local before the return. Behaviour is unchanged. Three spots needed more than that: `get_prompt` types its template as `str | None` until the unknown-prompt check, `resolve_time_progression` picks one key instead of returning from two annotated branches, and `call_blueprint_voicing` types the parsed voicing as `dict[str, Any]`.

The extra typed locals pushed coverage to 87.99%, and the floor from 2026.09.24.2 failed the gate as intended. Instead of lowering the floor, the new `tests/test_extract_title.py` covers the three untested branches of `datasworn/loader.py::extract_title` (dict title, string title, fallback) in seven cases.

Quality gate: 1267 tests green, twenty-eight project-rule scans clean, coverage 88.16%, ruff check and ruff format clean, mypy --strict clean on 105 source files. Save format unchanged.

## [2026.09.24.4] — 2026-09-24

Import layers become a rule, and the two dependencies that broke it are fixed at the root.

`game/tracks.py` moved to `mechanics/tracks.py`. `find_progress_track`, `complete_track`, `sync_combat_tracks`, and `roll_oracle_answer` depend only on the engine core, `datasworn/`, and `mechanics/legacy.py`: mechanics living one layer too high. `mechanics/threats.py` and `mechanics/clock_consequences.py` imported `complete_track` from `game/` through inline imports, one of them marked as a circular break; both now import it at module level from `.tracks`, and their two entries in the inline-import whitelist are gone. The four functions are exported through `mechanics/__init__.py`; all callers in `game/` and `correction/` and two test files were updated in the same commit.

New scan `_check_import_layers` (twenty-seven → twenty-eight). `datasworn/` and `db/` import only the engine core; `npc/` and `mechanics/` never import `ai/`, `tools/`, `game/`, `correction/`, or `web/`; `ai/`, `tools/`, and the engine core's top-level files never import `game/`, `correction/`, or `web/`; `game/` never imports `correction/` or `web/`; `correction/` never imports `web/`. Inline imports count. Apart from the two fixed imports, the rule describes the dependency graph exactly as it already was. ARCHITECTURE.md gains an "Import layers" Key Design Decision. The documentation-drift scan caught one stale mention of the old path in AUDIT.md during this change.

Quality gate: 1260 tests green, twenty-eight project-rule scans clean, coverage 88.08%, ruff check and ruff format clean, mypy clean on 105 source files. Save format unchanged.

## [2026.09.24.3] — 2026-09-24

Five more ruff rule families enabled: RUF, PERF, PT, PTH, and DTZ. The first run reported 104 findings. Ruff fixed 61 automatically (pytest parametrize and fixture style, unused unpacked variables, sorted `__all__`, collection literals); the rest were fixed by hand:

- `open()` replaced by `Path.open()` in ten places (PTH123), in line with the pathlib code standard.
- Timestamps are timezone-aware (DTZ005): the save file's `saved_at`, the user's `created`, and Elvira's session filenames use `datetime.now().astimezone()`. Save metadata now carries a UTC offset; saves stay loadable.
- Seven `pytest.raises(match=...)` patterns such as `outside 1..100` treated `.` as a regex wildcard (RUF043); they are now raw strings with escaped dots.
- `test_mark_unknown_track_raises` accepted any `ValueError`; it now matches the actual message (PT011).
- Two intentional en dashes in sentence-end checks are written as `\u2013`, so the intent is explicit (RUF001).
- A real bug (RUF006): Elvira's WebSocket runner started the uvicorn server with `asyncio.create_task` without keeping a reference, so the task could be garbage-collected mid-run. The task is now held in a module-level set until it finishes.

PERF401 (manual list comprehension, 18 findings) is deliberately ignored, with the reason in `pyproject.toml`: loops with conditions stay loops when they read clearer.

Quality gate: 1260 tests green, twenty-seven project-rule scans clean, coverage 88.03%, ruff check and ruff format clean, mypy clean on 105 source files.

## [2026.09.24.2] — 2026-09-24

Documentation drift becomes a test, the provider adapters get tests, and coverage gets a floor.

Four new project-rule scans (twenty-three → twenty-seven) turn the manual re-sync of 2026.09.24.0 into a mechanical check. `_check_doc_paths_exist`: every backticked path in README, ARCHITECTURE, SECURITY, ORIGINS, and AUDIT must exist in the repository; a small placeholder set covers the documented examples (`your_setting.yaml`, `provider_yourname.py`, Elvira's generated session files) and fails itself when a placeholder is no longer used. `_check_file_map_complete`: every source file appears in the ARCHITECTURE.md file map, and every file the map lists exists. `_check_ownership_symbols_exist`: every `file.py → symbol` and `file.py::symbol` reference in ARCHITECTURE.md names a symbol defined in that file. `_check_changelog_consistent`: the newest CHANGELOG entry matches the `pyproject.toml` version, versions strictly decrease, and no entry after a separator lacks its header.

The new scans found two real errors on their first run. ARCHITECTURE.md named `PROGRESS_RANKS` in `models_base.py`, which no longer exists; valid ranks are the keys of `engine/progress.yaml::track_types.default.ticks_per_mark`. And the 2026.05.08.0 entry added in 2026.09.24.0 sat above 2026.05.14.0 instead of between 2026.05.11.0 and 2026.05.06.3. Both fixed.

New `tests/test_providers.py`: the Anthropic and OpenAI-compatible adapters, at 0% coverage until now because every other test uses a mock provider, are tested against fake SDK clients. Eleven tests cover response mapping (text blocks, tool calls, stop reasons, token usage), request building (system-prompt placement, sampling parameters, JSON-schema format, tool conversion, `top_k` merged into `extra_body` without mutating the spec), omission of unset options, and `base_url` handling. Both adapters are now at 100%.

Coverage floor: `[tool.coverage.report] fail_under = 88` in `pyproject.toml` (current total 88.0%). The quality gate in ARCHITECTURE.md (Contributing) and roadmap.md (post-flight) now runs `pytest tests/ -q --cov`; the floor is raised when coverage rises and never lowered.

Quality gate: 1260 tests green, twenty-seven project-rule scans clean, coverage 88%, ruff check and ruff format clean, mypy clean on 105 source files. Save format unchanged.

## [2026.09.24.1] — 2026-09-24

Project-rule scans hardened: blind spots closed, three new scans (twenty → twenty-three), and the one real violation they exposed fixed.

Blind spots closed in `tests/test_project_rules.py`. The dataclass-default scan now covers `engine_config_dataclasses.py`, where the 88 config dataclasses have lived since 0.67.0; it used to scan only `engine_config.py`, which holds one, and it now recognises `@dataclasses.dataclass` as well. The broad-except scan also catches `except BaseException`, tuples that include `Exception` or `BaseException`, and `contextlib.suppress(Exception)`. The model-name scan now includes the active narrator model family (`glm`, `zai-`) and other common families; before, only Qwen, GPT, and Claude names were caught. The warning-suppression scan (`# type: ignore`, `# noqa`, `# pragma: no cover`) now covers `tests/` too; five trailing `# type: ignore` comments in tests had slipped through because the comment scan only sees full-line comments. The yaml-comment scan skips virtual environments and other non-project directories instead of walking every yaml file under the repository root. The ruff-format delivery gate runs ruff from the active interpreter (`sys.executable -m ruff`) instead of whichever `ruff` comes first on PATH, and `ruff` plus `mypy` are added to the `test` extras. All file reads specify UTF-8; the Windows default is cp1252.

Three new scans. `_check_no_stale_carve_out_entries`: every carve-out and whitelist entry must still point at an existing file or symbol, and every AI-call carve-out file must actually contain a broad except. It found `log_tokens` and `impact_config` in the orphan-symbol carve-out (neither exists) and `engine/ai/metadata.py` in the AI-call carve-out (nothing to carve out); all three removed. `_check_no_skip_or_xfail_in_tests`: a test that cannot run must fail, not disappear. One hit fixed: `tests/test_web.py` skipped instead of failing when no setting yamls were found. `_check_no_orphan_prompt_keys`: every top-level key in `prompts/*.yaml` must have a reader in `src/`, mirroring the engine-yaml orphan scan; currently clean over 74 keys.

The real violation. `web/serializers.py` sat in the AI-call carve-out although it makes no AI call, and its one broad except wrapped the loading of a setting package in `build_creation_options`: a broken setting yaml or Datasworn file silently disappeared from character creation, with only a warning in the log. Config and data loading must raise per the project rules. The try/except is removed and the file is out of the carve-out.

Test-quality fix: `test_character_traits_is_frozen` used `pytest.raises((AttributeError, Exception))`, which passes on any exception at all; it now expects `dataclasses.FrozenInstanceError`.

Measured but not changed (see AUDIT.md Notes): coverage is 87% overall, with the two provider adapters (`provider_anthropic.py`, `provider_openai.py`) at 0%; `mypy --strict` reports 398 errors (237 `type-arg`, 131 `attr-defined`, 30 `no-any-return`); two upward imports from `mechanics/` into `game/`.

Quality gate: 1249 tests green, twenty-three project-rule scans clean, ruff check and ruff format clean on 186 files, mypy clean on 105 source files. Save format unchanged.

## [2026.09.24.0] — 2026-09-24

Documentation re-sync after a four-month pause, plus a repository fix for the design document. No Python changes; save format unchanged.

The design-document PDF was corrupted in every Windows checkout. ReportLab writes PDFs as pure ASCII, so git's text heuristic treated the file as text, and `core.autocrlf=true` converted its line endings on checkout (30,767 → 31,038 bytes, broken xref offsets). A new `.gitattributes` marks PDF, image, and font files as binary. The blob in the repository was never damaged; only working copies were.

roadmap.md re-synced with the code. Clock expansion (landed in 2026.05.14.0) moved to a new DONE section, together with one-line summaries of all earlier steps. Step 9 (Generator framework) promoted to NEXT STEP with an open question on what triggers fact resolution, a Definition of Done, and reference patterns. New Validator policy section, which four substeps referenced but which did not exist. Dead references fixed (CONTRIBUTING.md, FastAPI, "see Current state" for the session moves). The Purpose section no longer claims the file lives outside the repository and no longer depends on an external system prompt: the absolute rules are in ARCHITECTURE.md and `tests/test_project_rules.py`.

ARCHITECTURE.md drift fixed. Turn pipeline: order and file ownership match the code (NPC activation before the roll, `game/action_resolution.py`, `game/scene_finalization.py`, Director deferred via `game/director_runner.py`). Stale "analytical cluster" and "Architect" references replaced. `role_cluster` described as the full role-to-cluster mapping it is. File map completed with six missing files (`serialization.py`, `yaml_merge.py`, `xml_utils.py`, `bootstrap_log.py`, `ai/api_client.py`, `datasworn/cascade.py`), and the removed `get_logger()` dropped. Serialization claims made consistent: `MemoryEntry` is the only manual `to_dict`/`from_dict` override. The Minimal UI paragraph now matches the actual buttons and the four slash commands. "Engine-resolved fiction" separates the target model from what is implemented today, and Known Limitations agrees with it. Testing-layer count, shipped-ruleset count, and the Contributing rule on project-rule debt aligned. The AI-call carve-out now names `_AI_CALL_CARVE_OUT_FILES` in `tests/test_project_rules.py` as the authoritative file list. Deliberate divergences corrected on three points: EdgeTales and Straightjacket share a lineage, so they are not two independent confirmations; the design document lists a narration validator as one of three options for an open question, and AI-surface reduction is its third option; the design document does not itself call for inter-faction emotional dynamics. Remaining Dutch terms translated.

AUDIT.md: the carve-out anchor now points at the real file list, the output list is consistent, principle 4 names its carve-outs, and hand-off notes were added (see Notes for the next chat). ORIGINS.md: the Ironsworn/Starforged license corrected to CC BY 4.0 (Sundered Isles stays CC BY-NC-SA 4.0), matching README; the EdgeTales v0.9.66 sync attributed to 0.16.0. SECURITY.md: `xa()` attribute escaping mentioned next to `xe()`, and a private contact route added. README lists CHANGELOG, AUDIT, and roadmap.

CHANGELOG: entries added for 2026.05.08.0 and 2026.05.15.0, which were committed without one; version headers added to three entries that had none (2026.05.06.1, 2026.04.28.5, 2026.04.28.3, dated via `git log -S`); every entry is now in English. Two historical inaccuracies are noted here rather than rewritten: the 0.68.0 entry dates the `correction.py` package split to 0.59, but it happened in 0.67.0; and the git tags mentioned in 2026.04.28.3 do not exist in the repository. Entries 2026.05.06.0 and 2026.05.06.1 share commit `d51629c`.

Found during the re-sync and handed to AUDIT.md rather than fixed here: `_check_no_dataclass_defaults_in_config_binding` scans `engine_config.py`, which holds one dataclass, instead of `engine_config_dataclasses.py`, which holds the 88 config dataclasses (currently clean, so the blind spot has no hits yet); the orphan-symbol carve-out still lists `log_tokens`, which no longer exists.

Quality gate: 1249 tests green (including the twenty project-rule scans), ruff check clean, ruff format clean on 186 files, mypy clean on 105 source files — the same test count as 2026.05.14.0, so the state claimed four months earlier still holds. One new warning, not addressed here: the current Starlette release deprecates `httpx` in `starlette.testclient` in favour of `httpx2` (raised in `tests/test_web.py`).

## [2026.05.15.0] — 2026-05-15

Documentation only. `AUDIT.md` added: an operational document for auditing the codebase against five principles (high modularity, config-driven, no defensive programming, no backwards compatibility, clean codebase) as exhaustive hit-lists rather than yes/no verdicts, with a status section tracked per principle and per submodule. `roadmap.md`, until then kept locally, committed to the repository. No CHANGELOG entry was written at the time; this one was added in 2026.09.24.0. The committed roadmap still listed Clock expansion as the next step, although it had landed in 2026.05.14.0.

## [2026.05.14.0] — 2026-05-14

Clock expansion completed. Three spawn sources plus a fill handler plus an owner refactor in one commit.

`ClockData` shape revised: `owner: str = ""` (three semantic roles in two sentinels) → `owner_kind: str` plus `owner_id: str | None`. New required `creation_source: str`. Owner kinds live in `engine/clocks.yaml`. Save format breaks.

Fill handler `mechanics/clock_consequences.py::resolve_clock_fill`. One tag template per clock type from `engine/clocks.yaml::fill_consequences`. A filled progress clock completes its linked track. Suppressed while an attached keyed scene is still pending. Fill events flow through `ActionResolution.clock_fill_results` into a new `<clock_filled>` block in the action and dialog prompts. Fill events from autonomous ticks queue on `WorldState.pending_clock_fills` and are drained and prepended at the next turn.

Random-event spawner `spawn_clock_from_random_event` and AC spawner `spawn_clocks_for_turning_point` follow the threat-spawner pattern. Shared cap `max_clocks_per_chapter`. Naming: Mythic action+subject for random events, the plot-point name for AC (no cascade — deadlines already have their own character).

Spawn-source prefixes consolidated in the new `mechanics/spawn_sources.py` — four hardcoded tuple duplicates plus three module-level locals now in one place.

In-scope fixes: `ThreadEntry.linked_track_id` is now `str | None`; DB schema comments removed and NOT NULL dropped from `threads.linked_track_id`; the old `clock_triggered` attribute on `<r>` removed; the unused `clock_filled_template` removed from `ai_text.yaml`.

Tests 1236 → 1249 green. Ruff plus mypy clean.

## [2026.05.11.0] — 2026-05-11

Threat creation from random events and AC plot-points completed. Two spawn sources, two naming sources. Random-event foci `pc_negative` and `npc_negative` (mappings in `engine/random_events.yaml::threat_creation_mapping`) spawn via `mechanics/random_events.py::spawn_threat_from_random_event`, using the event's Mythic action+subject pair as the name — the random-event mechanism already produced that pair. AC plot-points `A New Enemy`, `Hidden Threat`, `Enemies`, `Hunted`, `A Problem Returns` (mappings in `engine/adventure_crafter.yaml::threat_creation_mapping`) spawn via `mechanics/adventure_crafter.py::spawn_threats_for_turning_point`, with a Datasworn cascade roll as the naming source — Delve cascades from `threat/category` into nine sub-tables, the other settings are single-table (starforged `campaign_launch/sector_trouble`, classic `settlement/trouble`, sundered_isles `seafaring/peril`). Existing 7c keyed scenes `threat_menace_phase any:N` from AC plot-points can now actually fire, because mid-game threats exist.

New shared cascade helper `datasworn/cascade.py::roll_oracle_cascade` follows markdown-link IDs (`[Label](id:setting/oracles/path)`) in oracle-row text, depth limit 4 with a raise when exceeded. `oracle_paths.threats` field added to `OraclePaths` plus all four settings yaml files.

`ThreatData` gets two field changes. `creation_source: str` is required — values `"setup"`, `"random_event:<focus>:<dedup_key>"`, `"ac:<plot_point_name>"` — and the dedup logic reads this field, with no separate dedup sets on NarrativeState. `linked_vow_id: str | None` (was `str`): the implicit "empty string means no vow" pattern becomes explicit, and three src readers get a None skip. Mid-game threats without a vow do not tick via `advance_menace_on_miss` (vow-driven) but do tick via `tick_autonomous_threats`.

Per-chapter cap `max_threats_per_chapter: 3` (in adventure_crafter.yaml) shared across both spawn sources; setup threats do not count.

Signature change of `assemble_blueprint_seed_from_ac` and `assemble_blueprint_seed_kishotenketsu` from `narrative: NarrativeState` to `game: GameState` (the AC spawner needs the setting package for the cascade roll). Three callsites updated; fifteen blueprint tests converted. Save format breaks through both ThreatData field changes plus a DB schema update; no migration.

Spec-drift fix in the same commit: the settings-yaml format example in ARCHITECTURE.md named `oracle_paths.descriptor_focus`, a field that exists neither on `OraclePaths` nor in any settings yaml — probably a leftover from an earlier design. Replaced by `oracle_paths.threats`.

12 new tests in `tests/test_threat_creation.py`. Quality gate: 1236 green (was 1224), ruff check + format clean over 175 files, mypy without issues over 103 source files.

Not done: cascade helper for deeper recursion (depth 4 is ample for the current data); per-source threat-rank variation; name uniqueness within one chapter. Next step: Clock expansion (fill consequences when no keyed scene is attached, clock creation from random events and AC plot-points).

## [2026.05.08.0] — 2026-05-08

Documentation only. `CONTRIBUTING.md` folded into ARCHITECTURE.md as the sections Code standards, Project rules, Config-driven design, Contributing, and Accessibility; the Testing section in ARCHITECTURE gained the Elvira commands. README's further-reading list updated accordingly. No CHANGELOG entry was written at the time; this one was added in 2026.09.24.0.

## [2026.05.06.3] — 2026-05-06

Step 7c completed. Three spawners built together plus a generic pattern layer. AC spawner via `spawn_keyed_scenes_for_turning_point`, called from `assemble_blueprint_seed_from_ac` after every rolled turning point; 33 plot-point mappings in `engine/adventure_crafter.yaml::keyed_scene_mapping` spread over all five trigger types with varying thresholds and priorities; dedup-A on plot-point name plus dedup-B via `max_keyed_scenes_per_chapter: 4`. Random-event spawner via `spawn_keyed_scene_from_random_event`, called from `generate_random_event` as soon as the event is constructed; four mappings in `engine/random_events.yaml::keyed_scene_mapping` (npc_action, npc_positive, npc_negative, pc_negative); concrete trigger value from `event.target_id` (bond) or `event.target` (threat name); dedup on `(focus, target_id)`. Clock spawner via `spawn_keyed_scenes_for_clock`, called from `apply_world_setup` plus the hardcoded background-vow clock in `game_start.py`; per-clock-type fractions in the new `engine/clock_keyed_scenes.yaml` (threat and scheme: 0.5 plus 1.0; progress: 1.0 only); the narrative-hint template substitutes clock_name; dedup on `(clock_name, threshold)`.

Generic pattern grammar for the three pattern-supporting trigger types. `bond_threshold` accepts `<npc_id>:N`, `any:N`, or `disposition_<value>:N` (validated against `engine/enums.yaml::dispositions`). `threat_menace_phase` and `clock_fills` accept `<entity_name>:N` or `any:N`. Per trigger type a `pattern_grammar` block in `engine/keyed_scenes.yaml` with valid prefixes plus matcher_strategy (`highest_bond` / `highest_menace` / `highest_filled`). At fire time `evaluate_keyed_scenes` resolves pattern triggers to concrete entities, sets `KeyedScene.bound_entity_id`, and respects "not previously bound" — an NPC, threat, or clock already bound to a keyed scene is skipped by sibling matchers. Once bound, a pattern scene behaves as a concrete trigger on its entity (re-evaluation checks whether that specific entity reaches the threshold, not the whole pool again).

KeyedScene changed: new `bound_entity_id: str | None = None` plus `source: str = ""` fields. Save format breaks — existing saves lose their keyed_scenes list shape, new saves carry the two fields. No migration. `chaos_extreme` and `scene_count` are entity-less and have no pattern form. ARCHITECTURE.md drops the "spawning is not yet wired" qualifier and moves to the three-spawner reality; the AC paragraph becomes "fully wired into engine-resolved fiction". 1224 tests green (was 1188, +36); ruff/format/mypy clean. Two new roadmap steps ("Threat creation from random events and AC plot-points" and "Clock expansion" — fill consequences plus clock creation from random events plus clock creation from AC plot-points) scheduled between 7c and 13b.

Not done in this step: faction filter on the bond_threshold grammar (waits for step 14a `FactionData`); threat creation from AC plot-points or random events (its own next step); clock creation from move outcomes, random events, or AC plot-points (covered by the Clock expansion step); default fill consequences when no keyed scene is attached (same Clock expansion step).

## [2026.05.06.2] — 2026-05-06

Step 7b completed. AC character-crafting tables ship as pure helpers in `mechanics/adventure_crafter.py`: `roll_character_traits(rng) -> CharacterTraits` plus three per-table lookup helpers (`lookup_character_special_trait`, `lookup_character_identity`, `lookup_character_descriptor`). `CharacterTraits` is a frozen dataclass with `(special_trait: str, identities: list[str], descriptors: list[str])` — a list length of 1 or 2 is the discriminator on both identities and descriptors. Reroll-on-flag convention: a roll of 1-33 on identity and 1-21 on descriptors triggers two direct rolls on the non-flag range (`rng.randint(34, 100)` / `rng.randint(22, 100)`), no recursion or rejection-sampling loop. No consumer wired in this step — step 11 (NPC tiers) consumes `CharacterTraits` in the NPC data flow; an orphan-symbol carve-out for the five new public symbols is in `tests/test_project_rules.py` and is removed by step 11 once the consumer lands.

Three spec-drift fixes in the same commit. First: roadmap substep 7b.1 prescribed `(special_trait, identity, dual_identity, descriptors)` — a single identity with a separate boolean flag. The step 4 precedent (`is_keyed: bool` removed because `scene_type == "keyed"` was the discriminator everywhere) applies symmetrically here: list length as discriminator, no parallel bool. Final shape `(special_trait, identities, descriptors)`, both list fields 1 or 2 long. Second: substep 7b.4 prescribed "result struct serialises through SerializableMixin round-trip", but `CharacterTraits` is a transient runtime seed object of the same shape as `BlueprintSeed`/`PlotPointHit`/`TurningPoint`/`ActSeed` — none of those has the mixin, because they are not persisted. They produce mutations on `narrative.*_list` fields, which do go through SerializableMixin via `NarrativeState`. Step 11 will follow the same pattern: rolled traits feed NPC data construction, the persisted state is the resulting `NpcData`, not the traits object. Serialization test dropped. Third: `data/adventure_crafter.json::character_identity` had no entry for roll 99 — the transcription of AC v2 page 117 (Collected Tables) faithfully reproduced the dash the book itself leaves there, presumably Tana Pigeon's own typo. Gap filled with `Spy` in this commit, categorically consistent with the neighbouring entries (Soldier 82, Law Enforcement 83, Scientist 84). Coverage 1..100 is now complete.

Tests: 43 new in `tests/test_character_crafting.py` (boundary tests per table, full coverage 1..100, flag-range detection, dual-identity / two-descriptor paths via stub RNG, fixed-seed determinism, frozen property). ARCHITECTURE.md: the AC primitives module-ownership row extended with the four new symbol names, the AC primitives Key Design Decision paragraph extended with one sentence on the character-crafting helpers plus the orphan carve-out status. Quality gate: 1188 tests green (was 1145, +43 character-crafting), ruff check + format clean over 171 files, mypy without issues over 102 source files.

---

## [2026.05.06.1] — 2026-05-06

Step 8 completed (shipped in the same commit as 2026.05.06.0, `d51629c`). `ai/architect.py` split into `ai/recap.py` (`call_recap`) and `ai/chapter_summary.py` (`call_chapter_summary`). After step 7a the file was no longer about an architect — `call_story_architect` disappeared there — and the name no longer covered the content. `engine/architect.yaml` renamed to `engine/recap_limits.yaml`; top-level block `architect_limits:` → `recap_limits:`; field `architect_campaign_window` → `recap_campaign_window`. Dataclass `ArchitectLimitsConfig` → `RecapLimitsConfig`. One stale reader in `ai/blueprint_voicing.py` (from step 7a) updated. Tests split: `test_architect.py` removed, new `test_recap.py` with the five recap tests, `test_chapter_summary.py` extended with the four chapter-summary tests. Carve-out list in `test_project_rules.py` updated. Quality gate: 1145 tests green, ruff check + format clean, mypy without issues over 102 files.

---

## [2026.05.06.0] — 2026-05-06

Step 7a completed. The AI architect is replaced by an AC blueprint plus a voicing call. Plot shape (acts, phases, turning points, plot-beat seeds, ending seeds) comes from Adventure Crafter; one small AI call (`call_blueprint_voicing`) translates those seeds into setting prose for fields that tables cannot supply (central_conflict, antagonist_force, thematic_thread, per-act goal/mood/title, revelation content, ending type/description). The AI no longer picks plot beats — it gives them a setting voice.

Pipeline: `assemble_blueprint_seed_from_ac` (3-act path; rolls turning points and assembles revelation seeds plus ending seeds from `narrative.plotlines_list`) or `assemble_blueprint_seed_kishotenketsu` (kishotenketsu path; no turning points, four phase-acts from yaml) produces a frozen `BlueprintSeed`. Then `call_blueprint_voicing` → dict or None. `materialize_blueprint(seed, voicing)` combines both into a complete `StoryBlueprint`; if voicing fails, `narrative.story_blueprint` stays None and the Director falls back to its no-blueprint defaults (graceful degradation, no session crash). Scene ranges per act come mechanically from an even split of `scene_range_default`; no invented distribution. `act.phase` per act comes literally from the yaml phase list.

Removed: `call_story_architect`, `_clean_act_moods`, `_validate_scene_ranges`, `_build_architect_user_msg`, `prompts/architect.yaml`, schema `get_story_architect_output_schema`, schema title `story_architect_output`, the role-cluster mapping for `architect`, yaml block `architect:` with `forbidden_moods`, ai_text field `default_act_mood`. Added: `prompts/blueprint_voicing.yaml`, `prompts/chapter_summary.yaml` (chapter_summary taken out of the old architect.yaml), an `engine/adventure_crafter.yaml` `blueprint:` section with phase names plus counts (no content), schema `get_blueprint_voicing_schema`, schema title `blueprint_voicing_output`, role-cluster mapping `blueprint_voicing: creative`. New `BlueprintConfig` dataclass. `ArchitectConfig` dataclass removed.

Dataclass defaults on `StoryAct`, `Revelation`, `PossibleEnding` removed (all fields now required); `StoryBlueprint` scalar defaults removed, empty-collection factories kept, runtime flag `story_complete: bool = False` kept (initial runtime state, not a config field). Save format breaks without migration. Three callsites reworked: `game/game_start.py`, `game/chapters.py`, `game/succession.py` — `_apply_blueprint` signature is now `(game, seed, voicing)` instead of `(game, provider, blueprint_dict)`.

Tests: `test_architect.py` (24 old tests) cut back to the 9 that still apply (the rest removed along with their functions). New `test_blueprint.py` with 16 tests on seed assembly, materialize, the kishotenketsu path, the frozen-dataclass property, plus a grep test that `call_story_architect` no longer appears anywhere in src/. Six other test files updated for stricter dataclass callsites (`test_director.py`, `test_models.py`, `test_story_state.py`, `test_web.py`, `test_prompt_boundary.py`, `test_chapters.py`). `_helpers.py` gained `make_act`, `make_revelation`, `make_ending`, `make_blueprint`. Quality gate: 1145 tests green, ruff check + format clean, mypy without issues over 101 files.

ARCHITECTURE.md updated: module-ownership rows for story structure and chapter transition; AI cluster table `architect` → `blueprint_voicing`; file map `ai/architect.py` split (technically in step 8, the doc already prepared for the combined delivery); carve-out paragraph updated; the "AC's role expands" paragraph rewritten with the blueprint path plus an explicit bounded scope (no mid-chapter AC scheduling; that stays with the six existing pacing systems); the Known Limitation "Blueprint is AI-generated at game start" removed because it no longer holds.

One design error early in the session, where yaml was filled with content I had invented (act moods "tense, rising, climactic", kishotenketsu prose templates), was caught by the user and reverted. Yaml now holds only what a table source or a mechanical distribution can justify; setting fields come from the voicing call, not from yaml. This is a principle — yaml is consolidation, not creation — and it is now recorded in the project rules (ARCHITECTURE.md "Yaml content boundary").

---

## [2026.04.29.0] — 2026-04-29

Step 6b (AC turning points and supporting tables) completed. Turning-point assembly via `roll_turning_point` combines 2-5 plot points into one plot beat: d100 on `plotlines_list_template` for the plotline choice, with a `choose_most_logical` fallback when the list is empty, then 3d10 per plot point (theme priority via `plot_point_theme_priority` with 4th/5th alternation in a per-assembly `ThemeAlternation` dataclass, plus 2d10 as d100 for the plot-point lookup). A Conclusion (1-8) on any of the hits flips the active plotline from `advancement` to `conclusion`. Three new lookup helpers (`lookup_theme_priority`, `lookup_characters_template`, `lookup_plotlines_template`). The seven `NotImplementedError` stubs from step 5 replaced by real handler bodies that mutate `narrative.characters_list` and `narrative.plotlines_list`; `dispatch_meta` signature changed to `(roll, narrative, active_plotline_id)`.

Spec drift repaired in the same commit. Roadmap substep 6b.3 prescribed two new NarrativeState fields (`ac_characters_list` plus `ac_plotlines_list`); the implementation has one shared `characters_list` with AC fields (`ac_status`, `ac_turning_point_count`) plus a new `plotlines_list`. Reason: the same NPC twice in NarrativeState with different ID schemes would become a join problem in step 11 (NPC tiers) and step 24 (NPC-NPC triangles) that need not arise now. Second correction: roadmap substep 6b.3 named 25 as a slot cap on the runtime list; 25 is in fact the template roll size (25 d100 ranges), not a length limit. The Mythic `consolidation_threshold` in `engine/random_events.yaml` is the real length control and works for AC additions as well. ChapterSummary gained two new fields for the three-place chapter pattern; save format breaks without migration.

Meta-handler numbers via yaml. `engine/adventure_crafter.yaml` gained a `meta_handlers` block with `weight_delta_step_up: 1`, `weight_delta_step_down: -1`, `weight_delta_upgrade: 2`, `weight_delta_downgrade: -2`, `weight_floor: 1`. Dataclass `MetaHandlerConfig` bound. The four weight-touching handlers (steps_up/down, upgrade/downgrade) read through one shared `_apply_weight_delta` helper that enforces the floor. Upgrade is therefore heavier than Steps Up (category jump vs gradual) and stays tunable without a code edit when playtest feedback lands in step 7a.

ARCHITECTURE.md "Adventure Crafter primitives" paragraph rewritten with turning-point semantics and the shared-list choice; the module-ownership table gained an AC-lists row; the file-map comment for `adventure_crafter.py` extended. Doc-only bycatch in the same session: a counting error in line 316 ("two existing Director tools" → "three existing Director tools") repaired. Tests 1117 → 1144 (+27: one extra config-loader test plus 26 for 6b behaviour, including two rewritten NotImplementedError tests). Save format breaks. Quality gate: pytest, ruff check, ruff format, mypy all four green.

---

## [2026.04.28.5] — 2026-04-28

Step 6 (AI data supply audit and migration) completed, plus extra hygiene on schema-validated AI output downstream of the first AI call sites. An audit of fourteen AI call sites confirmed that the "tool-call vs prompt-inject" principle is applied correctly everywhere — no migrations needed. What did have to go: hardcoded fallbacks, shadow-boxing `dict.get` with defaults on fields where the schema is stricter, dead code that promised a feature but was never consumed, plus stale config names.

Concretely: the `<reflect>` block memory window (8) and the `query_npc` memory window (5) unified on one yaml key, `engine/npc.yaml::npc.reflection_observation_window`. Schema-required AI output fields read via direct subscript in `ai/brain.py`, `ai/narrator.py`, `ai/metadata.py`, `ai/architect.py`, `correction/orchestrator.py`, `correction/ops.py`, `correction/analysis.py`, `npc/processing.py`, `director.py`. The hardcoded correction fallback dict in `correction/analysis.py` replaced by yaml keys under `narrator_defaults`. `constraint_check_max_retries` (a stale name from the removed constraint validator) renamed to `tool_loop_round_max_retries` across yaml plus dataclass plus handler. Dead `or ""` fallbacks on the always-string `snap.player_input` removed. `available_moves` now raises on no setting instead of returning an error-shaped dict. Dead `reflection_tone_fallback` yaml key removed (no Python reader). `find_npc` typed as `str | None`, as it had in fact always worked.

Two real bugs found during the sweep. One: the schema field `extra` in narrator_metadata was read by nobody, while `_apply_description_updates` in turn read an invented field `details` that never arrived — two dead sides that did not know about each other. Schema field plus code block both removed. Two: the director prompt asked the AI for an `act_transition: bool` field that the director schema does not have (`additionalProperties: False`) and that no Python reads — the act-transition decision is engine-deterministic in `_check_engine_act_transition`. Tokens and AI attention wasted on work the engine already did; a latent failure under stricter model behaviour. Prompt line removed, two mock tests cleaned up.

ARCHITECTURE.md gained a "Concrete callsite mapping" paragraph after "When tool-call vs when prompt-inject" — four sentences naming, per callsite category, what is prompt-only and which field the mixed Director callsite shares with the tool path. Save format unchanged. 1117 tests green (was 1119; two architect tests removed that passed `{}` to schema-validated functions — assumption-never-held), ruff clean, ruff format clean on 167 files, mypy clean on 100 source files, twenty project-rule scans clean.

---

## [2026.04.28.4] — 2026-04-28

Half of the fate flow from 28.2 reverted, based on a clarity of principle that 28.2 lacked: the player types actions, not questions. The engine consults fate under the hood when the fiction needs a fact, not through a player fate question detected by Brain. `BrainResult.fate_question` removed, `fate_question` removed from the Brain output schema, `_resolve_brain_requests` returns only `list[RandomEvent]` again, `SceneContext.fate_result` removed, `_fate_answer_block` plus the `<fate_answer>` injection removed from `prompt_action.py` and `prompt_dialog.py`. Dead imports (`FateResult`, `resolve_fate`, `resolve_likelihood`) cleaned up in five files. Test count unchanged (1119) — no tests exercised this path-specific flow; the existing fate tests cover the fate functionality of the random-event path, which stays intact.

ARCHITECTURE.md adjusted in three places. The Tool calling and Fate system paragraphs rewritten so they no longer describe the half flow. A new Engine-resolved fiction paragraph in Key Design Decisions records the principle: the engine produces all facts before the narrator writes, fate and oracle consultation happens at many concrete callsites spread across the turn pipeline, and there is no central fate router (per "duplication is cheaper than wrong abstraction"). A new Datasworn mechanic naming paragraph allows a `no_roll`/`special_track` move as an engine trigger with a direct name (such as `advance_menace_on_miss`) when it is a consequence, and as a formal move in `move_outcomes.yaml` when it is a player choice. Both principles make explicit what was implicit, so a future Claude session or a reader of the codebase does not have to reconstruct them.

Save format unchanged. 1119 tests green, ruff clean, ruff format clean on 167 files, mypy clean on 100 source files, project-rule scans clean.

---

## [2026.04.28.3] — 2026-04-28

`engine/move_categories.yaml` from 99 to 66 lines — 33 unimplemented Datasworn moves removed from the six category buckets. Trigger: investigating `session/begin_a_session` exposed that all five session moves plus 28 other Datasworn moves were in `move_categories.yaml` without a backing implementation in `move_outcomes.yaml` or `engine_moves.yaml`. Verification via `available_moves`: all 33 have a `roll_type` of `no_roll` or `special_track` and are filtered out of Brain's move list before Brain can choose them. Their presence in `move_categories.yaml` was not enforceable by any runtime path, only by a test invariant that demanded a deliberate categorisation for every Datasworn move.

`tests/test_engine_memories.py::TestMoveCategoriesCoverage::test_every_implemented_move_has_real_category` rewritten (was `test_every_datasworn_and_engine_move_has_category`). The old contract required every Datasworn move plus every `engine_move` to have a real category in `move_categories.yaml`, other than the fallback `other`. The new contract requires every move from `move_outcomes.yaml` plus `engine_moves.yaml` to have a real category. The old contract forced placeholder categorisations for moves that `move_category()` cannot reach via any existing code route, because all five callsites take Brain output as their source and Brain does not see the `no_roll`/`special_track` moves. The silent-fallback protection the old contract aimed for is already enforced more strongly by `resolve_move_outcome` line 19 (`raise ValueError(f"No outcome config for {move_key}")`) — an unimplemented move that still arrives via Brain raises loudly, not silently. The new contract is functionally equivalent without maintenance work done ahead of time.

CHANGELOG cleanup in the same session. Two entries added for 28.1 (doc-only `engine.yaml` shorthand cleanup) and 28.2 (two paragraphs, explicitly separating the independent cleanup from the half fate-flow migration, including the note that Brain is not instructed to fill `fate_question`, which makes the whole pass-through dead at runtime). Plus seven missing historical headers filled in based on paragraph content and position between the surrounding headers: 27.11 (based on an explicit reference in 28.0), 0.69, 0.68, 0.67 (positional derivation between 0.66 and 0.70 plus content order dead-code sweep → debt checks → file splits), 0.62 (based on the "Batch E from v0.61.0 audit" text), 0.61 (based on the "Batch F from v0.60.0 audit" text), 0.58 (based on the "Tranche 6" text). Plus a double `---` between 0.73 and 0.72 removed. This restores the delivery-gate precedent from 28.0 that had been broken again in 28.1 plus 28.2. (This entry itself was committed without a version header; the header was added in 2026.09.24.0.)

Begin a Session — no longer an open design question. The Datasworn spec has `roll_type: no_roll`, and at the tabletop it is a table procedure with group assumptions that does not map naturally onto a browser-tab context. The current load flow restores GameState completely and puts the player exactly where they were before saving; a recap is available via an explicit button. No functional gap. After this cleanup the five session moves are no longer in `move_categories.yaml`. If they are ever implemented, they come back in the same commit — in `move_outcomes.yaml` or `engine_moves.yaml` plus in `move_categories.yaml` under the right bucket, per the strict rule "update every caller in the same commit."

Pyproject version finally updated — it had been at 2026.04.28.0 since 28.0 while the git tags were 28.1 and 28.2. Existing drift, corrected here to 2026.04.28.3. (The repository contains no git tags; see 2026.09.24.0.) Save format unchanged. Test count 1119 (one test rewritten, no net addition or removal). Ruff clean, ruff format clean, mypy clean on 100 source files.

---

## [2026.04.28.2] — 2026-04-28

Two kinds of work in one commit, separated explicitly here.

Independent cleanup, separate from the fate/oracle design question. `prompts/brain.yaml` `brain_setup` prompt removed — pre-0.36 residue from when character creation was still AI-driven; deterministic via Datasworn since 0.36, no consumer. `src/straightjacket/engine/ai/json_utils.py` plus its test removed — `extract_json` had no consumers in src; the two callsites that once used it have long worked via structured provider output. `src/straightjacket/engine/datasworn/loader.py` `list_available()` plus `clear_cache()` removed — `list_packages()` in `datasworn/settings.py` is the canonical discovery route, the loader versions were dead. `src/straightjacket/engine/mechanics/fate.py` `get_odds_levels()` removed; it was a wrapper around `eng().enums.odds_levels` with no logic of its own. `src/straightjacket/engine/tools/builtins.py` `query_npc_list`, `roll_oracle`, `fate_question` removed as tool wrappers — leftovers from the v0.41-v0.45 tool-call architecture, no longer connected since 0.46.50 when Brain moved to prompt injection. `tests/test_project_rules.py::_collect_src_uses` now recognises `getattr(obj, "name")` as a use of `name` — closes one blind spot in the orphan scan. ARCHITECTURE.md, ORIGINS.md, CONTRIBUTING.md: drift-prone meta numbers removed (test counts, source-file counts, dataclass-field counts); the Deliberate divergences paragraphs extended from two to five with the two-call narrator pattern, no narration validator, and the faction-layer scope; the hub paragraph rewritten.

Half fate-flow migration, tied to the fate/oracle design question opened in the same session. `BrainResult.oracle_table` plus the Brain output-schema entry removed, because the `ask_the_oracle` move covers the same domain. `BrainResult.fate_question` stays; the pass-through flow between Brain classification and the narrator prompt is built: `_resolve_brain_requests` now returns `tuple[list[RandomEvent], FateResult | None]`, `SceneContext` gained a `fate_result` field, `prompt_shared.py` gained a new `_fate_answer_block` helper that renders `<fate_answer question="..." odds="..." answer="..."/>`, and `prompt_action.py` plus `prompt_dialog.py` inject the block next to `events_block`. The ARCHITECTURE paragraphs on Tool calling and Fate system rewritten to describe the new flow.

Not done on this flow: Brain is nowhere instructed to fill `fate_question`. The prompt has no field explanation, the schema returns `null` by default, and so the whole pass-through pipeline never fires in practice. This is dead-at-runtime weight in the tree, not working functionality. The next session decides whether the half flow is reverted before the real fate/oracle design lands, or stays as working-but-not-final scaffolding. Tests that fell away with this cleanup were for removed functions; no coverage lost — `tests/test_oracle.py`, `test_fate.py`, `test_tools.py`, `test_web.py`, `test_correction_flow.py`, `test_integration.py`, plus all of `test_json_utils.py`. Test count -19. Save format unchanged. Ruff clean, ruff format clean, mypy clean.

---

## [2026.04.28.1] — 2026-04-28

Doc-only cleanup of the `engine.yaml` shorthand drift that 28.0 explicitly named as deliberately deferred. The ARCHITECTURE.md Module Ownership table plus the Key Design Decisions paragraphs now consistently refer to `engine/<name>.yaml` (the actual per-subsystem files) instead of the collective path `engine.yaml`, which has not existed since the modular yaml split in v0.60.00. The drift-strategy paragraph got back its closing sentence, lost in an earlier edit, about the diagnostic measurement layer as an open option. No Python, no tests, no save format. One file touched, 24 substitutions.

---

## [2026.04.28.0] — 2026-04-28

27.11 residue actually finished. The previous session claimed three cleanup actions — deleting `tests/elvira/elvira_bot/drift_checks.py`, deleting `engine/move_routing.yaml`, a format fix on `tests/test_yaml_symmetry.py` — but the two deletes did not make it into the commit, because zipping over the local tree does not carry implicit deletes; the format fix did not either. Consequence: at the 27.11 commit `test_project_rules.py` was in fact red on three scans (broad except in drift_checks, orphan engine yaml key for move_routing, ruff format drift in test_yaml_symmetry), not "twenty project-rule scans clean" as 27.11 stated. This release removes the residue after all and restores the delivery-gate precedent: claims in the CHANGELOG correspond to the real state of the tree again.

ARCHITECTURE.md test-count drift repaired: 1187 → 1138, in line with ORIGINS.md and CONTRIBUTING.md, which had already been updated in 27.11. The doc debt around `engine.yaml` as shorthand for the `engine/<name>.yaml` package stays, per the decision in the roadmap's Current state — it gets cleaned up in a separate md-only session, not obscured by a feature step.

No Python edits beyond the two deletes. Save format unchanged. Test count 1138, twenty project-rule scans clean, ruff check clean, ruff format clean, mypy clean on 101 source files.

---

## [2026.04.27.11] — 2026-04-27

Cleanup pass plus three new project-rule scans. 27.10 residue cleaned up after all: `tests/elvira/elvira_bot/drift_checks.py` had been left behind and read refactored-away GenreConstraints attributes on a type that no longer exists — removed, plus its carve-out entry in `test_project_rules.py`. `data/settings/delve.yaml` still had an empty `genre_constraints: {}` block without a consumer — removed. `engine/move_routing.yaml` was a regression after its earlier removal in 0.46.5 — nobody read it, all its data is already represented in the per-move parameters of `move_outcomes.yaml` — removed. Two dead public functions removed: `reload_config` in `config_loader.py` (no consumer anywhere) and `list_tracks` in `tools/builtins.py` (written as an engine query helper analogous to `available_moves`, never used); `list_tracks` also stripped from the ARCHITECTURE table. Format residue from an earlier commit in `tests/test_yaml_symmetry.py` included.

Three new scans in `test_project_rules.py`, twenty in total now. `_check_ruff_format_clean` runs `ruff format --check` as a delivery gate from within pytest — it also catches format drift on machines without a pre-commit install. `_check_no_orphan_public_symbols` checks every public `def`/`class` in src for at least one external consumer, with a carve-out set for legitimately uncalled cases (web route handlers, sub-attribute dataclasses, AICallSpec fields); it would have stopped the `move_routing`-style regression. `_check_no_orphan_yaml_keys` checks every top-level yaml key in `engine/` for presence in Python via string literal or `get_raw("...")` with dotted path — exactly the scan that 0.46.5 introduced but that was not run in 27.10. The initial naive implementation took 32 sec; a one-pass corpus rewrite plus complexity decomposition brought it to 6.7 sec, the total suite from 42 sec to 12 sec. md files synced: ORIGINS from 1137/eleven to 1138/twenty, CONTRIBUTING from seventeen to twenty scans. Save format unchanged. Test count 1138.

---

## [2026.04.27.10] — 2026-04-27

Strict-rule cleanup passes and the completion of the validator cascade that began in 27.8 and 27.9. The scan result of `tests/test_project_rules.py` went from fifty-two violations at session start to zero at commit time. Four successive passes plus an md audit, all save-format compatible.

Pass 1 (`e6fd7ed`): twenty-two dead `Optional` collection defaults plus `or X` fallbacks removed, plus bycatch in touched files. Strict signatures on all prompt_blocks helpers, `call_narrator`, `apply_narrator_metadata`, `register_extracted_npcs`, `_npc_block` and families (move_category required). `ai/schemas.py` split into `_str` plus `_str_enum` plus `_str_with_desc` plus `_obj` plus `_obj_root` for non-Optional helpers, with eight callsites migrated. `tools/registry.py` split into production `register` plus `register_test_tool`. Magic number `creativity_seed n=3` moved to yaml. Pass 2 (`0fbb79a`): an AICallSpec dataclass replaces eleven optional kwargs on `AIProvider.create_message` and `create_with_retry` with one `spec` parameter — the Optionals now live inside one dataclass that models the external-boundary AI API shape, covered by the existing exception 2. Both providers plus nine production callsites plus the director pipeline plus `run_tool_loop` migrated. Test MockProviders consolidated in `tests/_mocks.py`. Pass 4 (`325264b`): three sentinel Optionals resolved by splitting — `resolve_fate_check` plus `resolve_fate_check_with_dice`, `process_deceased_npcs` plus `process_deceased_npcs_with_presence_check`, `_npc.secrets` via a module constant plus a `tuple[str, ...]` default.

Elvira demolition (`4915e24`): drift check and GenreConstraints removed entirely. `tests/elvira/elvira_bot/drift_checks.py` deleted plus all writers plus the `drift_summary` field plus reader. `GenreConstraints` plus partial plus parser plus resolver plus property removed in `datasworn/settings.py`. The `genre_constraints` block plus three keys (`forbidden_terms`, `atmospheric_drift`, `atmospheric_drift_threshold`) removed from all three shipped settings yamls. Twelve dead reporting fields removed from `SessionLog` (ten), `ChapterRecord` (one), `TurnRecord` (one) — all write-only, with no code reader outside the asdict payload. md audit (`2d7fd5e`): the ARCHITECTURE.md drift-strategy paragraph rewritten to "AI-surface reduction over post-hoc validation"; Settings YAML format plus Inheritance stripped of `genre_constraints`; CONTRIBUTING.md scan count from eleven to seventeen, Elvira paragraph rewritten, model_eval paragraph removed completely.

Not done: the ARCHITECTURE.md table still refers in several places to `engine.yaml` as shorthand for the engine yaml package, while the configuration is spread over `engine/<name>.yaml` files. A doc inconsistency, not demolition residue; a decision for a separate session. Test count: 1137 → 1138 (one test added for `run_tool_loop_hits_max_rounds`, which monkeypatches `pacing.max_tool_rounds` via `dataclasses.replace`). Save format unchanged.

---

## [2026.04.27.9] — 2026-04-27

Architect validator and chapter validator removed. `ai/architect_validator.py` plus `ai/chapter_validator.py`, their yaml and prompts, and their tests deleted. Reason: validators on AI output are AI work that belongs to the engine. The architect blueprint can become table-driven; the chapter summary guards the mechanical snapshot as canon, and the prose stays colour without a retry gate.

Leftover 27.8 residue included: `_validator_cache`/`get_validator_schema` in `ai/schemas.py`, `validator: judgment` and `validator_architect: extraction` in `config.yaml`, `engine/ai/validator.py` and `engine/ai/chapter_validator.py` in the carve-out of `test_project_rules.py`. Plus the whole Elvira validator stack: `ValidatorRecord`, `TurnRecord.validator`, `SessionLog.opening_validator`, `SessionLog.validator_summary`, `_snapshot_validator` in the recorder, `_log_opening_validator` and `_aggregate_validator_stats` in the runner, `compute_validator_balance` in drift_checks, the validator print block in display, and `tests/elvira/elvira_batch.py` (a compliance meter without a validator). Plus `tests/test_pattern_family_resolution.py`, which had been testing a removed API since 27.6.

Dead config fields removed in the same sweep: `GenreConstraints.forbidden_concepts` and `genre_test`; `OraclePaths.factions`; `StopwordsConfig.consequence` (plus a 45-line yaml block); `FuzzyMatchConfig.label_word_min_length`; `TruncationsConfig.narration_max`; `SuccessionConfig.retire_command`. `KeyedSceneTrigger` dataclass removed; `triggers` is now `frozenset[str]` instead of a dict with two dead fields. Missing CHANGELOG headers for 25 and 26 April restored.

Not done: Elvira's ten reporting fields in `ChapterRecord`, `SessionLog`, and `TurnRecord` that only end up in JSON via `asdict` were not touched — not code config, only log payload; a decision for a separate session. Three keys in `genre_constraints` (`forbidden_terms`, `atmospheric_drift`, `atmospheric_drift_threshold`) have only Elvira's `check_blueprint_drift` as a reader; to be removed when that check goes too. Test count: 1187 → 1137 (50 tests removed with the demolished modules and test_pattern_family_resolution).

---

## [2026.04.27.8] — 2026-04-27

Narration validator removed completely. `ai/validator.py` (LLM validator + retry loop) and `ai/rule_validator.py` (regex layer) plus all related yaml (`engine/validator.yaml`, `engine/rule_validator.yaml`, `prompts/validator.yaml`), tests (`tests/test_validator.py`, `tests/test_rule_validator.py`), and the model-eval tool (`tests/model_eval/`) are gone. Reason: the LLM validator judged writing rules that are ambiguous even for humans (fact_budget counting, RESULT INTEGRITY equivalence), and the retry loop produced predictable prose flattening. The rule validator would only exist to report diagnostically — without a consumer that is dead weight. The whole branch cut away.

Cascade: `ConsequenceEvent` dataclass plus the `consequence_event_phrasings` yaml section removed (built earlier this same session for the RESULT INTEGRITY event architecture), `generate_consequence_sentences` returns only `list[str]` again, `narrate_scene` signature simplified (no more `validate_result_type`/`player_words`/`consequences`/`consequence_events`/`target_npc_name`/`fact_budget` parameters), `SceneLogEntry.validator` field plus the matching `validator` column in the `scene_log` DDL and sync writer removed, `_resolve_target_fact_budget` in `turn.py` dead and deleted, `validator_blocks` ai_text section removed (only `momentum_burn_injection` remains, moved to `narrator_defaults`), `RuleValidatorConfig` and `ValidatorConfig` dataclasses + `_SIMPLE_SECTIONS` entries removed. The chapter validator keeps its own `violation_templates` (migrated from `rule_validator.yaml` to `chapter_validator.yaml`); chapter-validator prompts now have their own `prompts/chapter_validator.yaml` (they were part of the removed `prompts/validator.yaml`).

The architect validator stays until step 8 (roadmap). Save format breaks — no migration. ARCHITECTURE.md updated: validator flow, file map, module table, AI-call carve-out, drift strategy, and model-assignment table all adjusted for the removal of the narration validator.

---

## [2026.04.27.7] — 2026-04-27

`test_project_rules.py` extended with four strict-rule checks: `.setdefault()` fallbacks, misuse of `eng().get_raw(key, fallback)`, warning-suppression comments (`# noqa`, `# type: ignore`, `# pragma: no cover`), and versioned filename suffixes (`_v2.py`, `_old.py`). The last three are now clean; `.setdefault()` reports two violations in `engine/game/setup_common.py`.

The test was discovered red this session on pre-existing violations I had overlooked. Full state now: 62 violations in three categories (`name or empty-collection` fallback 9, optional-collection default 51, setdefault 2). The test is red; it reports file plus line number plus snippet per violation for a later fix session.

---

## [2026.04.27.6] — 2026-04-27

Three related pieces: a new RESULT INTEGRITY validator architecture, GENRE PHYSICS plus RESOLUTION PACING tuning on the active narrator prompt, and a large-scale cleanup of the `(role, model_family)` resolution layer. The RESULT INTEGRITY architecture first. The validator used to receive literal consequence sentences plus the instruction "demand the event, not the phrasing" — a contradiction that in the batch led to 31 RESULT INTEGRITY violations (52 percent of the total), dominated by literal "advantage shift" and "opening" string matching. New `ConsequenceEvent` dataclass in `models_base.py` with `event_code`, `subject`, `acceptable_phrasings`. New yaml section `consequence_event_phrasings` in `engine/consequence_templates.yaml` with 5-10 phrasings per event code; `momentum_gain`, for example, has "opening", "advantage shift", "edge", "ground tilts", "rhythm caught", "upper hand". Four singleton templates extended to three or more variants. `generate_consequence_sentences` now returns `tuple[list[str], list[ConsequenceEvent]]`; the resolver layer merged into one `_classify` function. The validator receives events via `ValidationContext.consequence_events`; the narrator keeps receiving prose seeds via `<consequence>` XML tags. Validator prompt block rewritten to "Each line names an event_code and acceptable phrasings; the narration is COMPLIANT if it expresses the event using ANY phrasing — exact match is not required." Two new symmetry tests in `test_yaml_symmetry.py` enforce that templates and phrasings have the same keys.

GENRE PHYSICS and RESOLUTION PACING at the narrator level. The narrator GLM prompt was asymmetric with the universal variant — no fact_budget explanation, no examples with `fact_budget=N` labels — while `<target_npc fact_budget="N">` was already in the input. The NPC SPEECH CONTENT block extended with a fact_budget explanation and pattern-block examples labelled `fact_budget=1` and `fact_budget=2`. For GENRE PHYSICS three measures: a TRANSFORMATION RULE added ("when an inanimate subject would take an active verb, swap subject and agent so the player or environment performs the action"), positive examples from batch data ("you press your palms against the iron rungs", "iron grinds against iron under your weight"), and a new regex layer `genre_physics_patterns` in `engine/validator.yaml` that catches personification of metal and architecture before the LLM validator has to run. Eight regression tests with the exact fragments from the batch ("iron rungs bite", "the hole yawns", "the lock whines", "iron screams", "wind moans") plus negative tests for correct use and the quoted-dialogue exception.

`(role, model_family)` resolution layer removed in its entirety — a fallback system for models that are not running, built in 2026.04.26.1 and dead weight since. The practice: one narrator prompt for one model (GLM), one validator prompt for one model (gpt_oss), three empty `_overlays: {}` dicts, and seven dead helper functions. All gone. `narrator_system_glm` renamed to `narrator_system`, the bare `narrator_system` (universal fallback) removed. Likewise `validator_system_gpt_oss` → `validator_system`. `*_universal`/`_overlays` keys in `engine/validator.yaml` and the three `data/settings/*.yaml` files replaced by bare keys (`agency_patterns`, `atmospheric_drift`). `compiled_patterns_for_family` plus `atmospheric_drift_for(family)` removed; consumers now use `compiled_patterns(section, key)` and direct attribute access. Three family helpers (`model_family_for_model`, `model_family_for_role`, `narrator_model_family`) plus the `model_family` field on `AIConfig` plus the `ai.model_family` config block removed. `get_prompt(name, role="...")` simplified to `get_prompt(name)`; 25-plus callsites stripped. ARCHITECTURE.md section "Role, model_family resolution layer" removed; CONTRIBUTING.md rewritten to "switching to a different model means re-tuning the prompts and pattern lists in place, not adding parallel variants." 21 family tests removed from `test_config_loader.py`, `test_prompt_loader.py`, and `test_pattern_family_resolution.py` (that last whole file removed).

Strict-rule violations fixed on our own perimeter. Two `or []` fallbacks that had slipped into the RESULT INTEGRITY implementation removed: `consequences=consequences or []` and `consequence_events=consequence_events or []` in `ValidationContext.build`. `Sequence[X] = ()` defaults used for empty-collection defaults — strict-rules compliant and mypy clean. `validate_and_retry`, `narrate_scene`, `apply_post_narration` brought into the same style; `finalize_scene` in `scene_finalization.py` cascade fix. 1225 tests green (1245 before cleanup, -21 family tests, +1 phrasings symmetry). Ruff clean, ruff format clean on 181 files, mypy clean on 105 source files. Save format unchanged.

---

## [2026.04.27.5] — 2026-04-27

Elvira batch output structure cleaned up. Session files had so far been written to `tests/elvira/elvira_session_<YYYYMMDD_HHMM>.json` with minute precision in the timestamp. In a fast batch (nine sessions of five turns) several runs finished within the same minute, after which `.write_text()` overwrote the earlier file. Three of the nine `explorer` sessions were lost this way in a recent batch measurement; the aggregated data in `batch_report.json` survived, the turn-by-turn data did not.

Filename enriched with setting and style — `elvira_session_<setting>_<style>_<YYYYMMDD_HHMMSS>.json`. Three × three batches now produce nine unique names based on content, not timing. Second resolution stays as a second layer for future parallel runs. All output (nine session files plus `batch_report.json`) goes to a new `tests/elvira/runs/` subdirectory; the batcher deletes that directory and rebuilds it at every start. One directory to zip, one directory to throw away.

In-scope rule fixes in the touched files. Three `game_cfg.get("load_existing")` violations in `runner.py` and `ws_runner.py` changed to direct subscript — `load_existing` is a required key in `elvira_config.yaml`. One `setting_id = game_cfg.get("setting_id", "")` in `_setup_game` rewritten to direct subscript plus an explicit `if setting_id == ""` guard for the auto-mode random-roll opt-in (no silent default; a documented protocol token). Four `cfg.setdefault("game", {})["..."]` patterns in `elvira_batch.py` changed to direct subscript on required yaml sections. Two dead `or ["starforged"]` fallbacks removed — `list_packages() if s != "delve"` yields at least three settings, so the fallback was unreachable. The `--output` CLI argument removed: it only overrode the report path while the subdirectory was wiped anyway, which made for a half-dead contract. `args.styles or ALL_STYLES` patterns replaced by `args.styles if args.styles is not None else ALL_STYLES`, so an empty explicit list is not silently replaced by the defaults. One `self.config.get("game", {}).get("setting_id", "")` in `models.py::SessionLog.to_diagnostic_dict` changed to direct subscript on the same grounds. Dead `_HERE` in `ws_runner.py` removed; in `runner.py` inlined as a direct `RUNS_DIR` building block.

Save format unchanged. 1234 tests green, ruff clean, ruff format clean, mypy clean on 105 source files. Four files touched: `tests/elvira/elvira_batch.py`, `tests/elvira/elvira_bot/runner.py`, `tests/elvira/elvira_bot/ws_runner.py`, `tests/elvira/elvira_bot/models.py`.

---

## [2026.04.27.4] — 2026-04-27

A bundle of bug investigation, truncation diagnosis, and architectural tuning on RESOLUTION PACING and GENRE PHYSICS. Production bug in `web/serializers.py:211`: `opt.get("summary", "")` on truth options. For classic (Datasworn truths without a `summary` field) this delivered empty options to the UI and empty `game.truths` in the narrator prompt — the narrator got no world context on classic. Fixed with format tolerance: `summary` if present, otherwise `description`. Doc drift repaired: ARCHITECTURE.md says `atmospheric_drift_overlays` is required (may be empty), but the loader was lax. Made strict; classic.yaml and starforged.yaml got an explicit `atmospheric_drift_overlays: {}`. Three suspects from the handover (chaos_thresholds high/low, disposition_shifts missing loyal, prompt_abbreviations missing none) turned out to be deliberate design choices after reading their consumers — not bugs.

Truncation mystery solved. The "appears truncated despite complete" warnings were not about narrator truncation but about GLM-4.7 on Cerebras sometimes returning responses with literal `\u201c`/`\u201d` escape sequences (6 ASCII characters) instead of the actual Unicode characters. The player saw `\u201c` in the narration instead of `"`. A decoder added in `post_process_response` that replaces only literal `\uXXXX` patterns — idempotent, safe for JSON content. Four tests in `test_provider_retry.py`. Bonus: a hardcoded 500-char truncation in Elvira's `models.py` that cut narrations mid-word in session files removed — analysis now works on complete narrations.

Architectural fact_budget flow for RESOLUTION PACING. The validator never got to see what the narrator saw: the gate computation produced a `fact_budget` per target NPC (0/1/2 based on scenes_known, bond, and stance), but only the narrator used it. The validator judged without context and applied the default "max ONE extra" rule — while the narrator was sometimes allowed 2. A contradiction inside the validator prompt itself: the rule said "1 or 2 fine, 3+ violation", the example said "2 = violation". `ValidationContext` extended with `target_npc_name` and `fact_budget`. Passed via `narrate_scene` → `validate_and_retry` → the validator prompt's `<context>` tag. Both validator prompt variants (default + gpt_oss) revised to respect `fact_budget` strictly; examples labelled with `fact_budget=N` so rule and example are consistent. Three tests in `test_validator.py` for the pass-through plus an update of `MockProvider` so that `messages` also lands in the calls log.

GENRE PHYSICS narrator prompt adjustment. Concrete WRONG examples in both narrator prompts ("the iron bites", "the hinges cry out", "the wood mocks", etc.) were probably verbal priming — by showing these tokens prominently, the narrator activated exactly that pattern. Replaced by a categorical description: "verbs of pain or injury, voice, breath, will or intent, awareness applied to inanimate subjects". RIGHT examples kept (positive priming is wanted). The effect is only measurable in the next batch. 1234 tests green, ruff clean, ruff format clean, mypy clean on 105 source files. Save format unchanged.

---

## [2026.04.27.3] — 2026-04-27

Three problems from the v0.27.1 batch measurement (that is, the 2026.04.27.1 build) solved. v0.27.2 (not released) contained the two `world_shaping` fixes; this release bundles those with the RESULT INTEGRITY false-positive fix and the Elvira truth-summary fix from the invariant violations.

`world_shaping` added to `engine/move_outcomes.yaml` with a fitting mechanic: `momentum +1` on STRONG_HIT, `narrative` on WEAK_HIT, `pay_the_price` on MISS — matching the move mechanic (the player declares a new fact, dice decide whether the world accepts it). The Brain-output sanitizer in `_sanitize_brain_output` now consults both Datasworn moves and engine moves via a new `_move_roll_type` helper. Previously `world_shaping` (an engine move) was skipped by the sanitizer, after which the strict raise in `_execute_roll` crashed anyway.

The most important tuning fix: the `CONSEQUENCE COMPLIANCE` block in `validate_narration` was injected unconditionally, so on STRONG_HIT turns the LLM validator started literal word matching on consequence sentences such as *"finds an opening. The advantage shifts."* — while the narrator described the mechanical outcome in smoother prose ("a passage gapes open"). Result: 76 RESULT INTEGRITY false positives in the v0.27.1 batch. The block is now only injected on MISS and WEAK_HIT, consistent with the existing prompt instruction *"STRONG_HIT or dialog — skip RESULT INTEGRITY entirely"*. STRONG_HIT turns still get the other three checks (PLAYER AGENCY, RESOLUTION PACING, GENRE PHYSICS) — only the cost/event obligation is dropped.

Elvira `creation.py` line 143 did `chosen.get("summary", "")` on truth options. Classic-setting Datasworn truths, however, have only `description`, no `summary` — which resulted in 110 invariant violations per classic session (`truth has empty summary` × 11 truths × 10 turns). Replaced by direct access with format tolerance: `summary` if present, otherwise `description`. Both are real Datasworn fields, not a silent fallback. Three validator tests, one sanitizer test, two move_outcome symmetry tests in `test_yaml_symmetry.py` to catch this class of bug for good. 1224 tests green, ruff clean, ruff format clean, mypy clean on 105 source files. Save format unchanged.

---

## [2026.04.27.1] — 2026-04-27

Hotfix on the v0 release: 16 of 18 Elvira sessions ended with `engine_error`. 15× through a KeyError on `gather_information` in `prompt_shared._resolve_stance_category`; 1× through the strict raise on Brain `stat='none'` for `adventure/secure_an_advantage` after an empty player input. The Elvira report was not usable for a tuning comparison with the v6 baseline.

Root cause of the KeyError: the v0 release expanded `move_categories.yaml` from 8 to 92 moves and introduced `gather_information` as a sixth category, but two other yaml tables that use the same category set were not made symmetric. `engine/stance_move_buckets.yaml mapping` lacked `gather_information: gather_information`. `engine/position_resolver.yaml move_baselines` lacked `gather_information: 0`. Both added. Two redundant hardcoded fallbacks around the mapping removed: the `if move == "adventure/gather_information"` short-circuit in `_resolve_stance_category` and the `cat in (...) else "other"` collapse in `resolve_npc_stance`. The symmetric mapping now guarantees the right bucket; the redundant bookkeeping is gone.

Brain-output sanitizer added in `process_turn` directly after the Brain call. When Brain returns an action_roll move with `stat='none'` (a Brain error, not an engine error), the sanitizer routes the turn to the dialog path instead of crashing. The strict raise in `_execute_roll` stays as a second protective layer for when something bypasses the sanitizer. One warning log to the console, so Brain errors stay visible without cutting off the session.

New test module `tests/test_yaml_symmetry.py` with ten tests that enforce every form of this class of bug: every category in `move_categories.yaml` must appear in `stance_move_buckets.mapping`, `position_resolver.move_baselines`, `memory_emotions.base`, and `memory_result_text` (all three results); every bucket value from `stance_move_buckets.mapping` must exist in every `(disposition, bond_level)` cell of `stance_matrix`; every move from Datasworn plus engine_moves must pass through the whole stance pipeline without crashing. Five tests around the Brain-output sanitizer in `tests/test_engine_memories.py`. One existing test in `test_stance.py` rewritten from "defaults to other" to "raises KeyError" — strict-rules compliant, errors propagate. 1218 tests green, ruff clean, ruff format clean, mypy clean on 105 source files. Save format unchanged.

---

## [2026.04.27.0] — 2026-04-27

Two engine bugs fixed and validator/narrator tuning after the v6 baseline measurement. Bug A: `generate_engine_memories` built keys such as `other_dialog`, `combat_dialog` for the `roll=None` path on `ask_the_oracle` and `dialog_only=True` on a non-dialog move. Four asymmetric "is this a dialog turn" checks in `engine_memories.py` plus turn.py consolidated into two helpers, `is_dialog_branch` (pre-roll, for the turn loop) and `is_dialog_memory` (post-roll, for memory and scene context). In addition, `move_categories.yaml` expanded from 8 to 92 moves — previously 91% of all moves fell through to `"other"`, which also kept the `gather_information` stance resolution broken. Two new category keys (`gather_information_MISS/_WEAK_HIT/_STRONG_HIT`) added in `memory_emotions.base` and `memory_result_text` so the mapping range is symmetric.

Bug B: `_execute_roll` now raises a diagnostic `ValueError` when Brain returns `stat="none"` on an action_roll move, instead of `Unknown stat: 'none'` deep inside `get_stat`. Plus a turn guard: `process_turn` refuses to run on `game.game_over=True` with a readable RuntimeError — a second protective layer for when a caller (web handler, Elvira runner) skips the game-over check.

Validator tuning on three measured false positives. The body-press agency pattern (`(presses?|settles?|weighs?|hangs?|bears? down) ... your (chest|shoulders|ears|...)`) removed from `agency_patterns_universal` — it caught sensory impressions that the validator prompt itself marks as SAFE. The silver-lining pattern `but you ... (find|discover|...)` given a negative lookahead on `nothing|no|none|without`, so `but you find nothing` no longer counts as a positive outcome. Sundered Isles drift list pruned: `weep`, `weeping`, `shimmers`, `shimmering` removed — legitimate in a gothic-marine setting; `_overlays: {}` added as the architecture prescribes. Other drift words kept until an Elvira measurement proves they cause problems too.

Equivalence clause added to both `validator_system` variants in RESULT INTEGRITY: "the narrator may describe a consequence in different words; only the event must be present." One RIGHT example as an anchor. The narrator prompt (both variants) gets an explicit player-as-agent rule for WEAK_HIT and STRONG_HIT — the player must be the grammatical subject of the successful action; no WRONG example, to avoid pattern activation.

Twenty new regression tests in `tests/test_engine_memories.py` for the helpers, the KeyError paths, the turn guard, the stat=none detection, move-categories completeness, and memory yaml symmetry. 1205 tests green, ruff clean, ruff format clean, mypy clean on 105 source files. Save format unchanged. Not touched this session: RESOLUTION PACING (47 instances, ~30%) and GENRE PHYSICS anthropomorphisms (25 instances, ~16%) — they need an architectural approach (an NPC whitelist via the gate layer and removing WRONG examples from the prompt, respectively) and wait for a next measurement.

---

## [2026.04.26.6] — 2026-04-26

Drift hotfix in Elvira character creation. `tests/elvira/elvira_bot/creation.py` line 68 accessed `pkg.oracle_paths` as a dict (`.get("names", [])`), but `OraclePaths` has been a dataclass since v0.50. Every batch session crashed immediately in `_roll_name` on an AttributeError. Fix: direct attribute access (`pkg.oracle_paths.names`); the field is required on the dataclass, so the fallback semantics were wrong anyway. Smoke-tested against all three settings (classic, starforged, sundered_isles); no unit test added — it rolls randomly, and the real regression test is Elvira itself.

---

## [2026.04.26.5] — 2026-04-26

Elvira styles `chaosagent` and `balanced` dropped. Chaosagent did not simulate a real player but fuzz input (single-word actions, wrong NPC names, claims about events that did not happen) — an input distribution the production engine never sees, and its high violation counts skewed compliance reports without adding unique information. Balanced overlapped with the combined coverage of `explorer`, `aggressor`, and `dialogist` without a unique measurement. Three styles remain, each representing a real player archetype.

`tests/elvira/elvira_prompts.yaml` now keeps three style blocks. `tests/elvira/elvira_batch.py` lost the redundant `DEFAULT_STYLES` constant — `ALL_STYLES` is now the only source, and the help text is derived from the constant so the earlier drift ("default: all 5") cannot return. `tests/elvira/elvira.py` `--style` help text updated. `tests/elvira/elvira_bot/ai_helpers.py` `get_persona` now raises `KeyError` with a list of valid styles instead of silently falling back to `style_balanced` — strict-rules compliant, no silent substitution. Save format unchanged, no Python edits outside Elvira. 1187 tests green, ruff clean, ruff format clean, mypy clean on 105 source files.

---

## [2026.04.26.4] — 2026-04-26

Model-specific prompt variants filled in where the architecture supports them. `narrator_system_glm` added to `prompts/narrator.yaml`: language directive first, persona frame ("senior RPG narrator producing tight, physical second-person prose for a fictional creative-writing roleplay"), front-loaded MUST constraints (genre physics → player agency → consequence compliance → result integrity → npc speech), WRONG/RIGHT patterns at the bottom as support. `validator_system_gpt_oss` added to `prompts/validator.yaml` in a section-structured pattern (INSTRUCTIONS / DEFINITIONS / VIOLATES (label 1) / SAFE (label 0) / EXAMPLES) with uppercase labels instead of markdown headers because of a project-rule conflict. Soft language ("generally", "usually", "may") explicitly forbidden in validator text. The universal variants stay as a fallback for other narrator and judgment models.

`prompt_blocks.py` fully config-driven. Nine block functions rewritten; all hardcoded XML wrappers, label strings, and format templates moved to 25 new keys in `prompts/blocks.yaml`. The narrative-direction token vocabulary (four for intensity, tempo, perspective, two for player, three for position) plus the wrappers for content_boundaries, character_state, tone_authority, vocabulary, world_truths, story_arc, revelation_ready, recent_events, campaign_history are now yaml. `get_narrator_system` passes `vocabulary_block` and `world_truths_block` as format vars instead of appending them at the end — so the yaml template can control their position. In the GLM variant they sit in the primacy zone directly after the hard MUST constraints; in the universal variant at the end, as in the old behaviour.

Same treatment for the Elvira bot. Five style personas (`explorer`, `aggressor`, `dialogist`, `chaosagent`, `balanced`) rewritten in a PURPOSE / ACTION RULES / OUTPUT structure with hard MUST language — "NEVER" and "Don't" replaced by "MUST NOT", soft language eliminated, output contract explicit per style. `burn_decision` split into a paired prompt: `burn_decision_system` ("answer with exactly one word") plus the user template. `tests/elvira/elvira_bot/ai_helpers.py` moved from hardcoded to yaml-driven: ten turn-directive texts, a rotation list, a MANDATORY-action-block template, a prev-action-block template, the complete `bot_turn_context` template, plus the "(unknown)" and "(none)" labels and the NPC/clock/track per-line formats. New `_p(key, **kwargs)` helper for type-safe yaml prompt resolution; `_resolve_turn_directive(turn)` reads the rotation list modulo the turn index. ARCHITECTURE.md drift fixed — three obsolete Qwen mentions replaced, the file-map description of `prompt_blocks.py` extended. No save-format changes. 1187 tests green, ruff clean, ruff format clean, mypy clean on 105 source files.

---

## [2026.04.26.3] — 2026-04-26

Test-suite maintenance: scope extension, reorganisation, coverage extension, performance. The eleven project-rule scans in `tests/test_project_rules.py` now also work over `tests/`, with carve-outs for pytest patterns (all inline imports allowed in tests; the dataclass-default scan stays `engine_config.py`-only). 35 `dict.get` domain-default violations and 3 `or` fallback patterns in test files fixed to direct subscript or an explicit if-else.

Two grab-bag test files dismantled: `tests/test_engine.py` and `tests/test_coverage.py` removed, their content distributed over focused files (`test_config_loader.py`, `test_validator.py`, `test_architect_validator.py`, `test_setup_common.py`, `test_provider_retry.py`) plus additions to existing files (`test_resolvers.py`, `test_parser.py`, `test_npc.py`, `test_director.py`). Shared mock infrastructure in the new `tests/_mocks.py` (MockProvider, MockResponse, make_test_game). Moves: five progress-track tests from `test_creation.py` to `test_track_lifecycle.py`, four CombatPosition tests from `test_move_outcome.py` to `test_models.py`, two track-finder tests from `test_move_outcome.py` to `test_track_lifecycle.py`. Imports cleaned up, a dead `if __name__ == "__main__"` block removed from `test_npc.py`.

Coverage from 81% to 88% via six new test files plus additions: `test_prompt_boundary.py` (10 tests, prompt_boundary.py 23→98%), `test_world.py` (29 tests, mechanics/world.py 58→99%), `test_story_state.py` (21 tests, story_state.py 51→98%), `test_json_utils.py` (10 tests, ai/json_utils.py 17→92%), `test_engine_loader.py` (7 tests, engine_loader.py 52→93%), `test_architect.py` (26 tests, ai/architect.py 28→97%), `test_chapters.py` (22 tests, game/chapters.py 37→74%), `test_game_start.py` (10 tests, game/game_start.py 54→94%), `test_web_handlers.py` (38 tests, web/handlers.py 31→50%). Plus 4 succession tests added to `test_succession.py` (game/succession.py 59→98%) and 3 run_tool_loop tests to `test_tools.py`.

Performance improvement in `test_project_rules.py`: a shared `_FILE_CACHE` plus `_load(path)` helper reuses parse + parents map + lines across the eleven scans. Previously every scan parsed every file again. The eleven separate `test_*` functions consolidated into one `test_project_rules` with eleven `_check_*` helpers — on failure the assertion groups all violations per category. Full pytest run from 10.9s to 8.4s (-23%). Test count 1019 → 1187 (+168 added, 11 rule tests merged into 1, no test removed from coverage). Save format unchanged. Ruff clean, ruff format clean, mypy clean on 105 source files, project-rule scan clean.

---

## [2026.04.26.2] — 2026-04-26

Comment and docstring sweep. All `#` comments and all docstrings removed from `src/`, `tests/`, and every yaml in `config.yaml`, `engine/`, `prompts/`, `emotions/`, `strings/`, `data/`, and `tests/`. 195 files touched, 6966 deletions against 799 insertions. Config bloat in `config.yaml` dropped from 40% comment lines to zero; roughly 47,000 tokens of docstring text that streamed along every time a file was read are gone. ARCHITECTURE.md and CONTRIBUTING.md took over the content that carried context in the codebase — a new paragraph "AI-call exception carve-out" in ARCHITECTURE holds the policy that used to be a module docstring in `provider_base.py`.

New `engine/tool_descriptions.yaml`, where the three director tools have their description strings; `tools/registry.py` reads them from yaml instead of from `__doc__`. Tests use a new `description=` override parameter on `register()` to register ad-hoc fixtures without a yaml change — production stays strictly yaml-driven. `CurrentAct` in `models_story.py` got a class-level `_NOT_SERIALIZED = True` opt-out, replacing the docstring escape that the SerializableMixin project rule used.

117 `# type: ignore` and `# noqa` directives worked away through real typing fixes. `_require()` in `datasworn/settings.py` split into typed `_require_dict` and `_require_str`; the three `pick()` helpers there replaced by typed variants (`pick_str`, `pick_int`, `pick_str_list`, `pick_bool`). `correction/orchestrator.py` now has correct `RollResult | None` annotations instead of `object`. `serialization.py` uses `TypeGuard[type]` for narrowing on the dataclass detector. No more hidden typing issues under ignore tape.

`tests/test_project_rules.py` revised: the now obsolete `test_no_banner_comments` and `test_no_untagged_todo_comments` replaced by `test_no_python_comments_or_docstrings` and `test_no_yaml_comments`, which stop regressions mechanically. `test_broad_except` lost the marker requirement (the carve-out list is sufficient). `test_inline_imports_only_in_whitelist` became a whitelist of ten legitimate circular-break imports. Dead helpers `_CARVE_OUT_MARKERS`, `_class_docstring`, `_except_has_marker` deleted. Save format unchanged. 1019 tests green, ruff format clean, ruff check clean, mypy clean on 105 source files, eleven project-rule scans clean.

---

## [2026.04.26.1] — 2026-04-26

Config-driven `(role, model_family)` resolution layer. Three model-specific layers — prompts, validator-regex pattern lists, and atmospheric-drift wordlists — now resolve via `cluster → model → family` from `config.yaml`. New `ai.model_family` mapping, three new helpers in `config_loader.py` (`model_family_for_model`, `model_family_for_role`, `narrator_model_family`), and a role-aware `get_prompt(name, role=...)` that prefers `{name}_{family}` and falls back to bare `{name}`. Twenty-five primary system/task/suffix prompts in seventeen call-sites pass `role=`; sub-blocks stay bare until a variant ships.

Validator-regex and atmospheric-drift adopt a uniform shape: a required `*_universal` list plus a required `*_overlays` dict keyed by family suffix. `EngineSettings.compiled_patterns_for_family` combines universal + overlay; `GenreConstraints.atmospheric_drift_for(family)` does the same for setting-yaml drift wordlists. No Python code carries a list of valid families — adding a new family (DeepSeek, Kimi, anything) is one row in `ai.model_family` plus optional yaml overlays. Qwen removed from the family mapping; only active models stay registered.

No content changes — every existing prompt, regex, and wordlist now sits under its `_universal` key, all tests still green. Save format unchanged. Test suite +23 (1019 total): 7 new family-helper tests in `test_engine.py`, 8 new prompt-loader tests, 9 new pattern-resolution tests including a yaml-only-new-family contract test. Ruff clean, mypy clean on 105 source files. ARCHITECTURE.md and CONTRIBUTING.md updated to document the resolution layer and the overlays-dict shape; the `What goes where` table in ARCHITECTURE gained the `model_family` row.

---



## [2026.04.26.0] — 2026-04-26

Roadmap step 5: Adventure Crafter primitives — themes, plot points, meta dispatch. New `engine/adventure_crafter.yaml` registers themes (action, tension, mystery, social, personal), theme_slots, theme_die_table, and special_ranges (Conclusion 1-8, None 9-24, Meta 96-100); `AdventureCrafterConfig` and `PlotPointRanges` dataclasses parse via the keyed_scenes-style nested block in `engine_config.py`. New `mechanics/adventure_crafter.py` ships `assign_themes`, `lookup_plot_point(theme, roll) → PlotPointResult(name, special_range)`, `lookup_meta_plot_point`, and `dispatch_meta` over a seven-handler dispatch table. `_load_ac_data` cross-validates the yaml `theme_die_table` against `data/adventure_crafter.json random_themes` on first load and raises ValueError on mismatch. The seven meta handlers stub with `NotImplementedError("wired in step 6")` to keep the dispatch shape testable without committing to step-6 signatures.

Spec-drift fix in 5.2: roadmap implied a flat d100 → entry table with theme-independent special ranges; the data shape disagrees because most of the 186 plot-point entries declare ranges on a subset of themes only, so lookup is `(theme, roll)` with theme-independent special-range flagging. Decision documented in roadmap Current state: AC `theme_translation` (the seven-key genre layer in `data/adventure_crafter.json`) deliberately not implemented — Datasworn `data/settings/*.yaml` already provides the genre layer through `vocabulary.substitutions` and `genre_constraints`, adding `theme_translation` would be a parallel layer at plot-weighting level without a measured drift problem the existing layer fails on (KISS + YAGNI). 81 new tests, 996 total green. Ruff, ruff format, mypy clean across 105 source files. Eleven project-rule scans clean. ARCHITECTURE.md updated: AC entry in module-ownership table, `mechanics/adventure_crafter.py` in file map, Key Design Decision paragraph for AC primitives. Test-count drift fixed in ARCHITECTURE.md and ORIGINS.md (816 → 996).

---

## [2026.04.25.2] — 2026-04-25

Roadmap step 4: keyed scenes. Engine-pre-defined narrative beats now override the chaos check at scene start. `KeyedScene` on `narrative.keyed_scenes` carries an id, trigger spec, priority, and narrative hint; `evaluate_keyed_scenes` priority-orders matches and `check_scene` consumes the highest hit, returning `SceneSetup(scene_type="keyed", ...)`. Priority order is `keyed > interrupt > altered > expected`. Five trigger types registered in `engine/keyed_scenes.yaml`: `clock_fills`, `threat_menace_phase`, `bond_threshold`, `chaos_extreme`, `scene_count`. `<keyed_scene>` block emits from `_pacing_block` with the wrapper template owned by yaml. `KeyedScene.__post_init__` validates `trigger_type` against the registered map so a buggy spawner cannot install a dead scene.

The step ships consumer-side only — no spawner. The Adventure Crafter (planned step 7) is the natural home for keyed-scene spawning when AC turning points and plot beats map onto engine triggers. Until then the list stays empty in normal play and the keyed branch is dormant. A placeholder `propose_keyed_scene` Director tool was considered and dropped to avoid building a function that would only exist to be reshaped one step later. The `thread_phase` trigger is similarly deferred to the thread-progress-tracks step where it gets a real consumer.

In-scope rule fixes on touched files. `SceneSetup.scene_type` lost its Python default; every construction site already passed it. Two silent fallbacks in `mechanics/scene.py` (`_lookup_adjustment` and `_roll_single_adjustment` returning `"increase_activity"` on missed table lookup) replaced with raises. The `entry.get("flags", "")` site in `engine_config.py::compiled_labeled_patterns` was rationalised by a comment claiming external-boundary status, but yaml under `engine/` is internal config — direct-subscripted to `entry["flags"]`, three callsite entries in `engine/validator.yaml` gained explicit `flags: ""` to opt out rather than omit. Save format breaks: `NarrativeState` gains `keyed_scenes`. No migration. NarrativeState snapshot captures the full list because mid-turn consumption can shrink it. 915 tests green (+28 in `tests/test_keyed_scenes.py`). Ruff, ruff format, mypy clean across 104 source files. Eleven project-rule scans clean.

---

## [2026.04.25.1] — 2026-04-25

Roadmap step 3: continue a legacy. When the protagonist dies (face_death MISS or both health and spirit zero) or is retired by the player, the campaign continues with a new protagonist in the same world. Two-phase lifecycle: `prepare_succession` archives the predecessor and locks in inheritance rolls onto `CampaignState.predecessors`, sets `pending_succession=True`. `start_succession_with_character` reads the locked rolls, closes the chapter, applies NPC carryover (active full / background half / lore half / deceased pruned, per `engine/succession.yaml`), keeps world-level threats and unresolved threads (vow-typed and creation-sourced threads drop), seeds the successor's legacy, replaces character, generates an opening. Locking rolls at archive time prevents reload-rerolls. New WebSocket messages: `retire`, `request_succession_creation`, `start_succession`. New UI: succession overlay (predecessor + per-track inheritance text), retire button with confirmation, locked setting in the successor creation form.

No-fallback sweep across the touched files. `_require_str` helper introduced in `web/handlers.py`; `handle_create_player`, `handle_select_player`, `handle_delete_player`, `handle_delete_save`, `handle_advance_asset`, `handle_start_succession` strict-validate required fields. `start_new_game` and `_replace_character_identity` direct-subscript required character-creation fields (player_name, pronouns, paths, backstory, background_vow); KeyError on absence, explicit empty-string raise on player_name and background_vow. WebSocket message-type validation strict in `server.py`. Datasworn JSON parsing direct-subscripts `_id`, `name`, `description`, `quest_starter` (always present per schema); only `summary` keeps an empty fallback (cross-setting). Two-sided removal of dead `default_player_name` (function, dataclass field, parser line, config.yaml entry, test fixture). Stripping the WebSocket-type validation pushed `websocket_endpoint` past the project complexity ceiling; decomposed into `_takeover_existing_session`, `_send_initial_state`, `_dispatch_one_message`, `_message_loop`. `ProgressTrack.TICKS_PER_BOX` ClassVar + `ticks_for_filled_boxes` helper extracted, three hand-coded `// 4` sites replaced.

Save format breaks: `CampaignState` gains `predecessors` and `pending_succession`. No migration. 887 tests green (+45 in `test_succession.py` and the new `TestSuccessionWebSocket` class). Ruff, ruff format, mypy clean across 103 source files. Eleven project-rule scans clean.

---

## [2026.04.25.0] — 2026-04-25

First CalVer release, and roadmap step 2: chapter-summary contradiction validator. After `call_chapter_summary` writes the AI narrative, the new `ai/chapter_validator.py` checks its claims against the engine's mechanical state snapshot. Two passes: a deterministic rule pass scans named NPCs/tracks/threats paired with status-shift keywords (death, completion, resolution); an LLM pass on the new `chapter_validator` AI role catches euphemisms the rule pass cannot interpret. Both passes feed one retry loop that re-invokes `call_chapter_summary` with the correction passed through `epilogue_text` — the only free-text channel the call already accepts. Exhausted retries keep the last narrative with a warning logged. AI-invented colour (entities not in state) is unconstrained by design.

New surfaces: `ai/chapter_validator.py`, `engine/chapter_validator.yaml` (max_retries plus three keyword sets), `ChapterValidatorConfig` dataclass, three `chapter_*_contradiction` violation templates added to `engine/rule_validator.yaml`, three new prompt entries in `prompts/validator.yaml` (system, user, correction_intro), and the `chapter_validator` role registered on the analytical cluster in `config.yaml`. `_close_previous_chapter` in `game/chapters.py` wires the validator between AI call and snapshot fusion. The carve-out whitelist in `tests/test_project_rules.py` gains `engine/ai/chapter_validator.py`.

Documentation cleanup also shipped this release. Four feature-claims in the md-files were factually wrong against the codebase or the upstream licenses, and have been corrected: SECURITY.md pointed at `prompt_builders.py` which has not existed since 0.73 (replaced with the actual prompt-assembly modules); ARCHITECTURE.md hardcoded "63 subsystem dataclasses" which had drifted (now unspecified, lifecycle-stable); README.md mis-stated three license terms (Datasworn rulesets are CC BY 4.0 except sundered_isles which is CC BY-NC-SA 4.0; Mythic GME 2e and Adventure Crafter are CC BY-NC 4.0 via the formal Word Mill Games non-commercial license at wordmillgames.com/license.html, not "no license"; Blades in the Dark / Forged in the Dark SRD is CC BY 3.0). README also gains an explicit note that the AGPL on the engine code does not override the NC clauses on the bundled NC data — the project as a whole can only be redistributed non-commercially while those data files ship together. CONTRIBUTING.md gains a Project rules section that documents the absolute rules (raise-on-miss, errors propagate, no backwards compatibility, two-sided removal) explicitly rather than leaving them implicit in `tests/test_project_rules.py`. CHANGELOG gains a Versioning section explaining the move from running-counter `0.x.y` to CalVer.

Test suite: 842 tests green (+26 new in `tests/test_chapter_validator.py`, covering each rule-pass detector, invented-colour false-positives that must NOT trigger, deceased-NPC-with-death-keyword pass-through, word-boundary safety, LLM-pass via mock provider, retry-loop convergence and exhaustion). Eleven project-rule tests green. Ruff, ruff format, mypy clean across 101 source files. No saves break — `chapter_validator` config is purely additive, no existing dataclasses changed shape.

---

## [0.75.0] — 2026-04-25

No-Python-defaults sweep, plus a typed-config push. The audit document on hardcoded defaults — groups 1 through 5 — applied in one session. Group 1: two AI-call fallback dicts (`call_opening_setup`, `call_narrator_metadata`) now read empty-collection placeholders from `engine/ai_text.yaml` under `narrator_defaults`, matching the 0.74.0 chapter_summary pattern. Group 2: dead defaults removed from `ThreatEvent`, `ClockEvent`, `NarrationEntry`, plus `ClockData.trigger_description`, `ThreatData.description` (and `.new` factory), `FateResult.question`, `RollResult.match`, `SceneLogEntry.scene_type` made required; `resolve_fate_chart` / `resolve_fate_check` / `resolve_fate` gained a required `question` parameter. One latent bug fixed in passing: `tick_threat_clock` was creating its `ClockEvent` inside the `clock.fired = True` branch but defaulting `triggered=False` — now `triggered=True` explicitly. Group 3: `ThreadEntry` and `CharacterListEntry` lost their domain defaults on `id`, `name`, `thread_type`, `source`, `entry_type`. Group 4: four resolver dicts moved from inline Python to typed config — `disposition_weights` and `position_weights` as new yaml mappings on `position_resolver` and `effect_resolver`, `_cond_checks` switched to direct subscript that raises on unknown override conditions, and a new `engine/stance_move_buckets.yaml` replaces the inline `{"combat": "combat", "social": "social"}.get(move_cat, "other")` map in `prompt_shared`. Group 5: defensive `gate_mem_counts.get(...)` removed in favour of direct subscript, and `default_cap` purged from `InformationGateConfig` after extending `stance_caps` with the 32 stances that previously fell through to it.

Audit point 2.9 deliberately skipped: `NarrativeState.scene_count: int = 0` is a legitimate runtime sentinel ("zero scenes elapsed pre-game"), parallel to `Resources` counters that start at zero, not a domain default that should move to yaml. Audit point 2.2 corrected against the document — the recommended `triggered=False` would have conserved the latent bug noted above.

Typed-config push beyond the audit. Eleven `get_raw` callsites converted to typed dataclass binding so mypy sees the config shape: `stance_bond_buckets`, `stance_move_buckets`, `stance_matrix` (with leaf-only `StanceMatrixEntry`), `time_progression_steps`, `narrator_status_descriptions`, `scene_adjustments`, `scene_context` (the two top-level keys merged into one nested block), `memory_emotions`, `memory_templates`, `validator`, `correction`. Nine other `get_raw` sites stay deliberately, motivated: their yaml-keys are themselves the domain data (move-names, dispositions, scene-types, templates indexed by move/result) and a dataclass would either break on every yaml extension or reduce to `dict[str, X]` with no typing win. ARCHITECTURE gains a Key Design Decision documenting this rule.

Test suite: 816 tests green, eleven project-rule tests green, ruff + ruff format + mypy clean on 100 source files. No new tests added — the existing suite covered every changed callsite via production-side assertions. README, ARCHITECTURE updated. Saves from prior versions are not loadable: `RollResult`, `FateResult`, `SceneLogEntry`, `NarrationEntry`, `ThreadEntry`, `CharacterListEntry`, `ClockData`, `ThreatData`, `ClockEvent`, `ThreatEvent` all changed shape.

---

## [0.74.0] — 2026-04-25

Chapter transitions made explicit. `ChapterSummary` now carries both the AI-written narrative fields and a deterministic engine-captured mechanical snapshot (progress_tracks, threats, impacts, assets, narrative.threads). All fourteen fields required — no defaults. `call_chapter_summary` returns the narrative dict only; `_close_previous_chapter` combines it with the engine snapshot. AI writes colour, engine writes canon; step 2 (chapter_validator) will check the AI text against the snapshot.

`_reset_chapter_mechanics` now zeros every chapter-spanning field instead of leaving some implicit; new `_restore_chapter_mechanics` replays the snapshot. Net behaviour identical to prior implicit carry-over, but adding a chapter-spanning field means touching three named places (capture, reset, restore) — no more "remember not to add it to the reset list". xp and legacy stay on CampaignState; NPC list and connection tracks carry via `game.npcs` unchanged. The AI-call fallback dict previously relied on dataclass defaults; the four empty narrative values now live in `engine/ai_text.yaml` alongside the existing fallback title/text keys.

Twenty-two new tests in `tests/test_chapter_summary.py` covering round-trip, required-field enforcement, reset+restore symmetry, snapshot immutability after live mutation, and fallback-path integrity. `tests/_helpers.py` gains `make_chapter_summary`. ARCHITECTURE.md updated with a Key Design Decision and module-table row. Saves from prior versions are not loadable. Delivery gate: 816 tests green (+22), ruff + ruff format + mypy clean on 100 source files, all 11 project-rule tests green.

---

## [0.73.0] — 2026-04-24

File splits and config-driven audit. Three oversized modules decomposed along intent lines: `turn.py` (761 lines) into `turn.py` (orchestration, 430 lines) + `action_resolution.py` (roll-consequence pipeline) + `scene_finalization.py` (post-narration) + `turn_types.py` (shared dataclasses); `prompt_builders.py` (629 lines) into `prompt_shared.py` (helpers reused by multiple builders) + `prompt_action.py` + `prompt_dialog.py` + `prompt_boundary.py` (new_game / epilogue / new_chapter); `move_outcome.py` (529 lines) into `move_outcome.py` (top-level resolver and dispatch) + `move_effects.py` (parser, 13 effect handlers, dispatch dict) + `move_handlers.py` (suffer / threshold / recovery). Every caller updated in the same commit; no re-export compatibility layers. Radon confirms average complexity stays A (4.15) over 765 blocks, no F/E/D-grade functions introduced, highest new C is `finalize_scene` at 19 (under the 20 ceiling).

Config-driven audit, category B — magic numbers. Eighteen hardcoded domain thresholds moved to yaml: bond/scenes_known bucket boundaries in `resolve_npc_stance` and `compute_npc_gate` (new `stance_bond_buckets.yaml` + `InformationGateBuckets` dataclass); `position_resolver` and `effect_resolver` bond thresholds; chaos adjust amounts for MISS/STRONG/dialog-hostile/dialog-friendly (extending `chaos.yaml`); time-progression label→steps mapping (new `time_progression_steps.yaml`); `threats.autonomous_tick_marks`; slice limits for consequences/NPCs in memory/scene-context (extending `prompt_display.yaml`); violation/examples/correction caps and word-length minima in `rule_validator.yaml`; filler-bond threshold and threads-in-context cap in `chapter.yaml`; description/word/name length minima in `fuzzy_match.yaml`; memory overlap scale factor in `memory.yaml`. The `move_category` resolver iterates over yaml keys instead of a hardcoded tuple. Ten dataclasses extended, every callsite converted to direct subscript or yaml-backed field access.

Config-driven audit, category A — hardcoded strings. Sixteen narrator-/AI-facing strings moved out of Python: the six scene-adjustment descriptions in `mechanics/scene.py` into a new `scene_adjustments.yaml`; the narrator-facing health/spirit/supply resource ladders (eighteen individual strings) into a new `narrator_status_descriptions.yaml` with a shared `_describe_narrator_resource` helper; the revelation-check user question into `prompts/brain.yaml`; the correction rewrite instruction, world-truths header, tone-authority body, character-state instruction, three story-ending variants, five status-flag labels, six result-constraint bodies and match-hints, crisis block, background-npcs prefix, and npc-evolutions hint into `prompts/blocks.yaml`; the new-chapter scene-context templates, NPC-agency action template, and clock-filled template into `engine/ai_text.yaml`. Category C produced one real fix (`_NPC_EDIT_ALLOWED` whitelist in `correction/ops.py` into a new `engine/correction.yaml`); three disposition/stance reconstruction dicts stay in Python because converting them would require restructuring nested yaml schemas for marginal gain. Category D (legacy fallback branches) found zero hits — the 0.70/0.71 dead-code passes had already cleaned it. Category E (hardcoded paths) found two low-risk hits (Mythic data filename, user-data format filenames) intentionally left alone as structural anchors.

What did not get touched in this pass: the C-grade functions that sit at or near the complexity ceiling of 20 (twelve functions at 18–20 branches, six at 15–17, thirty-eight at 11–14) — all acceptable under the current project rule but the first candidates if the ceiling is ever lowered. The three category-C borderline cases (position/effect resolver disposition dicts, `_resolve_stance_category`) remain visible as minor debt with motivation recorded in the audit report. ARCHITECTURE.md was updated inline for the new file layout (turn/prompt/move splits); CHANGELOG history references to the old filenames remain untouched as historical record. Delivery gate: 794 tests green, ruff + ruff format + mypy clean on 100 source files (+8 from 0.72.0 due to the splits), all 11 project-rule tests green.

---

## [0.72.0] — 2026-04-24

Complexity refactor. Six F-grade functions (41+ branches) and eleven E/D-grade functions (21–40 branches) decomposed into named phase-helpers. `process_turn` drops from F(69) and 344 lines to a thin orchestrator over ten phase functions; `fuzzy_match_existing_npc`, `resolve_position`, `activate_npcs_for_prompt`, `_apply_correction_ops`, and `process_correction` all out of F-grade. Eight D-grade functions — including `build_action_prompt`, `build_narrative_status`, `resolve_consequence_sentence`, `find_npc`, `call_story_architect` — decomposed the same way. Zero F/E/D-grade functions remain in the codebase; average complexity is A (4.17) over 765 blocks.

Unused parameters removed. Eleven function signatures carried arguments that no body read: `config` on four prompt/validator/director functions, `label` on `register_extracted_npcs`, `move` on `advance_menace_on_miss` and `_is_move_available`, plus dead `EngineConfig` and `Move` imports that existed only to type those removed arguments. Two web-handler parameters (`_session`, `_ws`) underscored to signal dispatch-contract conformance; `create_message(extra_body=...)` in `provider_anthropic.py` gets an inline comment explaining why it stays in the Protocol signature despite an unused body.

Orphan yaml deleted. `engine/monologue_detection.yaml` and `engine/recovery.yaml` — both documented as removed in 0.70/0.71 but still on disk — deleted. Two pure pass-through wrappers inlined: `normalize_disposition` in `npc/lifecycle.py` now re-exports directly from `emotions_loader`; `build_ui_strings` in `web/serializers.py` inlined into its single call site.

What did not get touched in this pass: file-level splits (turn.py at 761 lines, prompt_builders.py at 629, move_outcome.py at 529 are next), a genuine config-driven audit for hardcoded strings and legacy fallback paths in Python that belong in yaml, and the remaining C-grade functions (11–20 branches, acceptable but decomposable). New project-rule added to protect the refactor: `test_no_function_exceeds_complexity_ceiling` fails on any function with cyclomatic complexity above 20 (D-rank or worse), mechanically preventing a future session from reintroducing F/E/D-grade mammoths. Delivery gate: 794 tests green, ruff + ruff format + mypy clean on 92 source files.

## [0.71.0] — 2026-04-20

Third dead-code pass. The `momentum:` and `recovery:` yaml blocks claimed to drive momentum gain and recovery healing via per-tier tables, but nothing read them — action-move momentum lives in per-move outcome text parsed at runtime, and recovery amounts are per-move parameters in `move_routing.yaml`. Meanwhile `apply_suffer_handler` in `mechanics/move_outcome.py` hardcoded `+1` and `-1` momentum plus their label strings, exactly the values the abandoned yaml pretended to govern. The yaml lied, the code drifted, neither side knew.

The fix names what the code does. `MomentumGain` becomes `SufferRecoveryGain` with `strong_hit_gain` (momentum awarded when track recovery is unavailable on a strong hit) and `weak_hit_exchange_cost` (momentum spent to convert a weak hit into +recovery). `MomentumConfig` keeps `floor`, `max`, `start`, gains `suffer_recovery: SufferRecoveryGain`; `gain` and `loss` are gone. `RecoveryConfig` is removed entirely; `engine/recovery.yaml` deleted; `engine/momentum.yaml` rewritten. The three hardcoded sites now read from the config, and labels format via f-string from the same values. Bycatch: `NpcConfig.max_observations` removed from dataclass and `engine/npc.yaml`; its only mention was a stale docstring referring to a consolidation parameter the algorithm no longer uses.

The other ~17 vulture hits stay. They all failed the dual-side test — false positives where reads happen via dict-assignment, getattr, fixture access, or schema generation, or Python-only runtime event fields with no yaml counterpart. `THREAT_CATEGORIES` has no consumer that would read it from yaml; `antagonist_force`, `arc_notes`, and `ChapterSummary.scenes` are live through patterns vulture cannot see; `ticks_added`, `autonomous`, and `meaning_table` are runtime event fields, not configuration. Delivery gate: 793 tests green, ruff and ruff format clean on 147 files, mypy clean on 92 source files.

## [0.70.0] — 2026-04-20

Second dead-code pass, finishing what 0.69 left in "borderline case" territory.

`check_consequence_keywords` removed. A test comment ("Consequence checking moved to LLM validator") proved the function had been intentionally cut from `run_rule_checks` in an earlier refactor; the function, its `_consequence_stems()` helper, three dedicated tests, the `consequence_sentence_preview` dataclass field + yaml key, the `consequence_missing` violation template, the `consequence missing:` rewrite-instruction, and 141 lines of `consequence_stems:` yaml data all gone. `reload_config` kept: `tests/model_eval/eval.py` is an actively maintained standalone CLI for per-role model evaluation and uses it legitimately.

Duplicate provider code extracted. `provider_base.py` now exports `normalize_stop_reason(raw, truncated_value, tool_use_value)` and `extract_usage(raw_usage, input_key, output_key)`; both providers use them. Each `create_message` lost twelve lines; the stop-reason and usage vocabularies stay provider-specific at the call site. The other two pylint-flagged duplicates (`build_action_prompt` calls in two sites, `AIResponse(...)` constructor) are not extracted — the first is pseudo-duplication (legitimate API call, local variables), the second is already the shared return path the extracted helpers feed.

Dead config scrub. Thirteen yaml-bound dataclass fields that no code reads are gone from both the dataclass definitions and the yaml files: `ChaosConfig.interrupt_types`, five `EnumsConfig` enum lists (`npc_statuses`, `memory_types`, `thread_types`, `story_structures`, `positions`), `FuzzyMatchConfig.min_phrase_length`, `NpcMatchingConfig.stt_phrase_length` + `alias_min_length`, `ActProgressConfig.recap_scene_max`, `DescriptionDedupConfig.richness_alias` + `richness_description`, `status_descriptions.clock.full`. `MonologueDetectionConfig` was dead in full — class, yaml file (`engine/monologue_detection.yaml`), and its wiring through `EngineSettings` and `simple_map` all deleted.

Delivery gate: 793 tests green (−3 from 0.69 for the removed consequence-keyword tests), ruff + ruff format + mypy clean on 92 source files.

---

## [0.69.0] — 2026-04-20

Dead-code sweep. Vulture + manual verification found 23 callables, one full data path, one yaml file and 92 source files' worth of small trims that had no runtime readers.

Removed callables: `clear_provider_cache`, `_nullable_int`, `clear_brain_cache` (only caller was the also-removed `reload_engine`), five `DataswornData` methods (`setting_type`, `license`, `oracle_collections`, `move_categories`, `condition_meters`, `faction_oracles`, `oracle_ids_in`), `reload_engine`, `_reset_mythic_cache`, `find_threat_for_vow`, the `has_acts` property, `reload_prompts`, `reload_strings`, `load_global_config` + `save_global_config` (and with them the now-unused `stat`, `asdict`, `yaml`, `GLOBAL_CONFIG_FILE`, `_cfg` imports), `get_stat_labels`, `get_logger`.

Removed data path: `roll_descriptor_focus` plus the full chain — two dataclass fields (`OraclePaths.descriptor_focus`, `_OraclePathsPartial.descriptor_focus`), one yaml parse branch, one `pick()` call at resolve time, and the `descriptor_focus:` keys in four setting yamls (`classic`, `starforged`, `sundered_isles`, `delve`). `starforged`/`sundered_isles` had actual data there; `classic`/`delve` were empty sentinels. Nobody read the result.

Removed yaml: `engine/move_routing.yaml` was a top-level section with no `get_raw` caller. Verified by dotted-path scan, not just string-literal scan, because `get_raw("section")` is a different access pattern from `["section"]` subscript. The same scan saved `engine/damage.yaml`, which I also initially removed — the `damage()` convenience function in `engine_loader.py` reads `eng().get_raw("damage")` via `damage("damage.miss.clock_ticks", position)` in `game/finalization.py`, and my first string-literal-only grep missed it because the literal `"damage"` was everywhere else too (method names, field names). Restored; lesson filed.

Duplicate-code extraction: `engine_loader`, `emotions_loader` and `prompt_loader` each had a near-identical "read all *.yaml in a directory, raise on duplicate top-level keys" merge loop. Hoisted to a new `engine/yaml_merge.py` module exporting `load_yaml_dir(directory, *, missing_dir_hint, value_filter=None)`. `prompt_loader` needed the post-merge type-filter branch because it logs-and-ignores non-string prompt values; the shared helper stays focused on merge semantics and prompt_loader does the filter in its own loop after merging. `tests/conftest.py` was importing the private `_load_merged` symbol directly — switched to `load_yaml_dir` at the two fixture call-sites.

Session autosave default: the last domain literal from 0.68's autosave cleanup. `web/session.py::Session` had `save_name: str = "autosave"` and a second `"autosave"` in `clear_game()`. Both now route through `eng().persistence.default_save_name` via a `_default_save_name` helper. The dataclass field uses `field(default_factory=...)` so `Session()` with no args still works for the thirteen test sites.

Two duplicate-code findings left untouched, by design. The action-prompt construction in `correction/orchestrator` and `game/turn` share nine lines with the same argument list — a real refactor, not this session's scope. And the `AIResponse(content=..., stop_reason=..., tool_calls=..., usage=...)` packing in `provider_anthropic` and `provider_openai` is superficially similar but the surrounding stop-reason mapping is provider-specific enough that extracting would weaken the adapter boundary rather than strengthen it.

Three regressions during the sweep, all caught by running pytest after each deletion. `set_backoff_sleep` was used by `tests/conftest.py` to skip retry backoff during the test run; removed then restored. The `has_game` property on `Session` had two dedicated tests; removed then restored. `_load_merged` in `engine_loader.py` was imported by `tests/conftest.py` fixtures; the refactor moved the logic to `yaml_merge.py` and the conftest was updated. Each regression traces back to the same failure mode: filtering grep output too aggressively and trusting the result over running the tests. After the first one I added a post-deletion pytest run to the loop; the later two still slipped because "no callers" is not the same as "no breakage" — it misses private-symbol imports and reflective access.

Borderline cases left for a human eye: `reload_config` is used only by `tests/model_eval/eval.py` (test-only utility — keep for model eval, remove if that script is also archaeology). `check_consequence_keywords` in `ai/rule_validator.py` has three direct test importers but zero production callers — either the production path that uses it was amputated at some point (bug, rule-validator missing a check) or the function always existed for tests alone (sloppy but harmless). Both left alone pending a decision.

Delivery gate: 796 tests green, ruff + ruff format + mypy clean on 92 source files.

---

## [0.68.0] — 2026-04-20

All four `test_project_rules.py` debt checks pass: the rule file had been right, the code needed to catch up.

Twelve `.get("key", <domain literal>)` sites and eight `X or "<literal>"` fallbacks removed. AI-response parsers (`result.get("pass", True)` in `validator.py` × 3 and `architect_validator.py`, `result.get("revelation_confirmed", True)` in `brain.py`, `act.get("phase", "?")`) now read keys strictly; the existing `except Exception` graceful-degradation handlers own the "what if the response is malformed" policy instead of hiding it in a `.get` default. Schemas in `ai/schemas.py` now carry a JSON-Schema-standard `title` seeded from a new `ai_text.schema_titles` block; `provider_openai.py` reads it strictly, and `provider_openai.py`'s fallback on `"response"` turned out to be 100% dead code. `CHAPTER_SUMMARY_OUTPUT_SCHEMA` became `get_chapter_summary_schema()` because titles resolve through `eng()`. Narrator-facing fallbacks (`transition_trigger or "?"`, `current_location or "?"`, `split_name or "Unknown"`, `disposition or "neutral"`, `time_label or "?"`) read from `ai_text.narrator_defaults` and a new `npc.default_new_npc_disposition`. Three TF-IDF divide-by-zero guards rewritten as explicit `if ... else` so the rule-test's arithmetic carve-out recognises them.

Twelve broad-`except Exception` sites in `web/` got policy-marker comments on the first line inside the handler body (that is where `_line_has_marker` reads). `engine/correction/analysis.py` was added to the AI-call carve-out whitelist in the test — a straight oversight after the 0.59 `correction.py` → `correction/` package split. Twenty-three inline imports: eleven had no cycle to break and were hoisted to module top (`re`, `types`, `shutil`, `stat`, `urllib.parse` plus six package-internal symbols that were already top-level elsewhere); twelve genuine circular-breaks and optional-SDK lazy-loads now carry a `# circular:` or `# lazy:` marker on the immediately preceding line.

Dead code deleted: `src/straightjacket/engine/correction.py` sat next to the `correction/` package that superseded it in 0.59. Import resolution picked the package; the file had been unreachable for nine versions. Stale references in `provider_base.py`, `game/finalization.py`, `game/momentum_burn.py` and the rule-test's carve-out whitelist updated.

Off-scope bugs caught in passing. `config_loader.py::_read_version` silently returned `"0.0.0"` if `pyproject.toml` was missing or the version line did not match — a silent domain default the AST scanner could not catch. It now raises `RuntimeError`. The `save_game` / `load_game` `name: str = "autosave"` defaults were dead code (every caller passes an explicit name) and are gone; the autosave slot name is now a first-class config value via a new `engine/persistence.yaml`, `PersistenceConfig` dataclass, and `eng().persistence.default_save_name`. `test_process_new_npcs_uses_oracle_name` was patching `npc.naming.roll_oracle_name`, which only worked when the import was inline; after hoisting it patches the name at its rebind site — `npc.processing.roll_oracle_name`.

Delivery gate: 796 tests green (+4 from 0.67), ruff + ruff format + mypy clean on 91 source files.

---

## [0.67.0] — 2026-04-20

Two file splits triggered by a codebase-size audit. `correction.py` (461 lines) became a package: `orchestrator.py` (process_correction, snapshot restore), `ops.py` (atomic NPC/location/time/backstory patches), `analysis.py` (the correction brain call), and `__init__.py` that re-exports the three public names. The three-file layout is internal; consumers still import from `straightjacket.engine.correction`.

`engine_config.py` (1139 lines) split into two files: `engine_config_dataclasses.py` (739 lines) now holds the 63 subsystem dataclasses plus the `MoveAvailabilityCondition` type-alias, while `engine_config.py` (478 lines) keeps `EngineSettings` and the `_build_strict` / `load_strict` parse logic. All 64 names are re-exported explicitly from `engine_config.py` via a named import list rather than a star-import, so the public API stays identical without introducing implicit exports.

Module coupling measurement taken along the way: 76 modules, 434 local-import edges, average out-degree 5.7, heaviest importers are orchestrators (turn.py 20, correction 19), heaviest imported modules are infrastructure (logging_util 49, models 45, engine_loader 44). No feature-module god-object; the graph is flat.

Delivery gate: 786 existing tests green, ruff + ruff format + mypy clean on 91 source files. The four failing `test_project_rules.py` checks remain the unchanged debt measurement.

---

## [0.66.0] — 2026-04-20

Elvira gains three new diagnostic layers, all dumped into the existing `elvira_session.json` so there is still one file to hand to Claude after a run.

Two new per-turn invariants in `tests/elvira/elvira_bot/invariants.py`. First: NPC presence in `GameState` must match NPC presence in the SQLite read model. Drift between the two causes prompt-builders and tool-handlers to see stale data while production code sees live data — the same class of bug as the 0.47 `characters_list INSERT OR REPLACE` crash. The check skips when the db is empty (unit-test contexts that call `assert_game_state` directly without running the turn pipeline that calls `sync(game)`), so it only flags real divergence after a real sync. Second: `world.combat_position` and active combat progress tracks must be consistent — an `in_control`/`bad_spot` position without an active combat track, or a cleared position with orphan active combat tracks, both signal the combat lifecycle has leaked state.

New `tests/elvira/elvira_bot/drift_checks.py` runs two post-run analyses whose output lands under a new `drift_summary` key in the session log. Validator balance counts how many violations came from the rule-validator (`[rule]` prefix) versus the LLM-validator (`[llm]` prefix) across all turns and all retry attempts. A run with 20+ total violations where one side contributes under 10% is flagged as suspected drift — the same pathology that slipped past fourteen versions of testing in v0.63 when a hardcoded label in the secret-stripping regex had silently stopped matching. Blueprint drift re-runs the architect_validator's atmospheric_drift wordcheck against the stored blueprint, post-hoc and independent of whatever the architect_validator decided at creation time. Returns the actual offending words and the field they came from so you can see which act or which thematic field produced them.

`drift_summary` is wired into both `runner.py` (direct mode) and `ws_runner.py` (full-stack mode), emitted in `to_diagnostic_dict`, and naturally present in the full debug dump.

Delivery gate: 786 existing tests green, ruff + ruff format + mypy clean on 90 files. The four failing `test_project_rules.py` checks from 0.65.0 remain the measurement of debt, unchanged. Not verified: these additions have not been run against a live Elvira session with an API key — that is the first thing to do next session.

---

## [0.65.0] — 2026-04-20

New `tests/test_project_rules.py` runs ten AST/regex scans that enforce the absolute rules mechanically. Six pass against the current codebase, four fail and measure residual debt: 12 `.get("key", <literal>)` domain defaults (including three `result.get("pass", True)` in the AI validator where malformed responses register as passing), 7 `X or "literal"` fallbacks, 11 broad `except Exception` handlers in web/ and provider_base.py without the policy-marker comment the convention requires, and 23 inline imports without reason comments — the 0.64.0 changelog claimed "roughly a dozen, each carrying a comment"; the actual count was almost double and none in the sample inspected carried a marker.

Documentation fix: new ARCHITECTURE.md paragraph makes the subpackage `__init__.py` re-export convention explicit. `mechanics`, `npc`, `game`, `db`, and `tools` are public API facades (46 consumers of `mechanics`, 20 of `npc`); top-level `engine/__init__.py` is not; `models.py` is a deliberate hub. Before, only `models.py` was documented — the rest was silent convention, and the F401 ignore list in `pyproject.toml` had no paper trail.

Delivery gate: 786 existing tests green, ruff + ruff format + mypy clean on 88 files. The four failing project-rules tests are the measurement, not a broken suite.

---

## [0.64.0] — 2026-04-20

Full sweep of the v0.63.0 audit. Ten batches covering hardcoded narrator/UI strings, silent error suppression, half-wired features, magic truncation numbers, SQL schema drift, inline-import hygiene, orphan config keys, test isolation, and cosmetic noise. A handful of live bugs surfaced while sweeping and were fixed in passing.

Hardcoded strings moved to config. Ten violation-message templates in `ai/rule_validator.py` now live in `engine/rule_validator.yaml` under `violation_templates`; the category prefixes ("PLAYER AGENCY:", "IMPACT CHANGE:", etc.) stay as stable labels so downstream substring matching keeps working. Ten threshold dictionaries in `web/serializers.py` (`_HEALTH_DESC` through `_MENACE_DESC`) moved to a new `engine/status_descriptions.yaml` with a typed `StatusDescriptionsConfig`. Five error strings from `web/handlers.py` and `web/server.py` live in `strings/error.yaml`. Two prompt-structural replacements in the retry-strip path moved to `validator.yaml` under `retry_strip`. The hardcoded `"morning"` fallback in `ai/narrator.py` now reads `narrator_defaults["unknown_time"]` from `ai_text.yaml`. The vow-ranks list in `build_creation_options` is derived from `eng().legacy.ticks_by_rank.keys()` instead of hardcoded.

Silent error suppression cleaned up. `persistence.list_saves_with_info` no longer papers over corrupt save files with placeholder records — it skips them with a warning and a new test exercises the path. Four sites in `user_management.py` replaced bare `except Exception: pass` with narrow filesystem-exception clauses and warning logs. Three `contextlib.suppress` / `except Exception: pass` sites in `web/handlers.py` and `web/server.py` became typed catches on `WebSocketDisconnect / RuntimeError / OSError` with logs that explain why the swallow is acceptable (dead socket, stale client, invariant-transition race).

Pay-the-price consumer wired up. The feature had been half-built for several versions: `OutcomeResult.pay_the_price` was being set, the yaml referenced the effect, tests checked the flag, but no code actually rolled the oracle or passed the result to the narrator. New helper `_roll_pay_the_price` picks a random line from `engine/pay_the_price.yaml`, substitutes `{player}`, and appends it to `result.consequences`. Wired into both write sites (`apply_effects` and `apply_recovery_handler` miss branch). Narrator now sees the chosen consequence as a regular `<consequence>` tag and the rule-validator checks for reflection.

Magic truncation numbers consolidated. Thirty-five `[:N]` slice sites across logs and prompts (`N` in {40, 60, 80, 100, 120, 200, 300, 500, 600, 1000, 2000, 4000}) now read named keys from `engine/truncations.yaml` via a new `TruncationsConfig`: `log_xshort/short/medium/long/xlong`, `prompt_xshort/short/medium/long/xlong/xxlong`, `narration_preview`, `narration_max`. The `log_truncate_*` fields moved out of `architect_limits` where they didn't belong. The dead `retry.max_retries: 2` key (never read in production) was replaced with `constraint_check_max_retries: 1`, which the three sites that previously hardcoded `max_retries=1` overrides (validator, architect-validator, tool-handler) now consume.

SQL schema aligned with the `sync.py` insert contract. Every `DEFAULT` clause on data columns was dropped — `sync.py` is the sole writer and always provides every column, so DEFAULTs were dead code that hid bugs. `scene_type` had an odd inconsistency (no `NOT NULL`, double-quoted literal) that got fixed in the same pass. A genuine bug surfaced: `SceneLogEntry.oracle_answer` was present in the dataclass, serialised to savefiles, but absent from `schema.sql` and `sync.py` — so DB state and savefile state disagreed. Added to both for consistency.

Inline imports swept. From 154 function-level imports across the codebase down to roughly a dozen, each of those now carrying a comment explaining why it can't be top-level: `models.py → db` is a genuine cycle (db queries import models); `npc/lifecycle.py → mechanics` is another (mechanics.consequences imports find_npc); `api_client.py` provider imports stay lazy so unused providers don't need their SDK installed. The rest got promoted. This surfaced and fixed a family of subtle bugs from ruff's auto-fix ripping top-level imports that it considered unused while inlines still existed — every such case is now either top-level-and-used or inline-with-comment.

Orphan strings scan found zero real orphans after accounting for html consumers, `get_strings_by_prefix` usage, and dynamic key construction (`handlers.py:451` builds `"advance.upgraded"` vs `"advance.acquired"` at runtime). The two supposed orphans were false positives; nothing to delete.

Test isolation hardened. New autouse `_reset_random` fixture in `conftest.py` reseeds `random` after every test — tests that call `random.seed(N)` for deterministic rolls no longer bleed their seed into subsequent tests. Shebang-before-imports in `test_engine.py` fixed.

Cosmetic pass: 83 unused shebangs removed from non-entry-point modules. 255 lines of section-banner comments (`# ─── NAME ───`) removed across the codebase. Trivial one-line docstrings left alone — judgment call; they're noise but some are close enough to borderline useful that a mechanical sweep would lose signal too.

Delivery gate: 786 tests green, ruff + ruff format + mypy clean on 87 source files.

---

## [0.63.0] — 2026-04-19

Two small audit batches (N — validator regex drift, and G — `_raw` direct access). What started as a cosmetic cleanup turned up a live latent bug along the way.

The secret-stripping regex in `ai/validator.py` hardcoded the literal label `"weave subtly,never reveal"`, a string that was supposed to mirror `secrets_label` in `prompts/blocks.yaml`. That yaml value currently reads `"MUST NOT reveal directly,weave across 3+ scenes"` — the two drifted apart at some earlier point and nobody noticed, because the existing tests fabricated their input using the old label, so the test suite kept matching itself. In production the regex never matched the real prompts; every retry on a pacing violation was running with NPC secrets left in the context block. The regex is now structural — `secrets\([^)]*\):\[.*?\]` — so it matches any parenthetical label. Tests for both the pacing-match and the agency-nomatch paths were rewritten to read `secrets_label` from yaml at test time.

The `_raw` audit called out two callsites (`ai/rule_validator.py`, `ai/validator.py`) that bypassed `EngineSettings.get_raw()` and reached into the private `_raw` dict directly. Both now go through `get_raw()`. A third site surfaced while sweeping — `engine_loader.damage()` itself was walking from `eng()._raw` root to support dotted-path lookups like `"damage.miss.clock_ticks"`. Split on the first segment and the rest of the path walks through `get_raw(first)` just fine, so that's now consistent too.

Delivery gate: 783 tests green in 4.3s, ruff + ruff format + mypy clean on 87 source files.

---

## [0.62.0] — 2026-04-19

Batch E from the v0.61.0 audit. Five domain enums that were hardcoded inside `src/straightjacket/engine/ai/schemas.py` and `src/straightjacket/engine/mechanics/fate.py` now live in `engine/enums.yaml` alongside the existing enum lists. `EnumsConfig` grew five fields: `tone_keys`, `correction_ops`, `correction_fields`, `dramatic_weights`, `odds_levels`. The schema builders read them via `eng().enums.<name>`.

`DIRECTOR_OUTPUT_SCHEMA` and `STORY_ARCHITECT_OUTPUT_SCHEMA` were still import-time module constants — the only two left after the v0.58 schema-builder refactor moved validator/revelation-check/architect-validator to lazy builders. Both are now `get_director_output_schema()` and `get_story_architect_output_schema()`. Their callsites in `architect.py` and `director.py` were updated, and a pre-existing function-level import of the old constant in `director.py` got promoted to the top of the file.

`fate.py`'s module-level `ODDS_LEVELS` tuple is gone; `get_odds_levels()` returns a tuple built from `eng().enums.odds_levels`. Test `test_fate.py` flipped the import, updated call sites to the function, and the two tests that iterate all odds now request the `load_engine` fixture.

One divergence surfaced and got fixed in passing. The correction schema advertised six editable NPC fields (`name`, `description`, `disposition`, `agenda`, `instinct`, `aliases`) while `_apply_correction_ops` in `correction.py` also accepted `status`. The allowed-set was the wider contract; the schema is now aligned to it, so the AI can propose `status` edits directly instead of the code silently accepting a field the schema never exposed.

Delivery gate: 783 tests green in 4.2s, ruff + ruff format + mypy clean on 87 source files.

---

## [0.61.0] — 2026-04-19

Batch F from the v0.60.0 audit. Dataclass-field defaults that duplicated yaml or hardcoded a domain enum are gone. `Resources` and `WorldState` got `from_config()` classmethods used as `GameState`'s default factories. `ProgressTrack` and `ThreatData` got `.new()` factories that read `max_ticks` from the new `progress.yaml max_ticks` key. `ClockData`, `FateResult`, `MemoryEntry`, `RandomEvent`, and the structural fields on `NpcData` are now required. `NpcData.introduced` flipped from True to False — fresh NPCs haven't been shown on screen. `CampaignState` legacy tracks read display names from `strings/status.yaml` and rank from `legacy.yaml`. `BrainResult.type/move/stat` became kw_only required; the brain-exception fallback and the correction null-brain sentinel supply them explicitly.

`db/schema.sql` dropped `DEFAULT` clauses on now-required fields and flipped `introduced` to 0. Dead `game.resources.health = ...` overrides in `game_start.py` are gone — `from_config()` already reads those keys. Two silent fallbacks found in passing: the `"neutral"` on `disp_to_emotion.get(...)` in `npc/processing.py` and the `"actions"` default on `roll_meaning_table()` both raise now.

Tests: `tests/_helpers.py` grew from one helper to nine, one per dataclass, holding test-only defaults like `"dangerous"` rank and `"neutral"` disposition. 30 test files migrated to the helpers; tests that exercise specific values still pass their own kwargs. Production stays strict, test boilerplate lives in one place.

Delivery gate: 783 tests green in 3.8s, ruff + ruff format + mypy clean on 87 source files.

---

## [0.60.0] — 2026-04-19

Tranche 8 expanded: every yaml store in the repo is now modular. Callsites unchanged — each loader globs its directory, merges top-level keys, raises on duplicates.

`engine.yaml` (2165 lines) split into 58 files under `engine/`, one per subsystem, filename matching the section. Small siblings bundled where splitting would give one-key files: `npc.yaml` bundles npc/name_titles/npc_matching, `memory.yaml` the six memory sections, `architect.yaml` architect/architect_limits, `disposition.yaml` the two disposition maps, `scene_context.yaml` the two one-liners, `creativity_seeds.yaml` adds scene_range_default, `track_moves.yaml` the two track-move lists. Per-subsystem split chosen because tranches cluster that way (tranche 5 = move_availability only, tranche 6 = ai_text+architect, tranche 7 = stats only).

`emotions.yaml` (293 lines) split into `emotions/importance.yaml`, `keyword_boosts.yaml`, `disposition_map.yaml`. `prompts.yaml` (30 prompts) split into seven cluster-files under `prompts/`: brain, narrator, architect, validator, director, tasks, blocks. `strings.yaml` (142 keys) split into eighteen files under `strings/`, one per dotted-key prefix so translators edit one file at a time. `config.yaml` stays single — 62 lines, user-edited, not worth the usability hit.

One config rename: `ai.prompts_file` → `ai.prompts_dir` in `config.yaml` and `AIConfig`. One test-helper config followed. Session-cache behaviour preserved in `tests/conftest.py`.

Delivery gate: 783 tests green in 3.4 seconds, ruff + ruff format + mypy clean on 87 source files.

---

## [0.59.0] — 2026-04-19

Tranche 7: the five hardcoded stat fields on GameState (`edge`, `heart`, `iron`, `shadow`, `wits`) are gone. They duplicated `engine.yaml stats.names` in Python, carried the canonical 3-2-2-1-1 array as magic-number dataclass defaults, and had been flagged as a storage-schema migration since tranche 3. GameState now has a single `stats: dict[str, int]` field declared `kw_only=True` so it can sit among default fields while remaining a required kwarg — no default dict, no silent substitute for a missing character-creation state. `GameState.get_stat` reads from the dict and raises on an unknown or unset key. Save-file format breaks; there were no live saves to migrate.

One architecturally significant pre-existing violation got swept up. The Brain prompt in `ai/brain.py` rendered stats as a hardcoded `E{edge} H{heart} I{iron} Sh{shadow} W{wits}` f-string, duplicating the stat names a second time and hardcoding the English abbreviations. The abbreviations now live in a new `stats.prompt_abbreviations` yaml subsection (which also carries a field in `StatsConfig`), and `ai/brain.py` gained a `build_stats_line(game)` helper that iterates `eng().stats.names` and emits only stats that have an abbreviation. The stat named `none` has no abbreviation and is not rendered. The same helper is called from `tests/model_eval/eval.py` which had two copies of the same hardcoded template; they're gone. `tests/elvira/elvira_bot/runner.py` built a stats dict via attribute access on the five old fields — it now copies `game.stats` directly.

Tests got a `tests/_helpers.py` module with a single `make_game_state(**kwargs)` helper. It defaults to the canonical 3-2-2-1-1 array when a test doesn't pass `stats=` explicitly, so tests that don't care about specific stat values keep their minimal constructors. Tests that do care pass their own dict, which wins via setdefault. Roughly 125 `GameState(...)` call sites across 34 test files were migrated — 36 explicit stat-kwarg sites to the dict form, the rest to `make_game_state`. `GameState.stats` being a required kwarg in production means the helper is the only place the canonical test array is stated; production code (`game/game_start.py`) passes stats explicitly from validated creation data.

Delivery gate: 783 tests green in under 5 seconds, ruff + ruff format + mypy clean on 87 source files.

---

## [0.58.0] — 2026-04-19

Tranche 6: every hardcoded English string that ends up in an AI prompt, narrator output, or json_schema description now lives in `engine.yaml` under a new `ai_text:` section. Eight `TODO tranche 6` markers across the codebase are gone, plus roughly fifteen unmarked sites discovered along the way.

The new section has six dataclass-bound subsections. `brain_trigger_hints` carries the contrastive move descriptions Brain feeds the classifier. `schema_descriptions` holds the field-level `description=` strings injected into json_schema for the validator, revelation-check, and architect-validator outputs — these became lazy builder functions (`get_validator_schema()`, `get_revelation_check_schema()`, `get_architect_validator_schema()`) replacing the old import-time constants, and three callsites that still imported the old `VALIDATOR_SCHEMA`/`REVELATION_CHECK_SCHEMA`/`ARCHITECT_VALIDATOR_SCHEMA` constants were broken-but-untested before this release; they now call the builders. `consequence_labels` covers all thirteen narrator-facing templates produced by `move_outcome.py` — momentum changes, track gains and losses, mark-progress, clock fills, bond progress, disposition shifts, mark-impact, clear-impact, threshold vow — replacing roughly twenty-five inline f-strings across `apply_effects`, `apply_suffer_handler`, `apply_threshold_handler`, `apply_recovery_handler`, and `_apply_generic_suffer`. `validator_blocks` holds the wrapper text for the validator's correction-mode retry prompt, the `Fix: {violation}` fallback for unmatched violations, and the `<momentum_burn>` injection string used by `momentum_burn.py`. `narrator_defaults` collects the scattered placeholder strings that flow into AI prompts when game state is empty — `unknown_location`, `unknown_time`, `no_npcs`, `no_npcs_yet`, `no_npcs_nearby`, `no_roll`, plus the templated fallbacks `npc_appeared_event`, `unnamed_track`, `reflection_tone_fallback`, `default_act_mood`, `recap_fallback`, `chapter_summary_fallback_title`, and `chapter_summary_fallback_text`. `architect_labels` carries the three label fragments (`Forbidden terms`, `Forbidden concepts`, `Test`) that `architect_validator.py` concatenates into its constraint_text prompt.

Routes to the yaml: roughly eleven scattered `or "unknown"` / `or "(none)"` / `or "none"` defaults across `narrator.py`, `correction.py`, `prompt_builders.py`, `engine_memories.py`, `npc/processing.py`, `turn.py`, `director.py`, `momentum_burn.py`, and `architect.py` now read their fallback string from `eng().ai_text.narrator_defaults`. The two `or "?"` defaults in `web/serializers.py` and `director.py` stayed put — the former is an empty-state UI placeholder for the player status block (not config data), the latter only appears in a debug log line. Three pre-existing pieces of broken English that didn't carry TODO markers were swept up in passing: `correction.py`'s `"dialog (no roll)"` next to the `(none)` it sat alongside, `engine_memories.py`'s `"no one nearby"` next to the `or "unknown"` on the previous line, and `narrator.py`'s second-site `(none)` in the metadata-extractor prompt.

`architect.py` and `architect_validator.py` got the same treatment as the rest of the codebase, with their misleading "slated for deletion" docstrings removed along with the comment claim that magic numbers were "intentionally left hardcoded — fixing them would be wasted work before removal." Both files now use a new `architect_limits:` yaml section (twelve typed integer fields) for every truncation length and history window: recap log/narration/campaign windows, chapter-summary log window, and four log-truncation lengths. Architect_validator's three log-line magic numbers (`[:60]`, `[:5]`, `[:80]`) route through the same section; `drift_words_log_window: 5` was added for the previously inline `found[:5]`.

Two pre-existing inconsistencies surfaced and were fixed. The previous tranche renamed `memory_move_verbs._default` to `_catchall` in `engine.yaml` but left the callsite in `engine_memories.py:61` reading `verb_map["_default"]` — that branch would have raised KeyError on any move outside the explicit verb map, but no test exercised it. The schema-builder refactor in `schemas.py` replaced module constants with lazy functions and renamed the references from `VALIDATOR_SCHEMA` etc. to `get_validator_schema()` etc., but three lazy `from .schemas import ...` lines inside AI-call functions still pointed at the old names; tests passed because no test path reached those AI calls. Both classes of bug would have surfaced as runtime failures the first time a player triggered the affected paths in production.

---

## [0.57.1] — 2026-04-18

Test suite runs 16x faster — 49 seconds down to 3 seconds — with no test removed.

The `load_engine` and `stub_engine` fixtures in `tests/conftest.py` were function-scoped, which meant every test that used them reparsed the 82KB `engine.yaml` from scratch. Measurement showed that 427 tests each spent ~100ms in setup, totalling 44 of the 49 seconds. The actual test logic across 783 tests ran in under a second.

Fix: session-scope the yaml parse behind two hidden fixtures (`_real_engine`, `_stub_engine_instance`). The per-test `load_engine` and `stub_engine` fixtures now just pointer-swap the cached instance into `engine_loader._eng`. A duplicate `load_engine` fixture in `test_web.py` was updated to use the same session cache.

Safe because no test mutates `eng()` after installing it — they only read from the config snapshot.

---

## [0.57.0] — 2026-04-18

Tranches 4 and 5: yaml-internal naming cleanup, and move availability rules moved from Python into `engine.yaml`.

Tranche 4 reviewed six `_default` entries in `engine.yaml`. `time_progression_map._default` is a real resolver fallback and was renamed to `_catchall` (with the callsite in `resolvers.py` updated) so the naming matches the semantics. `narrative_direction.result_map._default` turned out to be dead — no callsite ever read it, the resolver raises on unknown keys — and was removed outright rather than renamed as the handover suggested. `move_verbs._default` is narrator-facing text and stays for tranche 6. The remaining three were already correctly named.

Tranche 5 moved the 77-line `_is_move_available` rule table in `tools/builtins.py` into a new `move_availability:` section in `engine.yaml`. Every rollable move across Classic, Delve, Starforged, and Sundered Isles is listed explicitly; unlisted keys raise. Each entry is either `{never: true}` (reactive moves that are never player-initiated) or `{available: [<conditions>]}` where conditions combine named boolean flags and combat-position checks. Three new condition dataclasses (`FlagCondition`, `NotFlagCondition`, `CombatPosCondition`) plus `MoveAvailabilityRule` in `engine_config.py`; the Python function is now a thin yaml-driven evaluator. Before extraction, the Python was cleaned up: a dead duplicated branch in `scene_challenge`, several redundant `return True` statements, and a stale delve comment referencing unimplemented site-state were removed.

---

## [0.55.0] — 2026-04-18

Tranche 3: data tables that lived only in Python moved to `engine.yaml`. Silent fallbacks found alongside now raise.

Progress-track ticks-per-mark, fate odds/chaos modifier tables, random-event focus-category sets, consequence/general/location stopwords, and NPC honorifics are all yaml-driven. Engine-specific moves (`dialog`, `ask_the_oracle`, `world_shaping`) consolidated into a single `engine_moves:` section read by `builtins.available_moves` and the brain schema. Reads that used to silently fall back — unknown fate odds, unknown chaos factors, unmatched score-to-odds, out-of-range event-focus rolls, invalid progress ranks — now raise.

Cleanup along the way: `_STAT_NAMES` frozenset, `CORRECTION_OUTPUT_SCHEMA` constant, and several hardcoded enums in the brain schema replaced by lookups against their yaml sources. A tranche-2.1 residue in `ai/schemas.py` (a hardcoded 4-settings tuple with `try/except pass`) now uses `list_packages()`.

Two tests flipped from expecting silent fallback to expecting raises.

---

## [0.54.0] — 2026-04-18

Tranche 2 of the config-strict refactor: settings discovery and inheritance.

Setting discovery is yaml-driven — no more Python mapping tables. `list_available()` scans `data/settings/*.yaml`; `get_moves()` reads `parent:` from the child. Settings yaml is strict-parsed with required top-level keys; `parent` and `creation_flow` are optional. Oracle paths, genre constraints, and creation flow now use per-field inheritance through the parent chain.

Delve yaml collapsed to pure inheritance from Classic. `active_package` no longer swallows errors on invalid setting ids. Oracle-path cascades deleted; `SettingPackage.oracle_data_for(path)` walks the chain. Multilingual residue in `parser.py`, `chapters.py`, and `web/serializers.py` removed along with two obsolete tests.

`ARCHITECTURE.md` "Settings YAML format" section rewritten.

---

## [0.53.0] — 2026-04-18

Tranche 1 of the config-strict refactor. Every domain-config access now raises on missing data; every tuning number that determines engine behaviour moved to yaml.

Strict dataclasses in `engine_config.py` and `config_loader.py` — no hidden Python defaults, no `get_raw(key, default)`. Nineteen new `engine.yaml` sections consolidating magic numbers from across the engine (TF-IDF, fuzzy-match, monologue-detection, rate-limit, retry, memory, description-dedup, rule-validator, parser, chapter, and more). Fifteen `get_raw` call sites and dozens of individual `.get(k, default)` fallbacks replaced with strict lookups. `engine_loader.damage()` rewritten to raise on missing paths, positions, or non-numeric leaves.

AI-call exception suppression is now a documented carve-out: twelve sites across `brain.py`, `narrator.py`, `validator.py`, etc. each log at warning level and carry a one-line comment pointing to the policy in `provider_base.py`'s module docstring.

Ruff config adds `SIM401` to ignore — it conflicts with the no-fallback rule on `dict.get`.

---

## [0.52.2] — 2026-04-17

Config-driven cleanup, second pass.

Two architect-validator prompts moved from Python f-strings to `prompts.yaml`. The `{dash}` placeholder retired project-wide — em-dashes are now literal `—` in all 33 prompt locations. Format-leak patterns and curly-quote regexes moved from module-level constants in `ai/rule_validator.py` to `engine.yaml`.

New EngineSettings helpers `compiled_patterns`, `compiled_labeled_patterns`, and `compiled_pattern` cache regex lists on the settings instance.

---

## [0.52.1] — 2026-04-17

Config-driven cleanup: AI-facing text removed from Python.

Seven prompts (validator system, director task, revelation check, and related blocks) relocated from f-strings in `ai/validator.py`, `director.py`, and `ai/brain.py` to `prompts.yaml`. A new `validator:` section in `engine.yaml` carries twelve rewrite-instruction templates (replacing an eleven-branch if/elif), twenty-seven consequence stem mappings, and regex pattern lists for agency violations, miss silver linings, and annihilation markers.

`run.py` startup fixed (stale re-export import). Stale `pacing={...}` log line in `director.py` removed.

---

## [0.52.0] — 2026-04-17

Legacy tracks and XP — campaign progression mechanics.

Three campaign-persistent `ProgressTrack`s on `CampaignState` (`legacy_quests`, `legacy_bonds`, `legacy_discoveries`), all epic rank. `mark_legacy` consumes `outcome.legacy_track` (which was previously set but never acted upon). Filled boxes grant XP; XP spent on asset upgrades via `advance_asset`. Bonus XP when a vow completes with its linked threat at high menace.

Architectural fix: new `apply_progress_and_legacy` helper in `game/finalization.py` consumed by turn, correction (input_misread re-roll), and momentum burn. Without it, correction and momentum burn silently dropped progress marks and legacy rewards from re-resolved outcomes. `/status` reports XP and legacy progress narratively (no numbers).

---



## [0.51.0] — 2026-04-16

Codebase audit and modularization. No new features.

Five splits: `game/tracks.py`, `game/momentum_burn.py`, `ai/architect_validator.py`, `ai/json_utils.py`, and `check_story_completion` moved to `story_state.py`. Main turn file dropped from 739 to 599 lines; correction, validator, and brain all shrank comparably.

`apply_opening_setup()` in `setup_common.py` unifies the wiring previously duplicated between `game_start.py` and `chapters.py`. `generate_epilogue` now uses the main parser pipeline instead of four custom regexes. Dead code removed: the `ai/__init__.py` re-export hub (59 lines, zero consumers), nine stub functions in `conftest.py`, Delve's 32-entry atmospheric_drift copy-paste (now inherits from Classic).

---

## [0.50.0] — 2026-04-16

Threats and menace, impacts, NPC name generation via oracles. Plus a typed-config refactor across engine.yaml and settings yamls.

Threats carry rank-based menace tracks linked to vows. Menace advances on MISS and autonomously per scene; full menace forces Forsake Your Vow. Ten impacts defined in `engine.yaml` — each reduces max momentum, some block specific recovery moves. Suffer and threshold handlers mark impacts; recovery handlers clear them. NPC name generation routes through the active setting's `oracle_paths.names` with parent-chain fallback (Delve inherits from Classic).

Typed-config refactor: five new config dataclasses (`ImpactConfig`, `PositionResolverConfig`, `EffectResolverConfig`, `InformationGateConfig`, `NarrativeDirectionConfig`); settings yamls get `SettingConfig`, `VocabularyConfig`, `OraclePaths`, `CreationFlow`. `SettingPackage.raw_config` removed. New `ValidationContext` dataclass replaces threading six loose params through the validator chain. `progress_tracks` added to GameState snapshot/restore.

---

## [0.49.0] — 2026-04-14

Model optimization: GLM-4.7 removed, two-model architecture. Qwen 3 for the narrator, GPT-OSS for everything else. Cost per session down ~53% ($0.117 → $0.055); cost per turn ~$0.012.

The narrator prompt was rewritten for Qwen 3 — MUST/STRICTLY language replaced with concrete WRONG/RIGHT examples, Qwen-specific agency and genre-physics failure modes added. NPC "speech budget" length limits retired in favour of a content-scope rule (answer the question, say nothing beyond it). The rule validator gained four Qwen-specific agency patterns and now strips quoted NPC speech before matching to eliminate a false positive.

Three arbitrary length limits (`monologue_max_chars`, `description_max_chars`, `arc_max_chars`) deleted. Atmospheric-drift wordlists cleaned of terms that have legitimate literal uses in their settings.

Measured over nine Elvira batch sessions: genre-physics violations −71%, player-agency violations −75%, consequence compliance +60%, result integrity +44%. Resolution pacing stable and still dominant.

---

## [0.48.1] — 2026-04-13

Codebase audit. Module ownership cleanup.

`logging_util.py` split: logging stays, user/save directory management and config load/save moved to new `user_management.py`. The `engine/__init__.py` re-export hub eliminated (88 → 8 lines); consumers import directly from submodules. Four underscore-prefixed public functions renamed to drop the underscore. `validator.py`'s `sampling_params()` return dict was being mutated in-place at three sites — now copied before mutation.

---

## [0.48.0] — 2026-04-13

Cluster-based AI model assignment.

Four model clusters (narrator, creative, classification, analytical), each with its own `ClusterConfig` (model, temperature, top_p, max_tokens, max_retries, extra_body — every field required). `model_for_role(role)` and `sampling_params(role)` resolve everything from cluster — no per-role overrides, no fallback chains, no hidden defaults. All fifteen `create_with_retry` call sites refactored to resolve parameters via these two helpers; direct config-field access removed from the AI modules.

New per-role evaluation script in `tests/model_eval/` — tests brain, validator, and extraction in isolation against fixed inputs. Uses the same provider/config infrastructure as the engine.

Bug fixes: duplicate `top_k`/`extra_body` assignment in `provider_openai.py`; `tick_chaos` floor 3 → 1 per Mythic 2e; hardcoded `% 5` in `consequences.py` replaced by `eng().pacing.npc_agency_interval`; stale accumulator leakage on failed turns fixed by draining `_pending_events` and `_token_log` at turn start.

## [0.47.0] — 2026-04-13

Combat, expedition, and scene-challenge track lifecycle. Multi-model support. Validator tuning.

`available_moves` now filters progress tracks by `status == "active"`. `complete_track` clears combat_position on combat track completion or failure; `sync_combat_tracks` removes orphaned active combat tracks when combat_position is cleared by narrative. Adventure moves mark progress on an active scene-challenge track on hit. `/tracks` command added.

Multi-model: `extra_body` configurable per-role via `PerRoleDict`, `validator_model` now actually used (was silently falling back to brain_model), `fast_model` field added for lightweight extraction roles. `run_tool_loop` accepts `extra_body`.

Validator RESOLUTION PACING rewritten: information discipline rather than sentence counting, with an explicit anti-instruction against counting (GLM hallucinated the old rule). RESULT INTEGRITY skips STRONG_HIT and dialog. Empty-response fallback retries without json_schema.

Bug fixes: `enter_the_fray` without track_name auto-generates from player intent instead of crashing; `SceneLogEntry.oracle_answer` added; `characters_list` INSERT OR REPLACE prevents crash on duplicate NPC ids.

## [0.46.50] — 2026-04-12

Config-driven prompt file. Shared resolution and narration. Typed config.

Prompt file path configurable via `config.yaml → ai.prompts_file`. New `resolve_action_consequences` and `narrate_scene` helpers in `game/finalization.py` unify four duplicated narrator → parse → validate sequences across turn, correction, and momentum burn. `SceneContext` dataclass reduces `_finalize_scene`'s signature from 18 parameters to 8. `_ConfigNode` replaced by a typed `AppConfig` dataclass tree with full mypy coverage. Status commands (`/status`, `/score`) now fully narrative — no numbers, no momentum, no chaos factor.

Brain back to single-call prompt injection. All game state (available moves, NPCs, active tracks) injected as XML context blocks; no tool loop. ~13× Brain token reduction (67K → ~5K over 10 turns).

## [0.46.0] — 2026-04-12

Track lifecycle. Connection tracks replace bond.

Progress tracks now have creation, progress marking, and completion/failure. `track_creating_moves` in `engine.yaml` maps moves to track types. Engine creates a `ProgressTrack` from Brain output (track_name + track_rank both required). Vow tracks auto-create linked `ThreadEntry`. `ProgressTrack.status` (active/completed/failed); `_find_progress_track` filters by status and disambiguates multi-matches via `target_track`.

`NpcData.bond` and `bond_max` deleted. All bond reads go through `get_npc_bond(game, npc_id)`, which reads `filled_boxes` on the NPC's connection track. The `bond` effect in move outcomes marks connection-track progress instead of mutating NpcData. Callers across stance, resolvers, prompt builders, director, architect, chapters, lifecycle, activation, tools, correction, metadata, processing, and serializers all migrated.

`/status` and `/score` commands — engine answers directly via `strings.yaml` templates, no AI call. `build_state` removed (80 lines); the per-turn state blob is gone. `turn_complete` WebSocket message replaces `state` as end-of-turn signal.

## [0.45.0] — 2026-04-11

Full Forge move system. Data-driven consequence resolution. Combat position.

New `Move` dataclass and setting-level loader in `datasworn/moves.py`, with expansion merge (Delve → Classic, Sundered Isles → Starforged). New `mechanics/move_outcome.py` with fifteen effect types (momentum, health, spirit, supply, integrity, mark_progress, pay_the_price, next_move_bonus, suffer_move, position, legacy_reward, fill_clock, bond, disposition_shift, narrative) plus three handlers for suffer, threshold, and recovery moves. All 112 moves across four settings have structured outcomes in `engine.yaml`.

`apply_consequences` and its category-based routing deleted — `resolve_move_outcome` now handles everything. Progress rolls are first-class: `roll_progress()` uses `filled_boxes` vs 2d10 instead of action dice. `combat_position` on `WorldState` (in_control, bad_spot) set by move outcomes. `available_moves` tool filters by game state — combat position restricts combat moves, track existence gates progress moves, suffer/threshold moves are excluded as reactive-only.

Brain move enum now covers all Datasworn moves across all settings; Brain prompt directs to call `available_moves` instead of a hardcoded list.

## [0.44.0] — 2026-04-11

Mythic GME 2e integration: fate system, scene structure, random events.

Fate system: fate-chart resolver (9×9 odds/chaos matrix), fate-check resolver (2d10 + modifiers), random-event trigger on doublets, likelihood resolver (NPC disposition + chaos + resources → odds), `fate_question` Brain tool.

Scene structure replaces chaos interrupts: `check_scene()` rolls d10 vs chaos factor → expected/altered/interrupt. Scene Adjustment Table drives altered scenes. Scene-end bookkeeping runs for every scene type including dialog (stance evaluation, list maintenance, consolidation at 25 entries). Chaos factor range changed from 3–9 to 1–9 per Mythic 2e.

Random events pipeline: event focus (12 categories) → target selection → meaning table (actions/descriptions) → structured `RandomEvent`. Weighted list selection, pending event buffer with drain, `<random_event>` tag in narrator prompt.

Director reduced: pacing removed from Director output and schema — now fully engine-computed from scene structure + narrative direction. NPC reflections and AIMS retained. Legacy `mechanics.py` monolith deleted (1011 lines of dead code).

## [0.43.0] — 2026-04-11

Config-driven refactor. Mechanics modularized.

Twenty-eight magic numbers moved from Python to `engine.yaml` — NPC reflection thresholds, death corroboration, seed importance floor, gate memory counts, retrieval weights, monologue/description/arc limits, opening clock defaults, move routing, architect forbidden moods. New yaml sections: `enums`, `memory_retrieval_weights`, `opening`, `move_routing`, `architect`.

Narrator-metadata and opening-setup schemas converted to lazy cached functions with config-driven enum values. Legacy `mechanics.py` monolith (1030 lines) split into a `mechanics/` package with `world.py`, `resolvers.py`, `consequences.py`, `stance_gate.py`, `engine_memories.py`. New `game/finalization.py` provides shared `apply_engine_memories` and `apply_post_narration` used by turn, correction, and momentum burn.

Bug fix: correction and momentum burn now run memory consolidation and set `needs_reflection` flags (previously skipped).

## [0.42.0] — 2026-04-10

GLM-4.7 prompt tuning. Config-driven prompts.

Narrator system prompt restructured for GLM-4.7's begin-bias: hardest constraints (GENRE PHYSICS, PLAYER AGENCY, CONSEQUENCE COMPLIANCE) at the top in MUST/STRICTLY language. New GENRE PHYSICS constraint: materials must not exhibit consciousness, memory, or transformation. All task templates, instruction fragments, and secrets labels moved from Python to `prompts.yaml`; `prompt_builders.py` is now pure XML assembly.

Atmospheric-drift wordlists expanded for GLM patterns across all four settings (weep, ooze, writhe, visage, reshape, phantom). Three new player-agency regex patterns for GLM-specific violations. New GENRE PHYSICS check in the LLM validator. Architect: rule-based mood sanitizer strips forbidden moods (surreal, haunted, dreamlike) from blueprint acts. Narrator temperature 0.8 → 1.0 per Z.ai recommendation.

Elvira results after tuning: retries 19 → 5, failures 2 → 0, first-pass rate 11% → 44%, zero genre drift, zero spatial issues.

## [0.41.0] — 2026-04-10

Brain and Director tool calling. Ask the Oracle.

Brain and Director both moved to two-phase calls: optional tool loop followed by json_schema. Director can query NPCs, threads, and clocks through tools. `ask_the_oracle` move: engine rolls an action/theme meaning pair from Datasworn tables, result injected as `<oracle_answer>` tag in the narrator prompt.

Bug fix: the Director's fallback accumulator reset was zeroing NPC importance every time it ran without producing a reflection, preventing NPCs from reaching the reflection threshold. Now only resets on successful reflection or API failure.

## [0.40.0] — 2026-04-10

Step 1: oracle roller. Vocabulary control. Cleanup.

- `OracleResult` dataclass; `OracleTable.roll()` preserves actual die value
- `roll_oracle` Brain tool: setting-aware Datasworn oracle roll
- Vocabulary control per setting: substitutions, sensory palettes, config-driven atmospheric drift detection in rule validator. All four settings configured
- Visual bar characters removed from clock display (accessibility)

## [0.39.0] — 2026-04-10

Steps 4–6: consequence sentences, NPC stance, information gating. Code audit.

- Consequence sentence templates in engine.yaml; `generate_consequence_sentences()` produces narrative sentences per mechanical change
- `<consequence>` tags in narrator prompt (required for action turns); validator checks keyword presence
- NPC stance matrix in engine.yaml: 60 entries mapping (disposition, bond, move_category) → stance + behavioral constraint
- `resolve_npc_stance()` replaces raw disposition/bond in narrator prompt with concrete instructions
- Information gate (0–4) per NPC per scene; `compute_npc_gate()` from scenes known, gather successes, bond, stance cap
- Prompt builder filters NPC data by gate level: gate 0 = name only, gate 4 = full secrets
- `gather_count` field on NpcData, incremented on successful gather_information
- `pay_the_price` table in engine.yaml for generic MISS consequences
- Code audit: operator precedence bug fixed in position resolver, floor_at_risky logic bug fixed, mypy 0 errors across 100 files, serialization unified (RollResult/BrainResult/TurnSnapshot on SerializableMixin), sampling_params filters None values, `_safe_name` hardened, CHANGELOG trimmed
- Stale `tests/playerbot elvira` directory removed; requirements.txt cleaned

## [0.38.0] — 2026-04-10

Steps 3.5 + 3.6: database layer and tool calling infrastructure.

- SQLite read model (`engine/db/`): 8 tables mirroring GameState, full sync after every state change, query functions for NPCs/memories/threads/clocks
- Tool registry (`tools/registry.py`): `@register("brain", "director")` decorator, type hints → OpenAI schemas
- Tool handler (`tools/handler.py`): dispatch + iterative tool-call loop
- Built-in query tools: `query_npc`, `query_active_threads`, `query_active_clocks`, `query_npc_list`
- Tool calling probe (`tests/tool_calling_probe.py`): 15 test cases, Qwen 87% / GLM 93% pass rate

## [0.37.0] — 2026-04-09

Steps 2 + 3: Brain slimming, metadata extractor split, code audit.

- Position/effect/time resolvers: engine-computed from game state via engine.yaml weights
- BrainResult stripped from 13 to 9 fields; Brain schema and prompts updated
- Engine-generated memories and scene context from templates in engine.yaml
- Metadata AI schema reduced from 10 to 5 fields (NPC detection only)
- SerializableMixin eliminates to_dict/from_dict boilerplate across 20 dataclasses
- Test stubs migrated to conftest fixtures
- Legacy NiceGUI code removed, XSS fixes in HTML client, i18n for status display
- Dead code: `_resolve_slug_refs`, `apply_memory_updates`, game_data JSON parsing

## [0.36.0] — 2026-04-08

Character creation overhaul. AI surface reduction.

- ProgressTrack, ThreadEntry, CharacterListEntry dataclasses; Mythic lists seeded at creation
- GameState extended with assets, vow_tracks, truths
- Stat validation and creation enforcement against engine.yaml constraints
- Truths in narrator prompt as `<world_truths>` block; truth-to-thread derivation
- Chaos factor derived from background vow keywords
- Director pacing and act transitions moved to engine (deterministic)
- Opening clock and time_of_day set by engine before AI calls
- Memory emotional_weight derived from (move_category, result, disposition) via engine.yaml
- Full creation UI: truths, name tables, backstory roll, vow rank, starting assets

## [0.35.0] — 2026-04-08

Strict typing. Elvira batch runner. Validator tuning.

- `disallow_untyped_defs = true` in mypy — 73 files, zero errors
- Dead code and legacy NiceGUI remnants removed
- Snapshot/restore blueprint asymmetry fixed
- Elvira: batch runner, `--setting`/`--style` CLI overrides, token logging
- Validator false positive reduction (73% → 86.5% compliance)

## [0.34.0] — 2026-04-08

Code audit. Minimal UI.

- Server binds localhost by default; WebSocket origin check added
- Dice roll display removed from client (design doc: player sees only narration)
- HTML client fully i18n'd via strings.yaml
- 266 dead NiceGUI-era strings removed
- emotions.yaml gaps filled (36 terms)
- chapters.py refactored into 6 focused functions
- config.yaml top_p simplified to single default with per-role overrides

## [0.33.0] — 2026-04-07

Prompt rewrite for Qwen3. Hybrid validator.

- prompts.yaml rewritten: data-driven hierarchy, positive instructions, concrete examples
- Hybrid validator: rule-based regex + LLM semantic checks, merged results
- Retry overhauled: 3 retries, correction in system prompt + user message, best-of selection
- Prompt stripping on retry: NPC secrets/memories removed for pacing violations
- Narration history skipped on retry to prevent poisoned few-shot
- models.py split into 4 files (models_base, models_npc, models_story, models)
- Elvira fail rate 84% → 27%

## [0.32.0] — 2026-04-06

NiceGUI replaced with Starlette + WebSocket.

- Starlette + uvicorn server with 19 async WebSocket handlers
- Single-page HTML client: screen reader accessible, scene headings, aria-live
- Elvira WebSocket mode (`--ws`): full stack testing via `debug_state` endpoint
- Chapter archives and dead persistence code removed

## [0.31.0] — 2026-04-06

Project independence. Renamed to Straightjacket.

- ARCHITECTURE.md: turn pipeline, module ownership, file map, extension guides
- ORIGINS.md: project history, EdgeTales credits
- VERSION reads from pyproject.toml; bootstrap_log for early-loading modules

## [0.30.0] — 2026-04-06

NPC arc system. Config-driven moves.

- `NpcData.arc`: narrative trajectory, set by Director, evolves each reflection
- Instinct locked after first fill; arc evolves per reflection
- Phase-trigger deduplication in Director scheduling
- `process_npc_details` memory guard: rejects spurious identity reveals
- 31 window-dressing tests removed

## [0.29.1] — 2026-04-05

Serialization tightening.

- `from_dict()` tightened: direct key access, no fallback defaults
- Hardcoded fallback blueprints removed from architect
- chapters.py and prompt_builders.py split out from monolithic modules

## [0.29.0] — 2026-04-05

Config-driven game logic. Defensive code removal.

- Bugfixes: Elvira CurrentAct/ChapterSummary dict access, fuzzy match `continue` bug, missing fields
- Move categories, disposition shifts, NPC seed emotions moved to engine.yaml
- `Resources.adjust_momentum`/`reset_momentum` require explicit config values
- Defensive `.get()` guards removed from `from_dict` methods
- Elvira added to mypy coverage

## [0.28.0] — 2026-04-05

ChapterSummary + CurrentAct dataclasses. Bugfix: gameplay.py sub-object nesting.

## [0.27.0] — 2026-04-05

MemoryEntry dataclass (10 fields). Dead `prompts.py` removed.

## [0.26.0] — 2026-04-04

Typed models: NpcData, ClockData, SceneLogEntry, NarrationEntry. Module split. Config-driven schemas.

## [0.25.0] — 2026-04-03

NPC hardening. Off-screen death detection. Elvira test bot.

## [0.24.0] — 2026-04-01

XML injection escaping. NPC rename via correction.

## [0.23.0] — 2026-04-01

Datasworn integration. Setting packages with vocabulary control and genre constraints.

## [0.22.0] — 2026-03-31

Constraint validator with `validate_and_retry()` and architect genre check.

## [0.21.0] — 2026-03-30

GameState decomposition into typed sub-objects. Save format break.

## [0.20.0] — 2026-03-30

Constraint validator. Open model prompt hardening. emotions.yaml (131 entries).

## [0.19.0] — 2026-03-29

engine.yaml: all damage tables, resource caps, NPC limits, chaos, pacing, narrative direction.

## [0.18.0] — 2026-03-28

strings.yaml: UI text extraction (372 keys). German removed from code.

## [0.17.0] — 2026-03-28

Upstream UI sync. turn.py `_finalize_scene` eliminates dialog/action duplication.

## [0.16.0] — 2026-03-28

Upstream sync v0.9.66. Revelation verification. Fired clock tracking.

## [0.15.0] — 2026-03-23

AI call audit. Metadata extractor receives mechanical ground truth.

## [0.14.0] — 2026-03-22

KISS cleanup (13.4K → 11.2K lines). Voice I/O removed.

## [0.13.0] — 2026-03-22

Upstream sync v0.9.61. GLM 4.7 as default.

## [0.12.0] — Provider tuning, multi-model testing.

## [0.11.0] — YAML configuration, multi-instance support.

## [0.10.0] — Modular refactor from upstream v0.9.44. Monolithic engine.py → packages.
