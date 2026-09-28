# Settings and character creation

A setting is a data package: a Datasworn JSON file with the game content (moves, oracles, assets) and a settings yaml with what the engine needs to use it (vocabulary, oracle paths, creation flow). The shipped settings are classic Ironsworn (`classic`), Starforged (`starforged`), and Sundered Isles (`sundered_isles`), plus Delve (`delve`), an expansion of classic that inherits from it and is not offered as a setting of its own. `datasworn/settings.py` loads the packages.

## Character creation

Creation is driven by the setting's Datasworn data, with no AI call: the client receives the options from `web/serializers.py` → `build_creation_options`, the setting's `creation_flow` decides which steps it shows, and `game/game_start.py` → `validate_stats`, `validate_creation` check the result against the stat arrays in `engine/stats.yaml`. The chosen truths are stored on the game state and reach every narrator prompt as a `<world_truths>` block (`prompt_blocks.py` → `truths_block`), which the narrator treats as canon. How creation seeds the first threads and tracks is in `docs/mechanics.md`.

## Adding a new setting

1. Place the Datasworn JSON at `data/<datasworn_id>.json`, where `<datasworn_id>` is the value the yaml declares. The format is documented at [github.com/rsek/datasworn](https://github.com/rsek/datasworn).
2. Create `data/settings/<id>.yaml`, with `data/settings/starforged.yaml` as template. The file's stem is the setting id the engine uses; `datasworn_id` inside it points at the JSON.
3. The setting appears in character creation automatically; no Python changes.

Discovery is yaml-only: `list_packages()` scans `data/settings/*.yaml` and `get_moves()` reads `parent:` from the child yaml. There are no Python mapping tables.

## Settings yaml format

Parsed strictly at load. Required top-level keys: `id`, `title`, `datasworn_id`, `playable`, `description`, `oracle_paths`, `vocabulary`. Optional: `parent`, `creation_flow`. A missing required key raises `KeyError`, and so does a key the loader does not know, at the top level or inside `oracle_paths`, `vocabulary`, or `creation_flow`. `playable: false` keeps a package out of character creation and out of Elvira's choice, as for Delve, which only extends classic.

```yaml
id: your_setting                    # yaml stem
title: "Your Setting Name"
datasworn_id: your_setting          # Datasworn JSON basename
playable: true                      # offered in character creation
description: "One paragraph."
parent: classic                     # optional: inherits from this setting

vocabulary:
  substitutions: { spaceship: "starship — worn, patched" }
  sensory_palette: "Metal, recycled air, ozone."

oracle_paths:
  action_theme: ["core/action", "core/theme"]
  names: ["characters/name/given", "characters/name/family_name"]
  backstory: "campaign_launch/backstory_prompts"
  threats: "campaign_launch/sector_trouble"

creation_flow:
  has_truths: true
  has_backstory_oracle: true
  has_name_tables: true
  has_ship_creation: false
  starting_asset_categories: [companion, module]
```

The comments in this example explain the fields; the rule against comments in yaml applies to the files in the repository. `vocabulary` keeps the narrator's word choice in the setting and is the one hand-written block the Yaml content boundary allows (CONTRIBUTING.md). `oracle_paths.names` drives NPC name rolls and `oracle_paths.threats` threat naming (`docs/mechanics.md`). `creation_flow` controls the client's creation steps.

## Inheritance

With `parent:`, blocks inherit from the parent yaml, resolved at load. `oracle_paths` and `creation_flow` inherit per field: an omitted field takes the parent's value, a present field (even an empty one) overrides it, and a root setting must specify every field. `vocabulary` inherits as a whole: when both sub-fields are empty, the block comes from the parent.
