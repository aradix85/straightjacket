# Principle 4 — No backwards compatibility: fix-file

Audit of 2026-10-17, all three passes of AUDIT.md over `src/straightjacket/`, in one session. Paths are relative to `src/straightjacket/`; line numbers are those before the session's fixes. Every violation below is fixed in release 2026.10.17.10.

## Pass 4a — Dataclass field defaults

References pass 2d: the 196 defaults listed in `docs/audit/fix_principle2.md`, removed module by module in roadmap 9h.4.

## Pass 4b — Migration patterns

No code accommodates an old save format: no version check or conversion, no renamed-field handling, and no comment about an old format (comments are banned in any case). `persistence.py` writes `engine_version` into a save and never reads it back, which is right for a format that is not migrated.

The `.get(` hits read external or protocol data (Datasworn, SDK responses, WebSocket messages, AI answers, optional per-move yaml such as trigger hints) or internal dictionaries; none of them reads a save. The ones that hide a missing value from the engine's own data belong to principle 3 and are listed under Findings for later principles.

## Pass 4c — Permissive deserialization

- **P4-01** `engine/serialization.py:72` — a null was accepted for any field, so a save holding null where a string or a number is required loaded as if it were valid. Fixed: null is accepted only where the type allows None (`Optional` or `Any`).
- **P4-02** `engine/serialization.py:79`, `engine/serialization.py:86` — a field typed as a dataclass, or a list of them, took a plain value unchanged when the save held one instead of an object, so the game ran with a string where a clock belongs. Fixed: such a value raises.
- **P4-03** `engine/models_base.py:68` `Resources.restore` — restoring a turn's snapshot skipped keys the class does not know and kept the current value of any key the snapshot lacked; snapshots are saved with the game, so an old save's snapshot restored half. Fixed: it deserializes strictly, as `WorldState.restore` already did.
- **P4-04** `engine/engine_config.py` — the engine yaml sections built field by field (fate, progress and its track types, engine moves, stopwords, the position and effect resolvers, the information gate, narrative direction, succession, keyed scenes and their pattern grammars, the Adventure Crafter with its blueprint and mappings, clock keyed scenes, clocks and their fill entries, random events and their mappings, Pay the Price, roll bonuses) ignored keys they did not know, so a key left behind after its reader went, such as the fate modifiers that left in 2026.10.17.8, would have stayed unnoticed. Fixed: `_reject_unknown` checks every one against its dataclass, at every depth; the yaml held no such key.
- **P4-05** `engine/config_loader.py:101` — `config.yaml` skipped a cluster that was not a mapping, ignored keys it did not know at every level, and read a cluster's `extra_body` with an empty fallback. Fixed: every level is checked for unknown and missing keys, and `extra_body` is required, as every cluster in the shipped file already has it.

Not violations: the settings loader's partial classes, which parse inheritance and already refuse unknown keys; the provider adapters' optional SDK fields; the cluster `extra_body` itself, a passthrough to the provider by design.

## Findings for later principles

Recorded for roadmap 9h.13:

- Principle 3: `engine/persistence.py:81` skips a save it cannot read while listing saves, so the player never sees it to load or delete it; `engine/user_management.py:66` swallows a failed write of the user settings; `engine/models_story.py:220` skips the blueprint part of a snapshot when the blueprint is missing on either side; `engine/logging_util.py:20` and `engine/bootstrap_log.py:7` log an unknown level as info; `engine/emotions_loader.py:38` turns an unknown disposition into neutral; `web/serializers.py:30`, `62`, and `101` show the raw key when a label is missing; the opening and metadata extractions are read with `.get` and empty fallbacks although their fallback dictionaries carry every key (`engine/game/setup_common.py:114` to `134`, `engine/game/scene_finalization.py:46`, `48`, `150`, `engine/game/chapters.py:105`, `engine/game/succession.py:300`); `engine/game/finalization.py:197` to `201` and `engine/game/director_runner.py:11` pass internal dictionaries whose keys are read with fallbacks where a dataclass would make them required.
- Principle 5: the user settings file `settings.json` is written at every new game and chapter (`engine/game/game_start.py:256`, `engine/game/chapters.py:111`) and read by nothing.
- Test hygiene, fixed in this session: `tests/test_fact_resolution.py` seeded the random generator before building its game, whose opening and blueprint run in two threads that both draw from it, so the test failed about one run in ten; it now seeds after the game is built.

## Grep log

Run with a script kept outside the repository, over every `.py` file under `src/straightjacket/`.

| Pass | Query | Hits |
| --- | --- | --- |
| 4b | `\.get\(` | 151 |
| 4b | a quoted key tested with `in` (`if "key" in x`, `"key" in x else`) | 21 |
| 4b | `except` naming KeyError, LookupError, AttributeError, TypeError, or IndexError | 1 |
| 4b | `getattr(x, name, default)` | 18 |
| 4b | `hasattr(` | 1 |
| 4b | legacy, backward, compat, migrat, old format, deprecated, fallback (case-insensitive) | 177, none about a format; "legacy" is the game's legacy tracks |
| 4c | `**kwargs`, `**data` | 3 |
| 4c | `extra=` | 0 |
| 4c | `isinstance(..., dict / list / str)` branches that might accept two shapes | 46, all external or protocol data |
| 4c | builders in `engine/engine_config.py` and `engine/config_loader.py` that pick known keys, read by hand | 18 builders |

Saves on disk were loaded with the strict loader as a check: the only save in the current format loaded; 126 older ones fail on the field `setting_archetype` that left in 2026.10.17.6, as they should.
