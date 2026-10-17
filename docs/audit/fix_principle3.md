# Principle 3 — No defensive programming, no boilerplate, no dead structure: fix-file

The audit of principle 3 runs one submodule per session (AUDIT.md). Paths are relative to `src/straightjacket/engine/`; line numbers are those before each session's fixes. Each violation names its outcome: fixed in the session's release, or the roadmap substep that holds it. Items marked **[needs human judgment]** wait for the user.

## mechanics/ — 2026-10-17

All four passes over the 28 files of `mechanics/`, with the principle-3 findings that the audits of principles 2 and 4 had seen there (roadmap 9h.13). Every fixed violation below is in release 2026.10.17.11.

### Pass 3a — Broad except

No broad except. Of the three narrow ones, two hid a state:

- **P3-01** `mechanics/world.py:59`, `mechanics/world.py:54` — `advance_time` returned silently when the time of day was empty or not a time phase, so a wrong time stopped moving without a trace; the correction's `time_edit` wrote any string the AI gave. Fixed: `advance_time` raises on a time that is not a phase, and `correction/ops.py` → `_op_time_edit` applies only a value from `enums.time_phases`, as `_op_npc_edit` already drops an unknown status.
- **P3-02** `mechanics/keyed_scenes.py:172`, `178`, `185`, `39` — `_split_two` and `_parse_int` validated the pattern trigger values again, which `KeyedScene` validates at construction and at load. Fixed: one split and `int`.

The third, `mechanics/consequences.py:248`, is P3-33.

### Pass 3b — Guards against impossible states

- **P3-03** `mechanics/fate.py:35` — the fate chart clamped the chaos factor into its columns, though the world keeps it in range; a value outside would have read a wrong column silently, and the `8` copied the chart's width. Fixed: the chart refuses a chaos factor it has no column for, as the fate check refuses one it has no modifier for.
- **P3-04** `mechanics/fate.py:152` — any fate method other than the check played as the chart. Fixed: an unknown method raises.
- **P3-05** `mechanics/fate.py:72` — `roll < 11` repeated what the comparison of tens and ones already decides, with a literal. Fixed: removed.
- **P3-06** `mechanics/clock_consequences.py:17` — a filled clock of a type without a fill entry was skipped with an info line; every clock type has one. Fixed: an unknown type raises.
- **P3-07** `mechanics/keyed_scenes.py:258` — the same for a clock type without keyed-scene fractions. Fixed.
- **P3-08** `mechanics/keyed_scenes.py:76`, `233` — a `threat_menace_phase` trigger naming a threat the game does not hold matched nothing for ever, while a bond trigger naming an unknown NPC raises; threats are never removed. Fixed: raises. The no-match results for clocks and NPCs stay, since clocks are purged and cleared at succession and NPCs are merged.
- **P3-09** `mechanics/impacts.py:9`, `24`, `37`, `51`, `58` — `impact_config` read the impact table with `.get`, so an unknown impact key became a warning in `apply_impact` and a silent skip or the raw key in `clear_impact`, `blocks_recovery`, and `impact_label`; impacts enter the game only through `apply_impact`, with keys from engine yaml. Fixed: `apply_impact` refuses an unknown key, the readers index the table, and the wrapper is gone. The membership test in `mechanics/consequences.py:217` stays as a test, because a `mark` label also covers progress and experience.
- **P3-10** `mechanics/tracks.py:49`, `mechanics/threats.py:25` — `linked_vow_id is None` checks before a comparison that None already fails. Fixed: removed.
- **P3-11** `mechanics/threats.py:18` — an early return for `menace_on_miss <= 0`, where the loop adds nothing anyway. Fixed: removed.
- **P3-12** `mechanics/legacy.py:56`, `mechanics/resolvers.py:72` — division guards for a threat without menace ticks and a clock without segments; both sizes come from config and are never 0. Fixed: removed.
- **P3-13** `mechanics/consequences.py:171` — an autonomous tick clamped a clock it had just checked is not full. Fixed.
- **P3-14** `mechanics/resolvers.py:98`, `126`, `175` — `session_log[-n:] if session_log else []`, where slicing an empty list gives an empty list. Fixed.
- **P3-15** `mechanics/resolvers.py:140` — a position override with no conditions never applied, a shape `engine/position_resolver.yaml` does not have. Fixed: its conditions alone decide, and their table is built once instead of once per override.
- **P3-16** `mechanics/resolvers.py:26`, `168` — position and effect left out the target NPC's disposition and bond when its id did not resolve; `call_brain` accepts only listed NPCs, and nothing removes one before the roll. Fixed: a target id that does not resolve raises.
- **P3-17** `mechanics/bonuses.py:70` — a bonus id not on offer was logged and ignored; `call_brain` refuses any other. Fixed: raises. `mechanics/bonuses.py:33` zipped abilities and their flags with `strict=False`, though the flags are built from the same list. Fixed: strict.
- **P3-18** `mechanics/complications.py:42` — heading off a complication clock that is not open returned False; `call_brain` accepts only open complication clocks, and nothing between the Brain and the averting fills or removes one. Fixed: raises, and `game/action_resolution.py` → `_maybe_avert_complication` adds the consequence without a test.
- **P3-19** `mechanics/move_effects.py:95`, `373` — an unknown effect string became a warning and an effect that did nothing, and an effect type without a handler a warning; effects come from engine yaml. Fixed: `parse_effect` raises, and `apply_effects` indexes its handler table. `mechanics/move_effects.py:87`, `90` — the bare `suffer_move` and the `suffer_move N` branch were unreachable, since the numeric pattern parses `suffer_move N` first and no yaml writes the bare form. Fixed: removed.
- **P3-20** `mechanics/move_outcome.py:34`, `36` — an outcome given as a single string or another sequence was converted to a list; every outcome in `engine/move_outcomes.yaml` is a list. Fixed: removed.
- **P3-21** `mechanics/consequences.py:206` — `pick_template` accepted a single string; every consequence template is a list. Fixed.
- **P3-22** `mechanics/move_handlers.py:75` — `getattr(res, track, None)` for a track already checked to be a resource. Fixed.
- **P3-23** `mechanics/adventure_crafter.py:594` — a game without a setting spawned no turning-point threats and said nothing, where the other generators raise. Fixed: raises.
- **P3-24** `mechanics/adventure_crafter.py:821` — `if seed.acts else 1` for a blueprint that always has acts; `mechanics/adventure_crafter.py:720` — `seeds[:limit]` after a loop that never passes the limit. Fixed.
- **P3-25** `mechanics/adventure_crafter.py:97` with its callers at `116`, `142`, `154`, `169`, `456`, `468`, `480`, and the theme check at `114` — `_check_roll` and the theme check refused what each lookup's own LookupError already refuses. Fixed: removed; the tests expect that LookupError.
- **P3-26** `mechanics/random_events.py:60`, `71` — `_select_from_weighted_list` tested for an empty list and an empty pool, which the test for active entries and weights of at least 1 already exclude. Fixed.
- **P3-27** `mechanics/engine_memories.py:64`, `83`, `119` — a target test written twice, a conditional join of an empty list, and a `"MISS"` fallback for a roll that the dialog test already guarantees. Fixed. `mechanics/engine_memories.py:79` — the intent fallback "general" was readable text in Python (principle 2). Fixed: `ai_text.narrator_defaults.unknown_intent`.
- **P3-28** `mechanics/scene.py:72` — `_roll_single_adjustment` re-rolled Make 2 Adjustments at most ten times and then raised, which a legal run of rolls reaches (about one altered scene with two adjustments in five thousand). Fixed: it draws from the faces that are not Make 2 Adjustments, the same distribution without a bound.

### Pass 3c — Single-use abstractions and dead structure

Of the 160 functions and classes with at most one production reference, most are named steps of a larger function (the `_score_*` factors of position, the effect handlers, the meta handlers). The violations:

- **P3-29** `mechanics/random_events.py:337` — `deactivate_thread` had no production caller; `complete_track` deactivates a vow's thread itself. Fixed: deleted with its test.
- **P3-30** `mechanics/adventure_crafter.py:581`, `mechanics/random_events.py:196` — two copies of `_next_threat_id`, against "What belongs together lives together". Fixed: `mechanics/threats.py` → `next_threat_id`.

### Pass 3d — Wrappers without logic

- **P3-31** `mechanics/world.py:48` — `time_phases` copied a config list for its one production caller. Fixed: inlined. `impact_config` is under P3-09.

### Needs human judgment

- **P3-32 [needs human judgment]** Parameters that exist for tests. Six that production never sets: `mechanics/fate.py:28` `resolve_fate_chart(roll)`, `mechanics/fate.py:140` `resolve_fate(method)`, `mechanics/scene.py:14` `check_scene(roll)`, `mechanics/scene.py:45` `_roll_adjustments(roll)`, `mechanics/random_events.py:26` `roll_event_focus(roll)`, and `mechanics/consequences.py:191` `purge_old_fired_clocks(keep_scenes)`, plus `mechanics/fate.py:100` `resolve_fate_check_with_dice`, the half of `resolve_fate_check` that only tests call. Eleven defaults that every production call overrides: `generate_engine_memories(consequences)`, `mark_legacy(source_rank)`, `advance_asset(kind)`, `resolve_move_outcome(target_npc_id, match)`, `generate_random_event(source)`, `resolve_time_progression(has_location_change)`, `resolve_npc_stance(miss)`, `advance_threat_by_id(marks, source)`, `update_chaos_factor(target_npc_id)`. Principle 3 counts an option production always sets the same way as dead structure, and the rule against defaults names dataclass fields only. Removing them means tests either patch `random` or pass the dice to a scoring function, as `score_action_roll` takes them. Roadmap 9h.15.
- **P3-33 [needs human judgment]** `mechanics/consequences.py:230` to `266`, the 9h.13 item at line 248 — the narrator's consequence sentences are chosen by parsing the engine's own consequence labels back from text. `mark` stands for an impact, progress, and experience; a bond is found by the word "bond" anywhere in the line, so an NPC named Bondar would count as one; and Pay the Price rows pass through the same parser, so the `except ValueError` that turns an unparsable amount into 1 is reached by a row whose last word has a hyphen. A structured consequence (kind, track, amount, NPC) carried in `OutcomeResult` would remove the parser; it touches the effect handlers, the move handlers, boasts, finalization, and the consequence block of the narrator prompt. Roadmap 9h.16.
- **P3-34 [needs human judgment]** `mechanics/adventure_crafter.py:426` `dispatch_meta`, `437` `get_meta_handler_names`, the seven `_meta_*` handlers, and `177` `lookup_characters_template` have no production caller: a Meta plot point is rolled into a turning point as a hit with no effect, and the Characters List template is never consulted. The Adventure Crafter applies Meta plot points, so wiring them follows the source, once each handler is checked against the book (Character Returns without an exited character becomes a new character, which today gets a placeholder name, and the handlers make their own unseeded random generators). Recorded in `docs/divergences.md` until roadmap 9j.7.
- **P3-35 [needs human judgment]** `mechanics/consequences.py:133` — no code creates a clock with `owner_kind` npc, so the agency tick of `check_npc_agency`, its `owner_id is None` guard, and its matching of `owner_id` against NPC names never run. Step 12 gives NPCs goal clocks and decides what owns them.
- **P3-36 [needs human judgment]** `mechanics/move_effects.py:222`, `305`, `319` — a bond, connection-rank, or disposition effect without a target NPC does nothing and logs nothing; the Brain's schema lets `target_npc` be null for every move. Whether `call_brain` should refuse such a move without a target is a decision about the Brain. Roadmap 9h.18. Not violations: no connection track (classic Ironsworn's bonds have none, roadmap 9j.2), a rank already at the top, a disposition with no further shift.

### Not violations

No-match results where the entity can leave the game: clocks in keyed scenes (purged, cleared at succession) and NPCs (merged), and the target NPC in `update_chaos_factor`, which runs after the metadata extraction may have merged it. An empty location, which a failed opening extraction leaves. `find_progress_track` returning None when no track of the type is active. Catch-all keys in yaml (`other`, `_catchall`). Mythic's null exceptional thresholds. The theme-index check in `_roll_plot_point`, which keeps a priority of 0 from wrapping to the last theme. The raising checks after `active_package` in `generation.py` and `tracks.py`. `assets.py` → `asset_data` returning None and the skips in `enabled_abilities` and `roll_bonuses`, which an asset id typed with `/advance` reaches today (below).

### Findings for other submodules and later principles

- web/ (a bug, roadmap 9h.17): `/advance` takes the asset id the player types. `web/handlers.py` → `handle_advance_asset` checks only the kind, so an unknown id is added to the character's assets, and `mechanics/legacy.py` → `advance_asset` spends experience on an upgrade of an asset the character does not hold, does not exist, or has fully upgraded.
- datasworn/: `datasworn/settings.py` → `active_package` returns None for a game without a setting; besides the mechanics callers, which raise, `npc/naming.py:11` and `prompt_blocks.py:48` then return an empty string.
- Principle 1 (roadmap 9h.14): three keyed-scene id helpers with one body and different prefixes (`mechanics/adventure_crafter.py` → `_next_keyed_scene_id`, `mechanics/random_events.py` → `_re_next_keyed_scene_id`, `mechanics/keyed_scenes.py` → `_next_clock_keyed_scene_id`), and `consolidate_threads` beside `consolidate_characters`.
- Principle 5: the `integrity` effect handler, which no yaml uses.

### Grep log

Run with an AST script kept outside the repository, over every `.py` file under `mechanics/`; references are counted over `src/` and `tests/`.

| Pass | Query | Hits |
| --- | --- | --- |
| 3a | `except` with no type, `Exception`, or `BaseException` | 0 |
| 3a | every `except` handler | 3 |
| 3b | `is None` and `is not None` comparisons | 69 |
| 3b | `x or <literal>`, `.get(`, `getattr` with a default, nested `min`/`max` clamps | 9 |
| 3b | `if not x: return` or `continue` | 27 |
| 3b | `isinstance`, `hasattr`, `callable` | 3 |
| 3c | functions and classes with at most one production reference | 160 |
| 3d | functions whose body is one `return call(...)` | 18 |
| 3 | parameters with a default that production never passes, or always passes | 17 |
