# Settings, rulesets, and character creation

A setting is a data package: a Datasworn JSON file with its world (oracles, truths, atlas, and NPCs) and a settings yaml with what the engine needs to use it (vocabulary, oracle paths, creation flow). Every Datasworn file also names a ruleset: a file of `type: ruleset` is its own, and an expansion names the one it extends in `ruleset`. A setting plays the ruleset its file names, and every file of its chain must name the same one, or loading stops. The shipped settings are classic Ironsworn (`classic`), Starforged (`starforged`), and Sundered Isles (`sundered_isles`), plus Delve (`delve`), which only extends classic; they play two rulesets, classic (classic and Delve) and Starforged (Starforged and Sundered Isles). `setting/packages.py` loads the packages, and `ruleset/datasworn.py` → `load_ruleset` the ruleset a setting plays.

## Rulesets

A ruleset's Datasworn data are its own file and the expansions in the setting's chain, in that order, so an expansion's move replaces the ruleset's: their rules (stats, condition meters, impacts, special tracks), their moves with the tables each carries, and their assets. The setting reads only the world of its files, its oracles and truths, and the ruleset only their rules, moves, and assets; a move's suggested tables are oracles, which the ruleset finds along the setting chain (`docs/mechanics.md`, Moves and outcomes). One exception: every classic setting rolls Delve's Advance a Threat from Delve's file, even without Delve in its chain, since Delve is classic's expansion (`threats.advance_a_threat` in `ruleset/threats.yaml`, `ruleset/moves.py` → `move_of_file`). So a setting whose chain holds no ruleset file, an expansion of Starforged without a parent, still plays Starforged's moves, while its oracles are only its own. A new character's paths and starting assets come from the setting's own file (`Ruleset.setting_file`), as each book offers its own.

What Datasworn does not carry lives in the ruleset layer's yaml (`ruleset/`): the moves' outcomes and effects, their categories and availability, the creation array, the ranks, and the rest `docs/mechanics.md` describes. It holds for every Ironsworn ruleset, and where one ruleset differs, its entries are keyed by its id, as classic's outcomes are under `move_outcome_overrides`.

## Character creation

Creation is driven by the Datasworn data of the setting and its ruleset, with no AI call: the client receives the options from `web/serializers.py` → `build_creation_options`, the setting's `creation_flow` decides which options it offers, `ruleset/character.py` → `make_character` checks and builds what the ruleset decides of the character: its stats with the array of `ruleset/stats.yaml` (`docs/mechanics.md`, Stats), its paths, from which its concept is named, its starting assets from the setting's `starting_asset_categories`, and its background vow, and `game/game_start.py` → `validate_creation` checks the rest (the name, the tone, and that a setting without truths gets none). A new game and a successor take up their character through the same `take_up_character`. The chosen truths are stored on the game state and reach every narrator prompt as a `<world_truths>` block (`prompt_blocks.py` → `truths_block`), which the narrator treats as canon. How creation seeds the first threads and tracks is in `docs/mechanics.md`.

## Adding a new setting

1. Place the Datasworn JSON at `data/<datasworn_id>.json`, where `<datasworn_id>` is the value the yaml declares. The engine reads Datasworn 0.1.0, the form `data/data.py` downloads the shipped files in, pinned to one commit; the format is documented at [github.com/rsek/datasworn](https://github.com/rsek/datasworn). The file is a ruleset or an expansion of one the engine has (Adding a new ruleset).
2. Create `data/settings/<id>.yaml`, with `data/settings/starforged.yaml` as template. The file's stem is the setting id the engine uses; `datasworn_id` inside it points at the JSON. A `parent` brings in the parent's oracles and yaml blocks (Inheritance), not its ruleset, which the file names.
3. The setting appears in character creation automatically; no Python changes.

Discovery is yaml-only: `list_packages()` scans `data/settings/*.yaml`.

## Adding a new ruleset

1. Place its Datasworn JSON, of `type: ruleset`, at `data/<id>.json`; its `_id` is the ruleset's id.
2. Give its moves what Datasworn does not carry: their outcomes in `ruleset/move_outcomes.yaml`, under `move_outcome_overrides.<id>` where they differ from the shared ones, and their categories and availability in `ruleset/move_categories.yaml` and `ruleset/move_availability.yaml` for moves no ruleset has yet.
3. Add a setting whose Datasworn file is the ruleset or an expansion of it (Adding a new setting).

This holds for a ruleset of the Ironsworn family. A system that is no Ironsworn needs a ruleset package of its own beside the shared layers (ARCHITECTURE.md, The four layers), which roadmap step 37 builds.

## Settings yaml format

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `playable`, `description`, `oracle_paths`, `generators`, `vocabulary`. Optional: `parent`, and `default_tone` and `creation_flow` for a setting whose parent chain supplies them (Inheritance). `default_tone` names one of the tones in `story.tones` (`gamemaster/story.yaml`), the one character creation offers first, which loading does not check; the player's choice reaches the narrator as its tone authority (`docs/mechanics.md`, Blueprint). A missing required key raises `KeyError`, and so does a key the loader does not know, at the top level or inside `oracle_paths`, `vocabulary`, or `creation_flow`.

```yaml
id: your_setting
title: "Your Setting Name"
datasworn_id: your_setting
playable: true
description: "One paragraph."
parent: classic

vocabulary:
  substitutions: { spaceship: "starship — worn, patched" }
  sensory_palette: "Metal, recycled air, ozone."

oracle_paths:
  action_theme: ["core/action", "core/theme"]
  backstory: "launching_your_campaign/character/backstory"
  threats: "launching_your_campaign/starting_sector/trouble"

generators:
  npc:
    given_name: "character/name/given_name"
    family_name: "character/name/family_name"
  location:
    theme: "location_theme/type"
    feature: "location_theme/{theme}/feature"

creation_flow:
  has_truths: true
  has_backstory_oracle: true
  has_name_tables: true
  has_ship_creation: false
  starting_asset_categories: [companion, module]
```

`id` must equal the yaml file's stem, which the loader checks, and `datasworn_id` is the basename of the Datasworn JSON. `playable: false` keeps a package out of character creation and out of Elvira's choice, as for Delve. `parent` names the setting it inherits from. `vocabulary` keeps the narrator's word choice in the setting and is the one block of hand-written game content the Yaml content boundary allows (CONTRIBUTING.md). `oracle_paths.threats` drives threat naming (`docs/mechanics.md`). `generators` names, for each category registered in `gamemaster/generation.yaml` apart from `fact`, the oracle table every role of it rolls: `npc` for NPC names (and the name buttons of character creation), `location` and `settlement` for places. A role's path may name an earlier role of the same category in braces, which stands for the table that role's row links to or for its text; a name that no earlier role rolls raises at load (`docs/mechanics.md`, Generators). `creation_flow` decides what creation offers: truths, the backstory oracle, the name tables, and the starting-asset categories (`web/serializers.py` → `build_creation_options`); a step with nothing to offer stays hidden. `has_ship_creation` is required and read by nothing until roadmap step 28.

## Inheritance

With `parent:`, an oracle path the setting's own file lacks is looked up along the chain, and blocks inherit from the parent yaml, resolved at load. `oracle_paths` and `creation_flow` inherit per field: an omitted field takes the parent's value, a present field (even an empty one) overrides it, and a root setting must specify every field. `generators` inherits per category: a category the setting names replaces its parent's. `default_tone` comes from the nearest setting in the chain that names it. `vocabulary` inherits as a whole: when both sub-fields are empty, the block comes from the parent.
